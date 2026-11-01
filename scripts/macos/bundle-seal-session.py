# SPDX-License-Identifier: AGPL-3.0-only
"""One ordinary HST Office session over UNO, for bundle-seal-probe.sh (run with the bundled Python).

    bundle-seal-session.py <port> <log>

Connects to an office started with --accept=socket,host=127.0.0.1,port=<port>;urp; opens a Writer document,
types Vietnamese and English text (the grammar checker loads its Python), runs HST ▸ Kiểm tra cập nhật… and
HST ▸ Văn bản hành chính… (the ND 30 wizard), closes every dialog they open and quits the office. Every step is
logged; exit status 1 only when the office cannot be reached or no Writer document opens.
"""
import sys
import threading
import time

import uno

COMMANDS = ("org.hst.office.update:Check", "org.hst.office.vi:Nd30Wizard")
LOG = open(sys.argv[2], "a", encoding="utf-8")


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, file=LOG, flush=True)


def connect(port):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(120):
        try:
            return resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001 - not listening yet
            time.sleep(1)
    raise RuntimeError("UNO socket did not open in 120 s")


def close_dialogs(toolkit):
    """End every modal dialog of the office (HST dialogs are UNO dialogs whose peer supports endExecute)."""
    closed = 0
    for index in range(toolkit.getTopWindowCount()):
        try:
            toolkit.getTopWindow(index).endExecute()
            closed += 1
        except Exception:  # noqa: BLE001 - a document window, or a window that vanished
            pass
    return closed


def run(ctx, frame, toolkit, command):
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = command
    _ok, url = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx).parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if dispatch is None:
        log("no dispatch for", command)
        return
    errors = []

    def call():
        try:
            dispatch.dispatch(url, ())
        except Exception as error:  # noqa: BLE001 - logged, the session goes on
            errors.append(error)

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    closed = 0
    for _ in range(20):  # the update check fetches over the network before it shows its result
        time.sleep(1)
        closed += close_dialogs(toolkit)
        if not worker.is_alive() and closed:
            break
    worker.join(10)
    log(command, "dialogs closed:", closed, "returned:", not worker.is_alive(), "errors:", errors)


def main():
    ctx = connect(int(sys.argv[1]))
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    close_dialogs(toolkit)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    if doc is None:
        log("no Writer document")
        return 1
    doc.Text.setString("Kiểm tra thử văn bản tiếng Việt. This is is a sentence with a a repeated word.\n")
    log("Writer document open")
    time.sleep(5)  # background spelling and grammar checking
    frame = doc.CurrentController.Frame
    for command in COMMANDS:
        run(ctx, frame, toolkit, command)
    doc.setModified(False)
    close_dialogs(toolkit)
    try:
        desktop.terminate()
        log("terminate requested")
    except Exception as error:  # noqa: BLE001 - the bridge closes while the office quits
        log("terminate:", error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
