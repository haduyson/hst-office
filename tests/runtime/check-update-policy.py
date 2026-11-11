# SPDX-License-Identifier: AGPL-3.0-only
"""Prove the update-lock templates of the user guide (extensions/hst-vietnamese-tools/help/files) in a real office.

Linux build tree (run as root; the office runs as the build user, the original instdir is never written):
    python3 tests/runtime/check-update-policy.py --instdir upstream/libreoffice/instdir [--out tests/output/update-policy]
  runs "none" and every template: a hard-linked instdir copy gets help/files/hst-office-<name>.xcd as
  share/registry/hst-update-policy.xcd (the file name the guide tells administrators to use).
Installed office, after CI applied a .reg file or the managed preferences of a .mobileconfig (office Python):
    python check-update-policy.py --soffice <soffice> --profile <name|none> --source core|managed --out <dir>

Each run starts the office headless with a fresh profile and a UNO socket and checks:
  - the core schema /org.openoffice.Office.HSTUpdate exists (the lock needs a beta.4 or later core);
  - update_config.load() of the installed extension (what the update check, its dialog and the menu use) returns
    the template's values and reports exactly the template's settings as locked;
  - --source core (.xcd, Windows registry): each property is finalized (read-only) with that value, the other
    settings are not, and a user write is refused; --source managed (macOS): no core property is finalized;
  - the HST command org.hst.office.update:Check reports IsEnabled = ManualCheck (menu and ribbon entry greyed out);
  - --ignored /node/path/Prop (repeatable): that property is not finalized, i.e. a lock CI set where HST Office must
    not read it (Windows: another suite's policy key) has no effect.
Results: <out>/<profile>.json. Exit status 1 when a check fails.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # also when loaded by file path from another probe
from update_policy_office import (  # noqa: E402 - after the path setup
    BUILD_USER, READONLY, command_enabled, core_node, extension_dir, load_extension_module, load_file, start_office,
    stop_office)

ROOT = os.path.dirname(os.path.dirname(HERE))
TEMPLATES = os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "help", "files")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the Windows console is cp1252


PROFILES = load_file("build_update_policy", os.path.join(ROOT, "scripts", "release", "build-update-policy-oxt.py")).PROFILES


def probe(soffice, name, source, out, port, ignored=(), label=None):
    import uno
    results = []
    label = label or name

    def record(check, ok, detail=""):
        results.append({"check": check, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
        print("%-4s [%s/%s] %s%s" % ("PASS" if ok else "FAIL", label, source, check, (" (%s)" % detail) if detail else ""), flush=True)

    ext = extension_dir(soffice)
    cfg = load_extension_module(ext or os.path.join(ROOT, "extensions", "hst-vietnamese-tools"), "update_config")
    expected = {} if name == "none" else {k: cfg.normalize(k, {"true": True, "false": False}.get(v, v))
                                           for k, v in PROFILES[name][0]}
    work = os.path.join(out, "run-" + label)
    os.makedirs(work, exist_ok=True)
    proc, ctx = start_office(soffice, work, port)
    try:
        record("installed extension found", ext is not None, ext)
        try:
            node = core_node(ctx)
            info = node.getPropertySetInfo()
            record("core schema HSTUpdate present", all(info.hasPropertyByName(k) for k in cfg.ADMIN_KEYS))
        except Exception as error:  # noqa: BLE001 - a core without the schema
            node = None
            record("core schema HSTUpdate present", False, error)
        values, locked = cfg.load(ctx)
        for key, value in expected.items():
            record("%s = %r and locked" % (key, value), values[key] == value and key in locked, "read %r" % values[key])
        record("nothing else locked", locked == set(expected), sorted(locked))
        if node is not None:
            final = {k for k in cfg.ADMIN_KEYS if info.getPropertyByName(k).Attributes & READONLY}
            if source == "core":
                record("core finalized = the template's settings", final == set(expected), sorted(final))
                for key, value in expected.items():
                    record("core %s reads %r" % (key, value), cfg.normalize(key, node.getPropertyValue(key)) == value)
                if expected:
                    key = sorted(expected)[0]
                    other = {bool: lambda v: not v, int: lambda v: v + 1}.get(type(expected[key]), lambda v: "beta")(expected[key])
                    try:
                        node.setPropertyValue(key, other)
                        node.commitChanges()
                    except Exception:  # noqa: BLE001 - configmgr refuses a finalized property
                        pass
                    record("user change of %s refused" % key, cfg.normalize(key, core_node(ctx).getPropertyValue(key)) == expected[key])
            else:
                record("no core property finalized (the lock comes from the profile)", not final, sorted(final))
        for path in ignored:
            parent, prop = path.rsplit("/", 1)
            try:
                final = core_node(ctx, parent).getPropertySetInfo().getPropertyByName(prop).Attributes & READONLY
                record("lock of %s not applied" % path, not final)
            except Exception as error:  # noqa: BLE001 - a wrong path is a failed check, not a crash
                record("lock of %s not applied" % path, False, error)
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "Hidden", True
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (arg,))
        enabled = command_enabled(ctx, doc.getCurrentController().getFrame(), "org.hst.office.update:Check")
        want = expected.get("ManualCheck", True)
        record("Kiểm tra cập nhật… %s" % ("enabled" if want else "greyed out"), enabled is want, "IsEnabled=%r" % enabled)
        try:
            doc.close(True)
        except Exception:  # noqa: BLE001 - a hidden document may refuse close(); terminate() ends it anyway
            pass
    except Exception as error:  # noqa: BLE001 - report instead of hanging the job
        record("probe ran", False, repr(error))
    finally:
        stop_office(proc, ctx, work)
    with open(os.path.join(out, label + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"profile": label, "source": source, "results": results}, fh, ensure_ascii=False, indent=1)
    return [r for r in results if r["status"] == "FAIL"]


def linux_tree(instdir, out, port):
    """Every template as share/registry/hst-update-policy.xcd of a hard-linked instdir copy."""
    copy = os.path.join(out, "instdir")
    if not os.path.isdir(copy):
        subprocess.run(["cp", "-al", os.path.abspath(instdir), copy], check=True)
        shared = os.path.join(copy, "share", "uno_packages")  # written at start: a real copy, never the links
        shutil.rmtree(shared, ignore_errors=True)
        subprocess.run(["cp", "-a", os.path.join(os.path.abspath(instdir), "share", "uno_packages"), shared], check=True)
        if os.geteuid() == 0:  # folders made by cp belong to root; the files stay shared links of the build user
            subprocess.run(["find", copy, "-type", "d", "-exec", "chown", BUILD_USER, "{}", "+"], check=True)
            subprocess.run(["chown", "-R", BUILD_USER, shared], check=True)
    target = os.path.join(copy, "share", "registry", "hst-update-policy.xcd")
    failed = []
    try:
        for name in ["none"] + list(PROFILES):
            if os.path.lexists(target):
                os.remove(target)  # a new file each time: never write through a hard link into the original
            if name != "none":
                shutil.copyfile(os.path.join(TEMPLATES, "hst-office-%s.xcd" % name), target)
                os.chmod(target, 0o644)
            failed += probe(os.path.join(copy, "program", "soffice"), name, "core", out, port)
    finally:
        if os.path.lexists(target):
            os.remove(target)
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", help="Linux build tree: test every template on a copy")
    ap.add_argument("--soffice", help="installed office: check the lock CI applied")
    ap.add_argument("--profile", default="none", choices=["none"] + list(PROFILES))
    ap.add_argument("--source", default="core", choices=("core", "managed"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "update-policy"))
    ap.add_argument("--port", type=int, default=22861)
    ap.add_argument("--ignored", action="append", default=[], metavar="/NODE/PATH/PROP",
                    help="a property that a lock CI set elsewhere must leave unlocked (repeatable)")
    ap.add_argument("--label", help="name of this run's results (default: the profile)")
    args = ap.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    if args.instdir:
        program = os.path.join(os.path.abspath(args.instdir), "program")
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
        failed = linux_tree(args.instdir, args.out, args.port)
    elif args.soffice:
        failed = probe(args.soffice, args.profile, args.source, args.out, args.port, args.ignored, args.label)
    else:
        ap.error("--instdir or --soffice is required")
    print("update policy: %d failed check(s)" % len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
