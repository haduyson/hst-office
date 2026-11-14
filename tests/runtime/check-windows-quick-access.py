#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the quick access toolbar of an INSTALLED HST Office (hst-ribbon-adaptive-qat.patch; Linux counterpart:
check-quick-access.py).

Own session (tests/runtime/windows-own-session-task.ps1; nothing is typed): per app (HST Writer, Sheets, Slides, Draw)
the defaults Lưu, Hoàn tác, Làm lại; 16 commands set from this UNO client's thread while the window shows (the office
keeps running: the toolbar's configuration listener takes the SolarMutex); the list survives a restart. Evidence:
PrintWindow shots of each window (<out>/<app>-*.bmp) and <out>/results.json.
--keys (console session only, under C:\\hst-test\\console-lock.txt): Alt+2 undoes and Alt+3 redoes text typed into
HST Writer, sent with the gated input to the verified document window only.
Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-quick-access.py --install DIR --out DIR [--keys]
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
from quick_access_config import DEFAULTS, MANY, WRITER, set_commands, shown  # noqa: E402
from windows_keytips_keys import VK_ALT, front  # noqa: E402

APPS = {  # app -> (factory, UI configuration module, window title)
    "writer": ("private:factory/swriter", WRITER, "HST Writer"),
    "calc": ("private:factory/scalc", "com.sun.star.sheet.SpreadsheetDocument", "HST Sheets"),
    "impress": ("private:factory/simpress", "com.sun.star.presentation.PresentationDocument", "HST Slides"),
    "draw": ("private:factory/sdraw", "com.sun.star.drawing.DrawingDocument", "HST Draw"),
}
TEXT = "Kiểm tra thanh truy cập nhanh"


def window_shot(hwnd, path):
    """BMP of one top-level window through PrintWindow (works in a disconnected session; only this window)."""
    import ctypes
    import struct
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, rect)
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    screen = user32.GetDC(hwnd)
    memory, bitmap = gdi32.CreateCompatibleDC(screen), gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(memory, bitmap)
    user32.PrintWindow(hwnd, memory, 2)  # PW_RENDERFULLCONTENT
    header = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, pixels, header, 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(hwnd, screen)
    with open(path, "wb") as out:
        out.write(b"BM" + struct.pack("<IHHI", 54 + len(pixels.raw), 0, 0, 54) + header + pixels.raw)


def open_app(office, app, out):
    """(document, hwnd of its window) for a new document of `app`; hwnd is None when no window appeared."""
    doc = office.load(APPS[app][0])
    time.sleep(5)
    wg.dismiss_startup(office, os.path.join(out, f"{app}-startup.png"), timeout=8, settle=2)
    window = wg.find_window(lambda title: APPS[app][2] in title, timeout=30)
    return doc, (window[0] if window else None)


def text_of(doc):
    return doc.getText().getString()


def keys_undo_redo(office, doc, hwnd, res):
    """Alt+2 (Hoàn tác) and Alt+3 (Làm lại), the 2nd and 3rd buttons of the default toolbar."""
    doc.getText().insertString(doc.getText().getEnd(), TEXT, False)  # an undoable API edit
    time.sleep(1)
    front(hwnd)
    wg.chord(VK_ALT, ord("2"), target=hwnd, front=False)
    time.sleep(1.5)
    undone = text_of(doc)
    res("[writer] Alt+2 runs Hoàn tác", TEXT not in undone, repr(undone[:60]))
    wg.chord(VK_ALT, ord("3"), target=hwnd, front=False)
    time.sleep(1.5)
    redone = text_of(doc)
    res("[writer] Alt+3 runs Làm lại", TEXT in redone, repr(redone[:60]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2377)
    parser.add_argument("--keys", action="store_true", help="also Alt+2/Alt+3 (console session only)")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(15)
        office.ctx = office._connect()  # the first start of a new image restarts itself after the extension sync
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        for app in APPS:
            doc, hwnd = open_app(office, app, args.out)
            if not res(f"[{app}] window found", bool(hwnd), APPS[app][2]):
                continue
            window_shot(hwnd, os.path.join(args.out, f"{app}-defaults.bmp"))
            res(f"[{app}] defaults Lưu, Hoàn tác, Làm lại", shown(office, APPS[app][1]) == DEFAULTS,
                shown(office, APPS[app][1]))
            if app == "writer" and args.keys:
                try:
                    keys_undo_redo(office, doc, hwnd, res)
                except wg.BlockedInput as error:
                    res("[writer] keys reached the document", False, repr(error))
            if app == "writer":
                set_commands(office, WRITER, MANY)
                time.sleep(4)
                names = shown(office, WRITER)
                alive = office.proc.poll() is None
                res("[writer] 16 commands set from a UNO thread: the office keeps running",
                    alive and len(names) == len(DEFAULTS) + len(MANY), {"alive": alive, "commands": len(names)})
                if alive:
                    window_shot(hwnd, os.path.join(args.out, "writer-16-commands.bmp"))
            if office.proc.poll() is None:
                doc.setModified(False)
                doc.close(True)
        office.stop()
        office.start(fresh=False)
        time.sleep(10)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, "restart-startup.png"))
        doc, hwnd = open_app(office, "writer", args.out)
        names = shown(office, WRITER)
        res("[writer] the list survives a restart", names[-1:] == MANY[-1:], names)
        if hwnd:
            window_shot(hwnd, os.path.join(args.out, "writer-after-restart.bmp"))
    finally:
        office.stop()
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
