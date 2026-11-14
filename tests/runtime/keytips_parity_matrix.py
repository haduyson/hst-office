# SPDX-License-Identifier: AGPL-3.0-only
"""Key input, key tips and the command / shortcut matrix of check-keytips-office-parity.py."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)


def tips():
    """Texts of the visible key tips: short labels of capitals or digits."""
    import pyatspi
    found = set()
    for node in gui.walk(gui.office_app()):
        try:
            if (node.getRoleName() == "label" and 0 < len(node.name or "") <= 2 and node.name == node.name.upper()
                    and node.getState().contains(pyatspi.STATE_SHOWING) and gui.extents(node)[1] < 260):
                found.add(node.name)
        except Exception:  # noqa: BLE001 - widgets come and go
            pass
    return found


def key(args, *names, pause=0.5):
    for name in names:
        gui.xdo(args.display, "key", name)
        time.sleep(pause)
    time.sleep(0.6)


def letters(args, word):
    key(args, *[c.lower() for c in word])


def focus(args):
    gui.xdo(args.display, "mousemove", "700", "600", "click", "1")
    time.sleep(0.8)


def new_window(office, before, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        fresh = [(w, n) for w, n in hst_gui.toplevels(office.display, office.pid) if w not in before]
        if fresh:
            return fresh[0]
        time.sleep(0.4)
    return None


def dialog_key(office, args, label, keys):
    before = {w for w, _ in hst_gui.toplevels(office.display, office.pid)}
    key(args, keys)
    found = new_window(office, before)
    record(label, found is not None, found)
    if found:
        gui.xdo(args.display, "windowfocus", "--sync", found[0], "key", "Escape")
        time.sleep(1.0)


def command_letters(office, args, app, doc, label):
    focus(args)
    if app == "writer":
        doc.Text.setString("parity")
        count = lambda: sum(1 for f in iter_enum(doc.TextFields) if f.supportsService("com.sun.star.text.textfield.Annotation"))  # noqa: E731,E501
        before = count()
        key(args, "Alt_L")
        letters(args, "RC")
        time.sleep(1.5)
        key(args, "Escape")
        record(label("Alt, R, C adds a comment (New Comment)"), count() == before + 1, f"{before} -> {count()}")
    elif app == "calc":
        sheet = doc.Sheets.getByIndex(0)
        for row, value in enumerate((3, 1, 2)):
            sheet.getCellByPosition(0, row).setValue(value)
        doc.CurrentController.select(sheet.getCellRangeByName("A1:A3"))
        key(args, "Alt_L")
        letters(args, "ASA")
        time.sleep(1.5)
        got = [sheet.getCellByPosition(0, r).getValue() for r in range(3)]
        record(label("Alt, A, SA sorts A to Z"), got == [1, 2, 3], got)
    elif app == "impress":
        pages = doc.DrawPages
        before = pages.Count
        key(args, "Alt_L")
        letters(args, "NSI")
        time.sleep(1.5)
        record(label("Alt, N, SI adds a slide (Insert tab)"), pages.Count == before + 1, f"{before} -> {pages.Count}")
        key(args, "Alt_L")
        letters(args, "HI")
        time.sleep(1.5)
        record(label("Alt, H, I adds a slide (Home tab)"), pages.Count == before + 2, f"{before} -> {pages.Count}")


def iter_enum(access):
    enum = access.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def shortcut_matrix(office, args, app, doc, label):
    focus(args)
    if app == "writer":
        before = doc.Footnotes.Count
        key(args, "ctrl+alt+f")
        key(args, "Escape")
        record(label("Ctrl+Alt+F inserts a footnote"), doc.Footnotes.Count == before + 1, doc.Footnotes.Count)
        focus(args)
        state = doc.RecordChanges
        key(args, "ctrl+shift+e")
        record(label("Ctrl+Shift+E toggles Track Changes"), doc.RecordChanges != state, doc.RecordChanges)
        doc.RecordChanges = False
    elif app == "calc":
        sheet = doc.Sheets.getByIndex(0)
        cell = sheet.getCellByPosition(0, 0)
        doc.CurrentController.select(cell)
        key(args, "ctrl+5")
        record(label("Ctrl+5 strikes the cell through"), cell.CharStrikeout != 0, cell.CharStrikeout)
        row = sheet.Rows.getByIndex(0)
        key(args, "ctrl+9")
        record(label("Ctrl+9 hides the row"), not row.IsVisible, row.IsVisible)
        row.IsVisible = True
        dialog_key(office, args, label("Shift+F3 opens Insert Function"), "shift+F3")
    elif app == "impress":
        dialog_key(office, args, label("Alt+F8 opens Macros"), "alt+F8")
    elif app == "draw":
        dialog_key(office, args, label("F12 opens Save As"), "F12")
    if app in ("writer", "calc"):
        focus(args)
        before = {w for w, _ in hst_gui.toplevels(office.display, office.pid)}
        key(args, "ctrl+F2")
        time.sleep(2)
        name = office.desktop().getCurrentFrame().getController().getImplementationName()
        record(label("Ctrl+F2 opens Print Preview"), "Preview" in name or "PagePreview" in name, name)
        key(args, "Escape")
        new_window(office, before, timeout=1)
