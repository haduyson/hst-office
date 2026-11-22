# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Runtime check of the shortcut parity table on a built HST Office (Linux, GTK3, Xvfb, vi UI).

Usage: python3 tests/runtime/check-shortcut-parity-runtime.py --instdir <instdir> [--out DIR] [--display :97]

1. Configuration sweep: every matching row of data/ribbon/shortcuts-office-parity.json (Windows/Linux key, no
   "handler") must run one of its commands in the running office: the module's shortcut manager, else the global
   one (com.sun.star.ui.GlobalAcceleratorConfiguration).
2. Real keys (xdotool) and their effect read back over UNO: Writer Ctrl+Shift+A All Caps on and off (the text is
   unchanged), Shift+F12 / Ctrl+F12 open the Save As / Open dialog of a new document, F1 hands the offline guide to
   xdg-open; Sheets Ctrl+Shift+F opens Format Cells, Ctrl+Alt+L reapplies the filter after the data changed; Slides
   Ctrl+Shift+C then Ctrl+Shift+V copies a shape's fill to another shape.
Exit 1 when any check fails.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from msoffice_keys_helpers import dialog_check  # noqa: E402
from shortcut_keys import RESULTS, Keys, check, wait, xdg_stub  # noqa: E402

PORT = 22964
DATA = os.path.join(hst_gui.ROOT, "data", "ribbon", "shortcuts-office-parity.json")
MODULES = {"writer": "com.sun.star.text.TextDocument", "calc": "com.sun.star.sheet.SpreadsheetDocument",
           "impress": "com.sun.star.presentation.PresentationDocument", "draw": "com.sun.star.drawing.DrawingDocument"}
MODIFIERS = {"SHIFT": 1, "MOD1": 2, "MOD2": 4, "MOD3": 8}


def key_event(code):
    """com.sun.star.awt.KeyEvent of an Accelerators.xcu key name ("F12_SHIFT_MOD1", "5_MOD1", "SEMICOLON_MOD1")."""
    import uno
    from com.sun.star.awt import KeyEvent
    parts = code.split("_")
    name = parts[0]
    event = KeyEvent()
    event.KeyCode = uno.getConstantByName("com.sun.star.awt.Key." + ("NUM" + name if name.isdigit() else name))
    event.Modifiers = sum(MODIFIERS[m] for m in parts[1:])
    return event


def command_of(office, module, code):
    """Command (without .uno: and arguments) the running office binds to code in module, or ""."""
    smgr = office.ctx.ServiceManager
    supplier = smgr.createInstanceWithContext("com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
    managers = [supplier.getUIConfigurationManager(module).getShortCutManager(),
                smgr.createInstanceWithContext("com.sun.star.ui.GlobalAcceleratorConfiguration", office.ctx)]
    for manager in managers:
        try:
            return manager.getCommandByKeyEvent(key_event(code)).replace(".uno:", "").split("?", 1)[0]
        except Exception:  # noqa: BLE001,S112 - NoSuchElementException: not bound at this level
            continue
    return ""


def config_sweep(office):
    with open(DATA, encoding="utf-8") as handle:
        rows = json.load(handle)["rows"]
    checked = 0
    for row in rows:
        if row["status"] != "match" or row.get("platform") or row.get("handler"):
            continue
        got = command_of(office, MODULES[row["app"]], row["key"])
        checked += 1
        check(f"config {row['app']} {row['office']} -> {'/'.join(row['uno'])}", got in row["uno"], f"got {got!r}")
    check("config sweep covered the table", checked > 150, checked)


def writer_keys(office, keys, log):
    doc = office.load("private:factory/swriter")
    text = doc.getText()
    text.insertString(text.getEnd(), "Xin chào HST Office", False)
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()
    keys.send("ctrl+End")  # the first key after the window appears can be lost
    ctrl = doc.getCurrentController()
    para = text.createEnumeration().nextElement()
    ctrl.select(para)
    sel = lambda: ctrl.getSelection().getByIndex(0)  # noqa: E731
    keys.send("ctrl+shift+a")
    check("Writer Ctrl+Shift+A turns All Caps on", wait(lambda: sel().CharCaseMap == 1, 5), sel().CharCaseMap)
    check("Writer Ctrl+Shift+A keeps the typed text", sel().getString() == "Xin chào HST Office", sel().getString())
    keys.send("ctrl+shift+a")
    check("Writer Ctrl+Shift+A again turns All Caps off", wait(lambda: sel().CharCaseMap == 0, 5), sel().CharCaseMap)
    dialog_check(office, keys, "shift+F12", "Writer Shift+F12 saves a new document: Save As")
    dialog_check(office, keys, "ctrl+F12", "Writer Ctrl+F12 Open")
    keys.send("F1")
    check("F1 opens the offline guide", wait(lambda: "help" in open(log, encoding="utf-8").read(), 15),
          open(log, encoding="utf-8").read()[-200:])
    doc.setModified(False)


def calc_keys(office, keys):
    from com.sun.star.sheet import TableFilterField
    from com.sun.star.sheet.FilterOperator import EQUAL
    doc = office.load("private:factory/scalc")
    sheet = doc.Sheets.getByIndex(0)
    for row, value in enumerate(("Tên", "a", "b", "a", "b")):
        sheet.getCellByPosition(0, row).setString(value)
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()
    ctrl = doc.getCurrentController()
    ctrl.select(sheet.getCellRangeByName("A2"))
    dialog_check(office, keys, "ctrl+shift+f", "Sheets Ctrl+Shift+F Format Cells")
    area = sheet.getCellRangeByName("A1:A5")
    desc = area.createFilterDescriptor(True)
    field = TableFilterField()
    field.Field, field.Operator, field.IsNumeric, field.StringValue = 0, EQUAL, False, "a"
    desc.setFilterFields((field,))
    desc.ContainsHeader = True
    area.filter(desc)
    visible = lambda r: sheet.getRows().getByIndex(r).IsVisible  # noqa: E731
    check("Sheets filter hides the 'b' rows", not visible(2) and visible(1), f"{visible(1)} {visible(2)}")
    sheet.getCellByPosition(0, 2).setString("a")  # the hidden row now matches
    ctrl.select(sheet.getCellRangeByName("A2"))
    keys.send("ctrl+alt+l")
    check("Sheets Ctrl+Alt+L reapplies the filter", wait(lambda: visible(2) and not visible(4), 8),
          f"row3 {visible(2)} row5 {visible(4)}")
    doc.setModified(False)


def impress_keys(office, keys):
    from com.sun.star.awt import Point, Size
    doc = office.load("private:factory/simpress")
    page = doc.DrawPages.getByIndex(0)
    shapes = []
    for n, color in enumerate((0xFF0000, 0x00AA00)):
        shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
        page.add(shape)
        shape.setPosition(Point(2000 + n * 8000, 3000))
        shape.setSize(Size(5000, 3000))
        shape.FillColor = color
        shapes.append(shape)
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()
    ctrl = doc.getCurrentController()
    ctrl.select(shapes[0])
    keys.send("ctrl+shift+c")
    ctrl.select(shapes[1])
    keys.send("ctrl+shift+v")
    check("Slides Ctrl+Shift+C / Ctrl+Shift+V copy the fill", wait(lambda: shapes[1].FillColor == 0xFF0000, 8),
          hex(shapes[1].FillColor))
    doc.setModified(False)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/shortcut-parity"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    bindir, log = xdg_stub(work)
    office = hst_gui.Office(args.instdir, work, PORT, display=args.display, lang="vi_VN.UTF-8",
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"),
                                    ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")],
                            env={"PATH": bindir + ":/usr/local/bin:/usr/bin:/bin"})
    try:
        office.start()
        config_sweep(office)
        keys = Keys(office)
        for step in (writer_keys, calc_keys, impress_keys):
            try:
                step(office, keys, log) if step is writer_keys else step(office, keys)
            except Exception as error:  # noqa: BLE001 - report and go on with the next module
                check(f"{step.__name__} completed", False, repr(error))
        for comp in office.desktop().getComponents():  # no "save?" question on terminate
            comp.setModified(False)
    finally:
        office.stop()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
