# SPDX-License-Identifier: AGPL-3.0-only
"""Open a modified Writer document over UNO and ask to close it, so the "Save Document?" dialog stays up
(run with the bundled Python).

  save-dialog-probe.py <out-dir>

Writes <out-dir>/ready when the close was dispatched; the dialog then waits for the shell's captures.
"""
import pathlib
import sys
import threading
import time

import uno

PORT = 2002


def main():
    out = pathlib.Path(sys.argv[1])
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            rctx = resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        raise SystemExit("cannot connect to soffice")
    smgr = rctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", rctx)
    helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", rctx)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    text = doc.getText()
    text.insertString(text.getEnd(), "Văn bản đã sửa, chưa lưu.", False)
    frame = doc.getCurrentController().getFrame()
    time.sleep(2)
    # the dispatch returns only when the dialog is answered: keep it in a thread
    threading.Thread(target=lambda: helper.executeDispatch(frame, ".uno:CloseDoc", "", 0, ()),
                     daemon=True).start()
    (out / "ready").write_text("1")
    time.sleep(90)


if __name__ == "__main__":
    main()
