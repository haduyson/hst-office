#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""KeyTips and shortcuts of the familiar office suite on Windows with real key presses (the Windows key matrix).

Usage (console session, under C:\\hst-test\\console-lock.txt; with the office's own python.exe):
  "<install>\\program\\python.exe" tests/runtime/check-windows-keytips-office-parity.py --install DIR --out DIR
Opens a new document per app in an office it starts itself, and sends every key with the gated input of windows_gui
to that document's verified window only. Checks: Alt shows the KeyTips (screenshot), Alt, R, C adds a comment (Writer),
Alt, A, S, A sorts (Sheets), Alt, N, S, I and Alt, H, I add a slide (Slides), Ctrl+Alt+F footnote, Ctrl+Shift+E track
changes, Ctrl+5 strikethrough, Ctrl+9 hide row, Ctrl+T font dialog (Slides). Evidence: <out>/results.json and PNGs.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402

VK_ALT, VK_CTRL, VK_SHIFT, VK_ESC = 0x12, 0x11, 0x10, 0x1B
FACTORY = {"writer": "private:factory/swriter", "calc": "private:factory/scalc", "impress": "private:factory/simpress"}
TITLE = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides"}


def letters(hwnd, word):
    for char in word:
        wg.chord(ord(char), target=hwnd, front=False)
        time.sleep(0.5)
    time.sleep(1.0)


def front(hwnd):
    """The document window in front, with no KeyTips left open (bringing it forward may press Alt itself)."""
    wg.foreground(hwnd)
    time.sleep(0.6)
    esc(hwnd, 2)


def alt_tip(hwnd, word):
    front(hwnd)
    wg.chord(VK_ALT, target=hwnd, front=False)
    time.sleep(0.8)
    letters(hwnd, word)


def esc(hwnd, times=2):
    for _ in range(times):
        wg.chord(VK_ESC, target=hwnd, front=False)
        time.sleep(0.3)


def annotations(doc):
    enum = doc.TextFields.createEnumeration()
    count = 0
    while enum.hasMoreElements():
        count += enum.nextElement().supportsService("com.sun.star.text.textfield.Annotation")
    return count


def writer(office, doc, hwnd, res, out):
    # Alt+N straight to Chèn (no Alt release in between), then Esc twice
    front(hwnd)
    wg.chord(VK_ALT, ord("N"), target=hwnd, front=False)
    time.sleep(1.0)
    wg.screenshot(os.path.join(out, "writer-3-alt-n.png"))
    esc(hwnd)
    res("[writer] Alt+N leaves the document text alone", doc.Text.getString() == "", repr(doc.Text.getString()))
    doc.Text.setString("parity")
    before = annotations(doc)
    alt_tip(hwnd, "RC")
    time.sleep(1.5)
    esc(hwnd)
    res("[writer] Alt, R, C adds a comment", annotations(doc) == before + 1, f"{before} -> {annotations(doc)}")
    wg.chord(VK_CTRL, VK_ALT, ord("F"), target=hwnd)
    time.sleep(1.5)
    esc(hwnd, 1)
    res("[writer] Ctrl+Alt+F inserts a footnote", doc.Footnotes.Count == 1, doc.Footnotes.Count)
    state = doc.RecordChanges
    wg.chord(VK_CTRL, VK_SHIFT, ord("E"), target=hwnd)
    time.sleep(1.0)
    res("[writer] Ctrl+Shift+E toggles Track Changes", doc.RecordChanges != state, doc.RecordChanges)
    doc.RecordChanges = False


def calc(office, doc, hwnd, res, out):
    sheet = doc.Sheets.getByIndex(0)
    for row, value in enumerate((3, 1, 2)):
        sheet.getCellByPosition(0, row).setValue(value)
    doc.CurrentController.select(sheet.getCellRangeByName("A1:A3"))
    alt_tip(hwnd, "ASA")
    time.sleep(1.5)
    got = [sheet.getCellByPosition(0, r).getValue() for r in range(3)]
    res("[calc] Alt, A, SA sorts A to Z", got == [1, 2, 3], got)
    cell = sheet.getCellByPosition(0, 0)
    doc.CurrentController.select(cell)
    front(hwnd)
    wg.chord(VK_CTRL, ord("5"), target=hwnd, front=False)
    time.sleep(1.0)
    res("[calc] Ctrl+5 strikes the cell through", cell.CharStrikeout != 0, cell.CharStrikeout)
    row = sheet.Rows.getByIndex(0)
    wg.chord(VK_CTRL, ord("9"), target=hwnd)
    time.sleep(1.0)
    res("[calc] Ctrl+9 hides the row", not row.IsVisible, row.IsVisible)
    row.IsVisible = True


def impress(office, doc, hwnd, res, out):
    pages = doc.DrawPages
    before = pages.Count
    alt_tip(hwnd, "NSI")
    time.sleep(1.5)
    res("[impress] Alt, N, SI adds a slide", pages.Count == before + 1, f"{before} -> {pages.Count}")
    alt_tip(hwnd, "HI")
    time.sleep(1.5)
    res("[impress] Alt, H, I adds a slide", pages.Count == before + 2, f"{before} -> {pages.Count}")
    before_dialogs = len(wg.dialogs(office))
    wg.chord(VK_CTRL, ord("T"), target=hwnd)
    time.sleep(2.0)
    shown = wg.dialogs(office)
    res("[impress] Ctrl+T opens the font dialog", len(shown) > before_dialogs, [t for _d, t in shown])
    for dialog, _title in shown:
        wg.close_dialog(dialog)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2371)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(5)
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        for app, step in (("writer", writer), ("calc", calc), ("impress", impress)):
            doc = office.load(FACTORY[app])
            time.sleep(4)
            # the welcome window can open with the first document: closed with WM_CLOSE, never with a key
            wg.dismiss_startup(office, os.path.join(args.out, f"{app}-startup.png"), timeout=8, settle=2)
            window = wg.find_window(lambda title: TITLE[app] in title, timeout=30)
            hwnd = window[0] if window else None
            if not hwnd:
                res(f"[{app}] window found", False, "none")
                continue
            front(hwnd)
            wg.chord(VK_ALT, target=hwnd, front=False)
            time.sleep(1.0)
            wg.screenshot(os.path.join(args.out, f"{app}-1-alt.png"))
            letters(hwnd, "H")
            wg.screenshot(os.path.join(args.out, f"{app}-2-home.png"))
            esc(hwnd, 3)
            try:
                step(office, doc, hwnd, res, args.out)
            except wg.BlockedInput as error:
                res(f"[{app}] keys reached the document", False, repr(error))
            doc.setModified(False)
            doc.close(True)
    finally:
        office.stop()
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
