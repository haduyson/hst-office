# SPDX-License-Identifier: AGPL-3.0-only
"""User Python macro of the macOS "Cập nhật ngay" probe (update-e2e-probe.py copies it into the probe profile).

run() logs the updater's helper spawn, question and quit to ARGS["events"] and dispatches org.hst.office.update:Install
on the current frame from the office's main thread, as the infobar button does."""
import json
import os
import sys
import time
import traceback

ARGS = {}  # filled in by update-e2e-probe.py


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
