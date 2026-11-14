# SPDX-License-Identifier: AGPL-3.0-only
"""Window, dialog and dispatch helpers of check-windows-smoke.py (see there)."""
import os
import subprocess
import threading
import time
import traceback

from windows_smoke_report import ROWS, record

def top_windows(toolkit):
    return [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]


def window_title(window):
    for getter in (lambda w: w.getTitle(), lambda w: w.getAccessibleContext().getAccessibleName()):
        try:
            value = getter(window)
            if value:
                return value
        except Exception:  # noqa: BLE001
            continue
    return ""


SHOT_DIR = None  # set by check-windows-smoke.py --screenshots


def shot(label):
    """Optional full-screen PNG (Windows CI passes --screenshots); never fails the smoke run."""
    if not SHOT_DIR:
        return
    name = "".join(c if c.isalnum() else "_" for c in label)[:40]
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "windows", "capture-screenshot.ps1")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Path", os.path.join(SHOT_DIR, "%d-%s.png" % (len(ROWS), name))],
                   timeout=60, check=False)


def close_dialog(window):
    """End a modal dialog: endExecute when the peer offers XDialog, otherwise press Escape in the foreground window."""
    try:
        window.endExecute()
    except Exception:  # noqa: BLE001
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{ESC}')"],
                       timeout=30, check=False)


def is_new(window, known):
    return all(window != other for other in known)  # pyuno proxies compare by UNO object identity


def pump(toolkit, work, wait_for_window):
    """Run `work` in a thread; close every window that opens meanwhile. Returns (descriptions, error text).

    A description is "title WxH" (pixels); a window larger than the screen work area is reported as OVERSIZE.
    """
    known = top_windows(toolkit)
    state = {"error": ""}

    def target():
        try:
            work()
        except Exception:  # noqa: BLE001
            state["error"] += traceback.format_exc()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    found, deadline = [], time.time() + 40
    area = toolkit.getWorkArea()
    while time.time() < deadline and (thread.is_alive() or (wait_for_window and not found)):
        for window in top_windows(toolkit):
            if is_new(window, known):
                known.append(window)
                time.sleep(4)  # let the dialog lay out (peer size settles), paint and get its title
                try:
                    size = window.getPosSize()
                except Exception:  # noqa: BLE001
                    size = area.__class__(0, 0, 0, 0)
                label = "%s %dx%d" % (window_title(window), size.Width, size.Height)
                if size.Width > area.Width or size.Height > area.Height:
                    label += " OVERSIZE(work area %dx%d)" % (area.Width, area.Height)
                found.append(label)
                shot(label)
                close_dialog(window)
        time.sleep(0.3)
    thread.join(10)
    if thread.is_alive():
        state["error"] += "still blocked after 50 s\n"
    return found, state["error"]


def open_document(ctx, desktop, kind):
    """Open a visible document from a thread: the first-start welcome dialog blocks the load until it is closed."""
    from com.sun.star.beans import PropertyValue
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    box = {}
    flag = PropertyValue()
    flag.Name, flag.Value = "Hidden", False
    titles, error = pump(toolkit, lambda: box.update(doc=desktop.loadComponentFromURL("private:factory/" + kind, "_blank", 0, (flag,))), False)
    record("open %s (windows during load: %s)" % (kind, titles), "doc" in box and not error, error)
    return box.get("doc")


def run_command(ctx, frame, url_text, expect_dialog):
    """Dispatch in a thread; return (new window titles, thread exception text or '')."""
    import uno
    smgr = ctx.ServiceManager
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    transformer = smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = url_text
    _, url = transformer.parseStrict(url)
    dispatch = frame.queryDispatch(url, "_self", 0)
    if dispatch is None:
        return None, "queryDispatch returned None: no handler claims " + url_text
    state = {"error": ""}

    def work():
        try:
            dispatch.dispatch(url, ())
        except Exception:  # noqa: BLE001
            state["error"] = traceback.format_exc()

    titles, error = pump(toolkit, work, wait_for_window=True)
    state["error"] += error
    return titles, state["error"]
