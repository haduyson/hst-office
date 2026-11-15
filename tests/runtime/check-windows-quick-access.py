#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the quick access toolbar of an INSTALLED HST Office (hst-ribbon-adaptive-qat.patch; Linux counterpart:
check-quick-access.py).

Own session (tests/runtime/windows-own-session-task.ps1; nothing is typed): per app (HST Writer, Sheets, Slides, Draw)
the six defaults Mới, Mở, Lưu, Hoàn tác, Làm lại, In; 13 more commands set from this UNO client's thread while the window shows (the office
keeps running: the toolbar's configuration listener takes the SolarMutex); the list survives a restart. Evidence:
PrintWindow shots of each window (<out>/<app>-*.bmp) and <out>/results.json.
--keys (console session only, under C:\\hst-test\\console-lock.txt): Alt+4 undoes and Alt+5 redoes text typed into
HST Writer, sent with the gated input to the verified document window only. The KeyTips are positional: Alt+4 undoes
(Hoàn tác) and Alt+5 redoes (Làm lại), because Mới, Mở, Lưu come first.
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
from quick_access_config import MANY, UNDO_KEY, REDO_KEY, WRITER, defaults, set_commands, shown  # noqa: E402
from windows_keytips_keys import VK_ALT, front  # noqa: E402

APPS = {  # app -> (factory, UI configuration module, window title)
    "writer": ("private:factory/swriter", WRITER, "HST Writer"),
    "calc": ("private:factory/scalc", "com.sun.star.sheet.SpreadsheetDocument", "HST Sheets"),
    "impress": ("private:factory/simpress", "com.sun.star.presentation.PresentationDocument", "HST Slides"),
    "draw": ("private:factory/sdraw", "com.sun.star.drawing.DrawingDocument", "HST Draw"),
}
TEXT = "qat"  # typed with the gated input: an API edit does not reach the undo stack
OUT_DIR = [""]  # set by main


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


def type_text(hwnd):
    for char in TEXT:
        wg.chord(ord(char.upper()), target=hwnd, front=False)
        time.sleep(0.2)
    time.sleep(1)


def keys_undo_redo(office, doc, hwnd, res):
    """The 4th and 5th buttons of the default toolbar (Hoàn tác, Làm lại) from the keyboard: Alt, then the digit (the
    KeyTips), and Alt+digit pressed together; the reference suite takes both."""
    for label, together in ((f"Alt, {UNDO_KEY}", False), (f"Alt+{UNDO_KEY}", True)):
        front(hwnd)
        type_text(hwnd)
        for digit, wanted in ((UNDO_KEY, False), (REDO_KEY, True)):
            if together:
                wg.chord(VK_ALT, ord(digit), target=hwnd, front=False)
            else:
                wg.chord(VK_ALT, target=hwnd, front=False)
                time.sleep(0.8)
                wg.screenshot(os.path.join(OUT_DIR[0], f"keytips-{digit}.png"))
                wg.chord(ord(digit), target=hwnd, front=False)
            time.sleep(1.5)
            text = text_of(doc)
            name = "Hoàn tác" if digit == UNDO_KEY else "Làm lại"
            res(f"[writer] Alt{'+' if together else ', '}{digit} runs {name}", (TEXT in text) == wanted, repr(text[-40:]))
        doc.getText().setString("")
    # control: Ctrl+Z undoes the same edit (else the keys or the undo stack are the problem, not the toolbar)
    type_text(hwnd)
    wg.chord(0x11, ord("Z"), target=hwnd, front=False)
    time.sleep(1.5)
    res.note("[writer] Ctrl+Z control", repr(text_of(doc)[-40:]))
    doc.getText().setString("")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2377)
    parser.add_argument("--keys", action="store_true", help="also Alt+4/Alt+5 (console session only)")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    OUT_DIR[0] = args.out
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
            res(f"[{app}] defaults Mới, Mở, Lưu, Hoàn tác, Làm lại, In", shown(office, APPS[app][1]) == defaults(APPS[app][1]),
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
                res("[writer] 13 more commands set from a UNO thread: the office keeps running",
                    alive and len(names) == len(defaults(WRITER)) + len(MANY), {"alive": alive, "commands": len(names)})
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
