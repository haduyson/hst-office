# SPDX-License-Identifier: AGPL-3.0-only
"""Run the "Cập nhật ngay" install step of the app's OWN shipped code inside a GUI office on macOS (evidence probe).

update-apply-probe.py --app <bundle> --profile <dir> --dmg <installer> --release-from R --release-to R --out <json>
Run with a bundled office Python (URE_BOOTSTRAP / PYTHONPATH of a separate driver copy of the app). The office is
started like a user's (LaunchServices `open`, GUI, not headless) with a UNO pipe. A user Python script is placed in the
probe profile and invoked over UNO: it imports hst_office from the running bundle and schedules
update_install.launch_and_quit(ctx, result, info) on the office's main thread, exactly as the "Cập nhật ngay" answer
does, with the verified installer already in ~/Library/Caches/HSTOffice/update. The driver then watches the soffice
process, the helper's update.log and the bundle version."""
import argparse
import json
import os
import plistlib
import subprocess
import time

SCRIPT = r'''
import json, os, sys, traceback
ARGS = json.loads(%r)


def note(event, **extra):
    extra.update(event=event, t=round(__import__("time").time(), 3))
    with open(ARGS["events"], "a") as handle:
        handle.write(json.dumps(extra) + "\n")


def run(*_):
    import uno
    ctx = uno.getComponentContext()
    base = uno.fileUrlToSystemPath(ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros("$BRAND_BASE_DIR"))
    python = os.path.join(base, "Resources", "extensions", "hst-vietnamese-tools", "python")
    if python not in sys.path:
        sys.path.insert(0, python)
    from hst_office import update_install, update_launch, update_ui
    note("loaded", pid=os.getpid(), module=update_install.__file__, quit_office=hasattr(update_launch, "quit_office"))
    spawn, cancel = update_launch.spawn, update_launch.cancel

    def spawn_logged(argv, system, *rest, **kw):
        proc = spawn(argv, system, *rest, **kw)
        note("helper-spawned", helper_pid=proc.pid, argv=argv)
        return proc

    def cancel_logged(proc):
        note("helper-cancelled", helper_pid=proc.pid)  # beta.5: Desktop.terminate() returned False
        return cancel(proc)
    update_launch.spawn, update_launch.cancel = spawn_logged, cancel_logged
    result = {"path": ARGS["dmg"], "entry": {"sha256": ARGS["sha256"]}, "release": {"version": ARGS["to"]}}
    info = {"release": ARGS["from"], "test_mode": False}

    def go():
        note("launch_and_quit-start")
        try:
            update_install.launch_and_quit(ctx, result, info)
            note("launch_and_quit-returned")
        except Exception:
            note("launch_and_quit-error", trace=traceback.format_exc())
    update_ui.on_main_thread(ctx, go)
    return "scheduled"
'''


def version(app):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as handle:
            return plistlib.load(handle).get("CFBundleShortVersionString")
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


def main():
    p = argparse.ArgumentParser()
    for name in ("app", "profile", "dmg", "sha256", "release-from", "release-to", "out", "pipe"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--watch", type=int, default=240)
    a = p.parse_args()
    import uno
    report = {"app": a.app, "version_before": version(a.app), "from": a.release_from, "to": a.release_to}
    events = a.out + ".events.jsonl"
    open(events, "w").close()
    scripts = os.path.join(a.profile, "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    args = {"dmg": a.dmg, "sha256": a.sha256, "to": a.release_to, "from": a.release_from, "events": events}
    with open(os.path.join(scripts, "hst_update_probe.py"), "w") as handle:
        handle.write(SCRIPT % json.dumps(args))
    accept = "--accept=pipe,name=%s;urp;" % a.pipe
    subprocess.run(["open", "-n", "-a", a.app, "--args", "-env:UserInstallation=" + uno.systemPathToFileUrl(a.profile),
                    "--norestore", "--nologo", accept], check=True, env=clean_env())
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
    time.sleep(15)  # let the Start Center and the start-up jobs settle
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    report["top_windows_before"] = toolkit.getTopWindowCount()
    factory = ctx.ServiceManager.createInstanceWithContext("com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
    script = factory.createScriptProvider("").getScript("vnd.sun.star.script:hst_update_probe.py$run?language=Python&location=user")
    report["invoke"] = str(script.invoke((), (), ())[0])
    time.sleep(3)
    loaded = [json.loads(line) for line in open(events) if line.strip()]
    pid = next(e["pid"] for e in loaded if e["event"] == "loaded")
    report["office_pid"] = pid
    started, exited = time.monotonic(), None
    while time.monotonic() - started < a.watch:
        if exited is None and not alive(pid):
            exited = round(time.monotonic() - started, 1)
        if exited is not None and time.monotonic() - started > exited + 60:
            break  # helper had 60 s after the exit to swap and relaunch
        time.sleep(1)
    report["office_exited_after_s"] = exited
    report["office_alive_at_end"] = alive(pid)
    if report["office_alive_at_end"]:
        try:
            report["top_windows_after"] = toolkit.getTopWindowCount()  # 0: running with no window (Dock only)
        except Exception as exc:  # noqa: BLE001
            report["top_windows_after"] = repr(exc)
    report["events"] = [json.loads(line) for line in open(events) if line.strip()]
    report["version_after"] = version(a.app)
    report["office_processes_after"] = office_processes()
    log = os.path.expanduser("~/Library/Caches/HSTOffice/update/update.log")
    report["update_log"] = open(log).read().splitlines()[-40:] if os.path.exists(log) else None
    with open(a.out, "w") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
