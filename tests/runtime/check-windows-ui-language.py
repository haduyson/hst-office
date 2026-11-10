#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""UI language of an INSTALLED office on one profile: what is stored, what the core UI uses, and a switch.

Run with the office's own interpreter (Windows CI, smoke-install-paths.ps1):
    "<install>\\program\\python.exe" tests/runtime/check-windows-ui-language.py --install "<install>" --profile <dir>
        --label <name> --out <dir> [--expect-stored none|vi|en-US] [--expect-ui vi|en-US] [--need-vi] [--set vi|en-US]

One headless start on --profile (created when missing): reads the UILocale stored in the profile's
registrymodifications.xcu (none: no choice stored), the effective /org.openoffice.Office.Linguistic/General/UILocale,
the UI language in use (Setup/L10N/ooLocale), the installed UI languages and the title of a new Writer document (a
core resource string: "Không tên 1" or "Untitled 1"). --set then writes UILocale the way Options does and closes the
office, so the next run of the same profile shows the switch. Exit 1 when an expectation fails.
Evidence: <out>/ui-language-<label>.json.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the Windows console is cp1252

GENERAL = "/org.openoffice.Office.Linguistic/General"
STORED = re.compile(r'<item oor:path="/org.openoffice.Office.Linguistic/General">'
                    r'<prop oor:name="UILocale" oor:op="fuse">(?:<value>(.*?)</value>|<value/>)</prop></item>')


def stored_choice(profile):
    """The UILocale written in the profile, or None when the profile stores no choice (or does not exist yet)."""
    path = Path(profile) / "user" / "registrymodifications.xcu"
    if not path.exists():
        return None
    found = STORED.findall(path.read_text(encoding="utf-8"))
    return found[-1] if found else None


def node(ctx, path, writable=False):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def start(program, profile, port, log):
    import uno
    cmd = [os.path.join(program, "soffice.exe" if os.name == "nt" else "soffice"), "--headless", "--norestore", "--nologo", "--nodefault",
           "-env:UserInstallation=" + Path(profile).resolve().as_uri(), f"--accept=socket,host=127.0.0.1,port={port};urp;"]
    proc = subprocess.Popen(cmd, stdout=open(log + ".out", "w"), stderr=open(log, "w"))
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    end = time.monotonic() + 180  # a new profile restarts the office once before the socket opens
    while True:
        try:
            ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            time.sleep(2)
            return proc, ctx
        except Exception:  # noqa: BLE001 - not listening yet
            if proc.poll() is not None or time.monotonic() > end:
                proc.kill()
                raise RuntimeError(f"no UNO connection (soffice exit {proc.poll()}, log {log})")
            time.sleep(1)


def observe(ctx):
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    import uno
    hidden = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    hidden.Name, hidden.Value = "Hidden", True
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (hidden,))
    try:
        title = doc.getTitle()
    finally:
        doc.close(True)
    return dict(effective=node(ctx, GENERAL).getPropertyValue("UILocale"),
                ui=node(ctx, "/org.openoffice.Setup/L10N").getPropertyValue("ooLocale"),
                installed=sorted(node(ctx, "/org.openoffice.Setup/Office/InstalledLocales").getElementNames()),
                title=title), desktop


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--install", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=2117)
    ap.add_argument("--expect-stored", choices=("none", "vi", "en-US"))
    ap.add_argument("--expect-ui", choices=("vi", "en-US"))
    ap.add_argument("--need-vi", action="store_true", help="the Vietnamese UI language must be installed")
    ap.add_argument("--set", choices=("vi", "en-US"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, ok, detail):
        checks.append(dict(check=name, ok=bool(ok), detail=detail))
        print(f"{'PASS' if ok else 'FAIL'}  [{args.label}] {name}  {detail}", flush=True)

    before = stored_choice(args.profile)
    state = dict(stored=before)
    proc = None
    try:
        proc, ctx = start(os.path.join(args.install, "program"), args.profile, args.port,
                          str(out / f"soffice-{args.label}.err"))
        seen, desktop = observe(ctx)
        state.update(seen)
        if args.expect_stored:
            check("stored choice", (before is None) if args.expect_stored == "none" else before == args.expect_stored,
                  repr(before))
        if args.need_vi:
            check("Vietnamese UI installed", "vi" in seen["installed"], seen["installed"])
        if args.expect_ui:
            prefix = "Không tên" if args.expect_ui == "vi" else "Untitled"
            check(f"core UI is {args.expect_ui}", seen["ui"] == args.expect_ui and seen["title"].startswith(prefix),
                  f"{seen['ui']}, {seen['title']!r}, effective {seen['effective']!r}")
        if args.set:
            writable = node(ctx, GENERAL, True)
            writable.setPropertyValue("UILocale", args.set)
            writable.commitChanges()
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge closes while the office quits
            pass
        proc.wait(120)
        state["stored_after"] = stored_choice(args.profile)
        if args.set:
            check(f"{args.set} written to the profile", state["stored_after"] == args.set, repr(state["stored_after"]))
    except Exception as error:  # noqa: BLE001
        check("office run", False, f"{type(error).__name__}: {error}")
        if proc is not None and proc.poll() is None:
            proc.kill()
    (out / f"ui-language-{args.label}.json").write_text(
        json.dumps(dict(state=state, checks=checks), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
