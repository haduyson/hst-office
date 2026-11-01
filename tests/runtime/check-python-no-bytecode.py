# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check that the office writes no Python bytecode caches into its installation (hst-python-no-bytecode.patch).

    python3 tests/runtime/check-python-no-bytecode.py [--instdir upstream/libreoffice/instdir] [--out tests/output/python-no-bytecode]

Run as root; the office runs headless as the build user on a hard-linked instdir copy whose folders the build user
owns, so Python could write caches there. The copy starts without any __pycache__ folder; one session loads the
pyuno loader and the HST extension's Python (a Writer document, the state of HST ▸ Kiểm tra cập nhật… and of the
Văn bản hành chính wizard) and checks:
  - the HST Python protocol handler answered (Python really ran);
  - a Python script run by the office sees sys.flags.dont_write_bytecode and PYTHONDONTWRITEBYTECODE=1, and a
    process it starts inherits the variable (as the update helper and the USB token worker do);
  - after the office quit, the copy has no .pyc file and no __pycache__ folder.
Exit status 1 when a check fails. The original instdir is never written.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
COMMANDS = ("org.hst.office.update:Check", "org.hst.office.vi:Nd30Wizard")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append(ok)
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def caches(tree):
    """Every __pycache__ folder and .pyc file below `tree`."""
    found = []
    for root, dirs, files in os.walk(tree):
        found += [os.path.join(root, d) for d in dirs if d == "__pycache__"]
        found += [os.path.join(root, f) for f in files if f.endswith((".pyc", ".pyo"))]
    return found


def fresh_copy(instdir, copy):
    shutil.rmtree(copy, ignore_errors=True)
    subprocess.run(["cp", "-al", os.path.abspath(instdir), copy], check=True)
    for path in caches(copy):  # unlinks the copy's entries only; the original's caches stay
        if os.path.isdir(path):
            shutil.rmtree(path)
    shared = os.path.join(copy, "share", "uno_packages")  # written at start: a real copy, never the links
    shutil.rmtree(shared, ignore_errors=True)
    subprocess.run(["cp", "-a", os.path.join(os.path.abspath(instdir), "share", "uno_packages"), shared], check=True)
    if os.geteuid() == 0:  # writable folders for the build user: the office could write caches if it tried
        subprocess.run(["find", copy, "-type", "d", "-exec", "chown", BUILD_USER, "{}", "+"], check=True)
        subprocess.run(["chown", "-R", BUILD_USER, shared], check=True)


SCRIPT = """import os, subprocess, sys
def probe(*args):
    child = subprocess.run(["/bin/sh", "-c", "printf %s \\"$PYTHONDONTWRITEBYTECODE\\""], capture_output=True, text=True).stdout
    return "%d %s %s" % (sys.flags.dont_write_bytecode, os.environ.get("PYTHONDONTWRITEBYTECODE"), child)
"""


def office_python(ctx, profile):
    """sys.flags.dont_write_bytecode, the variable and a child's view of it, from a user Python script."""
    folder = os.path.join(profile, "user", "Scripts", "python")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "hst_bytecode_probe.py"), "w", encoding="utf-8") as handle:
        handle.write(SCRIPT)
    factory = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
    script = factory.createScriptProvider("").getScript(
        "vnd.sun.star.script:hst_bytecode_probe.py$probe?language=Python&location=user")
    return script.invoke((), (), ())[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "python-no-bytecode"))
    ap.add_argument("--port", type=int, default=22871)
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    sys.path.insert(0, program)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    sys.dont_write_bytecode = True  # this probe's own imports (uno.py of the original instdir)
    import uno
    policy = load_file("check_update_policy", os.path.join(HERE, "check-update-policy.py"))

    copy = os.path.join(out, "instdir")
    fresh_copy(args.instdir, copy)
    record("copy starts without caches", not caches(copy), caches(copy)[:3])
    work = os.path.join(out, "run")
    proc, ctx = policy.start_office(os.path.join(copy, "program", "soffice"), work, args.port)
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        hidden = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        hidden.Name, hidden.Value = "Hidden", True
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (hidden,))
        doc.Text.setString("Kiểm tra thử văn bản tiếng Việt. This is is a test.\n")
        frame = doc.CurrentController.Frame
        states = {command: policy.command_enabled(ctx, frame, command) for command in COMMANDS}
        record("HST Python protocol handler answered", any(state is not None for state in states.values()), states)
        seen = office_python(ctx, os.path.join(work, "profile"))
        record("office Python and its child processes write no bytecode", seen == "1 1 1", seen)
        time.sleep(3)
        doc.close(True)
    except Exception as error:  # noqa: BLE001 - report instead of hanging
        record("session ran", False, repr(error))
    finally:
        policy.stop_office(proc, ctx, work)
    left = caches(copy)
    record("no Python caches in the installation after the session", not left, left[:5])
    shutil.rmtree(copy, ignore_errors=True)
    print("python no-bytecode: %d failed check(s)" % ROWS.count(False))
    return 1 if False in ROWS else 0


if __name__ == "__main__":
    sys.exit(main())
