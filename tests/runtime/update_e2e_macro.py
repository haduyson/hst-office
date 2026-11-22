# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# User Python script of the end-to-end update checks (update-e2e-drive.py, scripts/macos/update-e2e-probe.py).
# The driver copies this file into the probe profile's Scripts/python with the ARGS line filled in, then invokes run()
# over UNO. run() schedules, on the office's main thread, the dispatch of org.hst.office.update:Install on the current
# (document) frame: the path of the infobar button and of the menu entry. ARGS:
#   events   JSON-lines file of what happened (office pid, helper spawned/cancelled, questions, quit result)
#   code     directory to import hst_office from instead of the running office's own extension ("" = its own)
#   pretend  release reported to the update check instead of the running one ("" = the real one)
#   answer   "auto": answer the "Cập nhật ngay" question without showing it; "" = the real dialog (clicked by the driver)
#   close_welcome  close the welcome dialog first, as a user would (releases up to 1.0.2 cannot quit while it is open)
#   installer, sha256, to  a local installer that replaces the download (update_install.prepare) for any target
#            release; "" = the published manifest and the file already waiting in the update cache
import json
import os
import sys
import time
import traceback

ARGS = {}


def note(event, **extra):
    extra.update(event=event, t=round(time.time(), 3))
    with open(ARGS["events"], "a", encoding="utf-8") as handle:
        handle.write(json.dumps(extra) + "\n")


def _extension_dir(ctx):
    import uno
    base = uno.fileUrlToSystemPath(ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros("$BRAND_BASE_DIR"))
    share = os.path.join(base, "Resources") if sys.platform == "darwin" else os.path.join(base, "share")
    return os.path.join(share, "extensions", "hst-vietnamese-tools", "python")


def _instrument(update_install, update_launch, update_ui):
    spawn, cancel, ask = update_launch.spawn, update_launch.cancel, update_install._ask

    def spawn_logged(argv, system, *rest, **kw):
        proc = spawn(argv, system, *rest, **kw)
        note("helper-spawned", helper_pid=proc.pid, argv=argv)
        return proc

    def cancel_logged(proc):
        note("helper-cancelled", helper_pid=proc.pid)
        return cancel(proc)

    def ask_logged(ctx, peer, title, text, buttons, *rest, **kw):
        keys = [b[1] for b in buttons]
        note("question", title=title, text=text, buttons=keys)
        answer = "install" if ARGS.get("answer") == "auto" and "install" in keys else ask(ctx, peer, title, text, buttons, *rest, **kw)
        note("answer", answer=answer)
        return answer
    update_launch.spawn, update_launch.cancel, update_install._ask = spawn_logged, cancel_logged, ask_logged
    for name in ("quit_office", "elevate_and_quit"):
        original = getattr(update_launch, name, None)
        if original is None:
            continue

        def logged(*args, _original=original, _name=name, **kw):
            try:
                result = _original(*args, **kw)
            except Exception as exc:
                note(_name, error=repr(exc))
                raise
            note(_name, result=result)
            return result
        setattr(update_launch, name, logged)
    if ARGS.get("installer"):
        def prepare(info, *rest, **kw):
            note("prepare-local", installer=ARGS["installer"])
            return {"release": {"version": ARGS["to"]}, "entry": {"sha256": ARGS["sha256"]}, "path": ARGS["installer"]}
        update_install.prepare = prepare
    if ARGS.get("pretend"):
        info_for = update_ui.release_info_for
        update_ui.release_info_for = lambda ctx: dict(info_for(ctx), release=ARGS["pretend"])


def run(*_):
    import uno
    ctx = uno.getComponentContext()
    if ARGS.get("code"):  # another copy of the code: the handler re-imports what it needs from there
        sys.path.insert(0, ARGS["code"])
        for name in [n for n in sys.modules if n == "hst_office" or n.startswith("hst_office.")]:
            del sys.modules[name]
    elif _extension_dir(ctx) not in sys.path:  # the office's own modules, shared with its jobs and dialogs
        sys.path.append(_extension_dir(ctx))
    from hst_office import update_install, update_launch, update_ui
    note("loaded", pid=os.getpid(), module=update_install.__file__)
    _instrument(update_install, update_launch, update_ui)

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
    def close_welcome_then_go():
        from hst_office import welcome_dialog
        note("welcome", open=welcome_dialog.CURRENT is not None)
        if welcome_dialog.CURRENT is not None:
            welcome_dialog.CURRENT.close()
            update_ui.on_main_thread(ctx, go)  # after the dialog has left its modal loop
        else:
            go()
    update_ui.on_main_thread(ctx, close_welcome_then_go if ARGS.get("close_welcome") else go)
    return "scheduled"


g_exportedScripts = (run,)
