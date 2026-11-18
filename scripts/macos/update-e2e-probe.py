# SPDX-License-Identifier: AGPL-3.0-only
"""Drive "Cập nhật ngay" end to end inside a GUI HST Office on macOS (evidence probe, CI only).

update-e2e-probe.py --app <bundle> --profile <dir> --out <json> --pipe <name> [--code <python dir>] [--pretend R]
                    [--document <file>] [--watch S]
Run with a bundled office Python (URE_BOOTSTRAP / PYTHONPATH of a separate driver copy of the app). The office starts
like a user's (LaunchServices `open`, GUI) with a UNO pipe and a document. A user Python script placed in the probe
profile dispatches org.hst.office.update:Install on the document's frame from the office's main thread, as the infobar
button does: the published signed manifest is fetched, the installer already placed in ~/Library/Caches/HSTOffice/update
is verified and reused (no download), and the real "Cập nhật ngay" question is answered by a System Events click.
--code makes the office import hst_office from that directory (this checkout) instead of its own bundle; --pretend
reports that release to the update check (so that an up-to-date build is offered the published release).
The driver then watches the office process, the helper's update.log, the bundle on disk and the relaunched office."""
import argparse
import json
import os
import plistlib
import subprocess
import time

SCRIPT = r'''
import json, os, sys, time, traceback
ARGS = json.loads(%r)


def note(event, **extra):
    extra.update(event=event, t=round(time.time(), 3))
    with open(ARGS["events"], "a") as handle:
        handle.write(json.dumps(extra) + "\n")


def run(*_):
    import uno
    ctx = uno.getComponentContext()
    base = uno.fileUrlToSystemPath(ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros("$BRAND_BASE_DIR"))
    python = ARGS["code"] or os.path.join(base, "Resources", "extensions", "hst-vietnamese-tools", "python")
    sys.path.insert(0, python)
    for name in [n for n in sys.modules if n == "hst_office" or n.startswith("hst_office.")]:
        del sys.modules[name]  # the office may have loaded its own copy already
    from hst_office import update_install, update_launch, update_ui
    note("loaded", pid=os.getpid(), module=update_install.__file__)
    spawn, cancel, ask = update_launch.spawn, update_launch.cancel, update_install._ask

    def spawn_logged(argv, system, *rest, **kw):
        proc = spawn(argv, system, *rest, **kw)
        note("helper-spawned", helper_pid=proc.pid, argv=argv)
        return proc

    def cancel_logged(proc):
        note("helper-cancelled", helper_pid=proc.pid)
        return cancel(proc)

    def ask_logged(ctx, peer, title, text, buttons, *rest, **kw):
        note("question", title=title, text=text, buttons=[b[1] for b in buttons])
        answer = ask(ctx, peer, title, text, buttons, *rest, **kw)
        note("answer", answer=answer)
        return answer
    update_launch.spawn, update_launch.cancel, update_install._ask = spawn_logged, cancel_logged, ask_logged
    if hasattr(update_launch, "quit_office"):
        quit_office = update_launch.quit_office

        def quit_logged(ctx):
            closing = quit_office(ctx)
            note("quit_office", closing=closing)
            return closing
        update_launch.quit_office = quit_logged
    if ARGS["pretend"]:
        info_for = update_ui.release_info_for
        update_install.ui.release_info_for = lambda ctx: dict(info_for(ctx), release=ARGS["pretend"])

    def go():
        try:
            desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            frame = desktop.getCurrentFrame()
            url = uno.createUnoStruct("com.sun.star.util.URL")
            url.Complete = "org.hst.office.update:Install"
            url = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx).parseStrict(url)[1]
            dispatch = frame.queryDispatch(url, "_self", 0)
            note("dispatch", frame=frame.getTitle(), found=dispatch is not None)
            dispatch.dispatch(url, ())
            note("dispatch-returned")
        except Exception:
            note("dispatch-error", trace=traceback.format_exc())
    update_ui.on_main_thread(ctx, go)
    return "scheduled"
'''

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
    a = p.parse_args()
    import uno
    report = {"app": a.app, "version_before": version(a.app), "inode_before": os.stat(a.app).st_ino,
              "code": a.code or "bundle", "pretend": a.pretend}
    events = a.out + ".events.jsonl"
    open(events, "w").close()
    scripts = os.path.join(a.profile, "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    with open(os.path.join(scripts, "hst_update_e2e.py"), "w") as handle:
        handle.write(SCRIPT % json.dumps({"events": events, "code": a.code, "pretend": a.pretend}))
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
        if exited is not None and time.monotonic() - started > exited + 90:
            break  # the helper had 90 s after the exit to swap and relaunch
        time.sleep(1)
    subprocess.run(["screencapture", "-x", a.out + ".png"], check=False)
    report["office_exited_after_s"] = exited
    report["office_alive_at_end"] = alive(pid)
    report["events"] = events_of(events)
    report["version_after"] = version(a.app)
    report["inode_after"] = os.stat(a.app).st_ino if os.path.exists(a.app) else None
    report["office_processes_after"] = office_processes()
    log = os.path.expanduser("~/Library/Caches/HSTOffice/update/update.log")
    report["update_log"] = open(log, encoding="utf-8", errors="replace").read().splitlines()[-40:] if os.path.exists(log) else None
    with open(a.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
