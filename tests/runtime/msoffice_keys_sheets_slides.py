# SPDX-License-Identifier: AGPL-3.0-only
"""HST Sheets and HST Slides part of check-msoffice-shortcuts.py: the Excel and PowerPoint keys."""
from msoffice_keys_writer import dialog_check
from shortcut_keys import check, wait


def calc_checks(office, keys):
    doc = office.load("private:factory/scalc")
    wait(lambda: "Sheets" in office.desktop().getCurrentFrame().getTitle(), 20)
    office.raise_windows()
    sheet = doc.getSheets().getByIndex(0)
    ctrl = doc.getCurrentController()
    cell = sheet.getCellByPosition
    for row, value in enumerate((1, 2, 3)):
        cell(0, row).setValue(value)
    ctrl.select(cell(0, 3))
    keys.send("alt+equal")
    keys.send("Return")
    check("Sheets Alt+= AutoSum", wait(lambda: cell(0, 3).getFormula().upper() == "=SUM(A1:A3)", 5), cell(0, 3).getFormula())

    ctrl.select(sheet.getCellRangeByName("A1:C1"))
    keys.send("ctrl+r")
    check("Sheets Ctrl+R fills right", wait(lambda: cell(2, 0).getValue() == 1, 5), cell(2, 0).getValue())

    formats = doc.getNumberFormats()
    target = cell(3, 0)
    target.setValue(0.5)
    ctrl.select(target)
    kind = lambda: formats.getByKey(target.NumberFormat).Type  # noqa: E731
    # com.sun.star.util.NumberFormat: DATE 2, TIME 4, CURRENCY 8, NUMBER 16, SCIENTIFIC 32, PERCENT 128
    for combo, mask, name in (("ctrl+shift+2", 4, "@ time"), ("ctrl+shift+3", 2, "# date"), ("ctrl+shift+6", 32, "^ scientific"),
                              ("ctrl+shift+4", 8, "$ currency"), ("ctrl+shift+5", 128, "% percent"), ("ctrl+shift+1", 16, "! number")):
        keys.send(combo)
        check(f"Sheets Ctrl+Shift+{name} format", wait(lambda: kind() & mask, 5), kind())
    keys.send("ctrl+shift+grave")
    check("Sheets Ctrl+Shift+~ General format",
          wait(lambda: formats.getByKey(target.NumberFormat).FormatString in ("General", "Standard"), 5),
          formats.getByKey(target.NumberFormat).FormatString)

    ctrl.select(cell(4, 0))
    keys.send("a")
    keys.send("alt+Return")
    keys.send("b")
    keys.send("Return")
    check("Sheets Alt+Enter starts a new line in the cell", wait(lambda: cell(4, 0).getString().lower() == "a\nb", 5),
          repr(cell(4, 0).getString()))
    ctrl.select(sheet.getCellRangeByName("F1:G2"))
    keys.send("x")
    keys.send("ctrl+Return")
    check("Sheets Ctrl+Enter fills the selected cells", wait(lambda: cell(6, 1).getString() == "x", 5),
          repr(cell(6, 1).getString()))

    count = doc.getSheets().getCount()
    keys.send("shift+F11")
    check("Sheets Shift+F11 inserts a sheet", wait(lambda: doc.getSheets().getCount() == count + 1, 5),
          doc.getSheets().getCount())
    ctrl.setActiveSheet(sheet)
    ctrl.select(sheet.getCellRangeByName("A1:A3"))
    dialog_check(office, keys, "ctrl+t", "Sheets Ctrl+T Create Table")
    doc.setModified(False)


def impress_checks(office, keys):
    doc = office.load("private:factory/simpress")
    wait(lambda: "Slides" in office.desktop().getCurrentFrame().getTitle(), 20)
    office.raise_windows()
    pages = doc.getDrawPages()
    for combo, name in (("ctrl+m", "Ctrl+M new slide"), ("ctrl+d", "Ctrl+D duplicate slide"),
                        ("ctrl+shift+d", "Ctrl+Shift+D duplicate slide")):
        count = pages.getCount()
        keys.send(combo)
        check(f"Slides {name}", wait(lambda: pages.getCount() == count + 1, 8), f"{count} -> {pages.getCount()}")

    from com.sun.star.awt import Point, Size
    page = doc.getCurrentController().getCurrentPage()
    shapes = office.service("com.sun.star.drawing.ShapeCollection")
    for x in (1000, 6000):
        shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
        page.add(shape)
        shape.setPosition(Point(x, 9000))
        shape.setSize(Size(3000, 2000))
        shapes.add(shape)
    doc.getCurrentController().select(shapes)
    groups = lambda: sum(page.getByIndex(i).ShapeType == "com.sun.star.drawing.GroupShape"  # noqa: E731
                         for i in range(page.getCount()))
    keys.send("ctrl+g")
    check("Slides Ctrl+G groups", wait(lambda: groups() == 1, 5), groups())
    keys.send("ctrl+shift+g")
    check("Slides Ctrl+Shift+G ungroups", wait(lambda: groups() == 0, 5), groups())
    dialog_check(office, keys, "F12", "Slides F12 Save As dialog")
    doc.setModified(False)
