# SPDX-License-Identifier: AGPL-3.0-only
"""Drive "Cập nhật ngay" end to end inside a GUI HST Office on macOS (evidence probe, CI only).

update-e2e-probe.py --app <bundle> --profile <dir> --out <json> --pipe <name> [--code <python dir>] [--pretend R]
                    [--document <file>] [--watch S] [--race]
Run with a bundled office Python (URE_BOOTSTRAP / PYTHONPATH of a separate driver copy of the app). The office starts
like a user's (LaunchServices `open`, GUI) with a UNO pipe and a document. A user Python script placed in the probe
profile dispatches org.hst.office.update:Install on the document's frame from the office's main thread, as the infobar
button does: the published signed manifest is fetched, the installer already placed in ~/Library/Caches/HSTOffice/update
is verified and reused (no download), and the real "Cập nhật ngay" question is answered by a System Events click.
--code makes the office import hst_office from that directory (this checkout) instead of its own bundle; --pretend
reports that release to the update check (so that an up-to-date build is offered the published release).
The driver then watches the office process, the helper's update.log, the bundle on disk and the relaunched office.
--race opens the app again (LaunchServices, like a click on its Dock icon) as soon as the office has quit, while the
helper still works: the helper must not replace the bundle under that copy."""
import argparse
import json
import os
import plistlib
import subprocess
import time

MACRO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update-e2e-probe-macro.py")
PLACEHOLDER = "ARGS = {}  # filled in by update-e2e-probe.py"

CLICK = r'''
on run argv
  set wanted to item 1 of argv
  tell application "System Events"
    set p to first process whose unix id is (item 2 of argv as integer)
    set frontmost of p to true
    delay 0.3
    repeat with w in windows of p
      repeat with b in buttons of w
        if name of b is wanted then
          click b
          return "clicked " & wanted & " in " & (name of w)
        end if
      end repeat
    end repeat
  end tell
  return "none"
end run
'''


def version(app):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as handle:
            data = plistlib.load(handle)
        return "%s (%s)" % (data.get("CFBundleShortVersionString"), data.get("CFBundleVersion"))
    except OSError:
        return None


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def office_processes():
    out = subprocess.run(["pgrep", "-lf", "MacOS/soffice"], capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def clean_env():
    """`open` passes the caller's environment on: without this the office would boot from the driver copy's URE."""
    drop = ("URE_BOOTSTRAP", "PYTHONPATH", "PYTHONHOME", "PYTHONDONTWRITEBYTECODE")
    return {k: v for k, v in os.environ.items() if k not in drop}


def click(label, pid):
    result = subprocess.run(["osascript", "-", label, str(pid)], input=CLICK, capture_output=True, text=True, timeout=30)
    return (result.stdout + result.stderr).strip()


def events_of(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    p = argparse.ArgumentParser()
    for name in ("app", "profile", "out", "pipe"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--code", default="")
    p.add_argument("--pretend", default="")
    p.add_argument("--document", default="")
    p.add_argument("--watch", type=int, default=300)
    p.add_argument("--close-welcome", action="store_true")
    p.add_argument("--race", action="store_true")
    a = p.parse_args()
    import uno
    report = {"app": a.app, "version_before": version(a.app), "inode_before": os.stat(a.app).st_ino,
              "code": a.code or "bundle", "pretend": a.pretend}
    events = a.out + ".events.jsonl"
    open(events, "w").close()
    scripts = os.path.join(a.profile, "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    with open(MACRO, encoding="utf-8") as handle:
        macro = handle.read()
    assert PLACEHOLDER in macro
    with open(os.path.join(scripts, "hst_update_e2e.py"), "w", encoding="utf-8") as handle:
        handle.write(macro.replace(PLACEHOLDER, "ARGS = %r" % {"events": events, "code": a.code, "pretend": a.pretend}, 1))
    argv = ["open", "-n", "-a", a.app, "--args", "-env:UserInstallation=" + uno.systemPathToFileUrl(a.profile),
            "--norestore", "--nologo", "--accept=pipe,name=%s;urp;" % a.pipe] + ([a.document] if a.document else [])
    subprocess.run(argv, check=True, env=clean_env())
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(240):
        try:
            ctx = resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % a.pipe)
            break
        except Exception:  # noqa: BLE001 - not listening yet
            time.sleep(1)
    if ctx is None:
        raise SystemExit("UNO pipe did not open; offices: %s" % office_processes())
    time.sleep(20)  # let the document window and the start-up jobs settle
    if a.close_welcome:  # releases up to 1.0.2: a modal welcome dialog left open makes the quit fail at once
        time.sleep(10)
        report_close = click("Đóng", int(subprocess.run(["pgrep", "-n", "-f", a.app + "/Contents/MacOS/soffice"],
                                                         capture_output=True, text=True).stdout.split()[0]))
        print("close welcome:", report_close, flush=True)
        time.sleep(3)
    factory = ctx.ServiceManager.createInstanceWithContext("com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
    script = factory.createScriptProvider("").getScript("vnd.sun.star.script:hst_update_e2e.py$run?language=Python&location=user")
    report["invoke"] = str(script.invoke((), (), ())[0])
    time.sleep(3)
    pid = next(e["pid"] for e in events_of(events) if e["event"] == "loaded")
    report["office_pid"], report["clicks"] = pid, []
    started, exited, answered = time.monotonic(), None, False
    while time.monotonic() - started < a.watch:
        if not answered and any(e["event"] == "question" for e in events_of(events)):
            time.sleep(2)
            for label in ("Cập nhật ngay", "Update now"):
                outcome = click(label, pid)
                report["clicks"].append(outcome)
                if outcome.startswith("clicked"):
                    answered = True
                    break
        if exited is None and not alive(pid):
            exited = round(time.monotonic() - started, 1)
            if a.race:
                subprocess.run(["open", "-a", a.app], check=False, env=clean_env())
                report["race_opened_after_s"] = round(time.monotonic() - started, 1)
                report["race_processes"] = office_processes()
        # the helper had 90 s after the exit to swap and relaunch; with --race it may first wait 60 s for that copy
        if exited is not None and time.monotonic() - started > exited + (150 if a.race else 90):
            break
        time.sleep(1)
    subprocess.run(["screencapture", "-x", a.out + ".png"], check=False)
    report["office_exited_after_s"] = exited
    report["office_alive_at_end"] = alive(pid)
    report["events"] = events_of(events)
    report["version_after"] = version(a.app)
    report["inode_after"] = os.stat(a.app).st_ino if os.path.exists(a.app) else None
    report["office_processes_after"] = office_processes()
    names = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every window of every process '
                            'whose name is "soffice"'], capture_output=True, text=True, timeout=30)
    report["windows_after"] = (names.stdout + names.stderr).strip()  # the relaunched office: reopened document?
    log = os.path.expanduser("~/Library/Caches/HSTOffice/update/update.log")
    report["update_log"] = open(log, encoding="utf-8", errors="replace").read().splitlines()[-40:] if os.path.exists(log) else None
    with open(a.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
