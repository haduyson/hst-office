#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of Alt+\\ (Chuyển TeX ⇄ công thức) in a visible HST Writer: X11 with xdotool, or Windows.

Usage, Linux (as hstbuild inside tests/runtime/no-hst-telemetry.sh, on a display of your own):
    DISPLAY=:87 python3 tests/runtime/check-tex-toggle-key.py --soffice PATH [--out DIR] [--port 2398]
Windows (the image's own python, in the console session; the window is brought forward as activate() in
check-backstage-print-close.py does, and the keys are Alt + the US-layout backslash key, VK_OEM_5):
    <image>\\program\\python.exe tests\\runtime\\check-tex-toggle-key.py --soffice <image>\\program\\soffice.exe

A new Writer document holds "Thử $x^2+1$ và $\\frac{1}{2}$ nhé". Alt+\\ is typed into its window: both spans become
formulas, no backslash is typed, and the end-of-run message is closed with Enter. The office quits on its main thread.
Exit 1 when a check fails.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402
import tex_toggle_check_helpers as base  # noqa: E402
TEXT = "Thử $x^2+1$ và $\\frac{1}{2}$ nhé"


class VisibleOffice:
    """An office with a window (not headless), own profile, fixed port."""

    def __init__(self, soffice, workdir, port):
        uno = headless_office.import_uno(soffice)
        profile = uno.systemPathToFileUrl(os.path.join(workdir, "profile"))
        self.proc = subprocess.Popen([soffice, "--norestore", "--nologo", "--writer",
                                      "-env:UserInstallation=" + profile,
                                      f"--accept=socket,host=127.0.0.1,port={port};urp;"])
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(240):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - the office is still starting
                time.sleep(0.5)
        else:
            raise SystemExit("office did not start")
        self.desktop = self.service("com.sun.star.frame.Desktop")

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)


def xdotool(*args):
    return subprocess.run(("xdotool",) + args, capture_output=True, text=True).stdout.strip()


class Keyboard:
    """Find the Writer window, bring it forward, type Alt+\\ and Enter: xdotool on X11, keybd_event on Windows."""

    def window(self):
        if sys.platform != "win32":
            found = xdotool("search", "--onlyvisible", "--name", "Writer").split()
            return found[-1] if found else None
        import ctypes
        user32, found = ctypes.windll.user32, []

        def visit(hwnd, _):
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, 512)
            if user32.IsWindowVisible(hwnd) and "Writer" in title.value:
                found.append(hwnd)
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(visit), 0)
        return found[0] if found else None

    def activate(self, window):
        if sys.platform != "win32":
            xdotool("windowactivate", "--sync", window)
            return True
        import ctypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        for _ in range(5):  # a lone Shift gives this process the last input; Alt would show the key tips
            self.press("shift")
            front = user32.GetForegroundWindow()
            theirs = user32.GetWindowThreadProcessId(ctypes.c_void_p(front), None) if front else 0
            mine = kernel32.GetCurrentThreadId()
            attached = bool(theirs) and theirs != mine and user32.AttachThreadInput(mine, theirs, True)
            try:
                user32.BringWindowToTop(ctypes.c_void_p(window))
                user32.SetForegroundWindow(ctypes.c_void_p(window))
            finally:
                if attached:
                    user32.AttachThreadInput(mine, theirs, False)
            time.sleep(1)
            if (user32.GetForegroundWindow() or 0) & 0xFFFFFFFF == int(window) & 0xFFFFFFFF:
                return True
        return False

    def press(self, combo):
        if sys.platform != "win32":
            xdotool("key", "--clearmodifiers", combo)
            return
        import ctypes
        codes = {"alt+backslash": (0x12, 0xDC), "Return": (0x0D,), "shift": (0x10,)}[combo]  # VK_MENU, VK_OEM_5…
        for code in codes:
            ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        for code in reversed(codes):
            ctypes.windll.user32.keybd_event(code, 0, 2, 0)


def objects(doc, timeout=20):
    """Number of embedded objects, read off the main thread (the end-of-run message may be up); None on timeout."""
    box = {}
    thread = threading.Thread(target=lambda: box.update(n=len(doc.getEmbeddedObjects().getElementNames())),
                              daemon=True)
    thread.start()
    thread.join(timeout)
    return box.get("n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "tex-toggle-key"))
    parser.add_argument("--port", type=int, default=2398)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    office = VisibleOffice(args.soffice, out, args.port)
    try:
        doc = None
        for _ in range(60):
            doc = office.desktop.getCurrentComponent()
            if doc is not None and doc.supportsService("com.sun.star.text.TextDocument"):
                break
            time.sleep(1)
        time.sleep(5)  # the view and its key handler are set up after the document
        base.on_main(office, lambda: doc.getText().setString(TEXT))
        keyboard = Keyboard()
        window = keyboard.window()
        base.record("Writer window found and in front", window is not None and keyboard.activate(window), window)
        time.sleep(1)
        keyboard.press("alt+backslash")
        time.sleep(4)
        count = objects(doc)
        keyboard.press("Return")  # the end-of-run message
        time.sleep(1)
        if count is None:
            count = objects(doc)
        base.record("Alt+\\ turned both spans into formulas", count == 2, count)
        text = base.on_main(office, lambda: doc.getText().getString())
        base.record("no backslash typed", "\\" not in text and "$" not in text, repr(text))
        base.on_main(office, lambda: doc.setModified(False))
    finally:
        base.quit_office(office)
    failed = [name for name, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
