# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog, save-warning, Writer and menu steps of check-vietnamese-utilities.py (real dispatches, keys, screenshots)."""
import os
import time

import hst_gui
import vietnamese_utilities_gui as gui
from vietnamese_utilities_gui import record


def dialogs(office, doc, args):
    controller = doc.getCurrentController()
    frame = controller.getFrame()
    sheet = controller.getActiveSheet()
    cell = sheet.getCellRangeByName
    cell("P1").setValue(10000000)
    controller.select(cell("P1"))
    thread = gui.background_dispatch(office, frame, "org.hst.office.vi:NumberToWords")
    wid = gui.wait_window(office, r"^Đọc số thành chữ$")
    record("Đọc số thành chữ dialog opens", wid is not None)
    if wid:
        gui.dialog_shot(office, wid, args.shots, "doc-so-thanh-chu")
        gui.keys(office.display, wid, "Return")
        thread.join(30)
        record("dialog writes the words as text into the cell on the right", cell("Q1").getString() == "Mười triệu"
               and cell("Q1").getFormula() == "Mười triệu", cell("Q1").getFormula())
    controller.select(cell("P1"))
    thread = gui.background_dispatch(office, frame, "org.hst.office.vi:NumberToWords")
    wid = gui.wait_window(office, r"^Đọc số thành chữ$")
    if wid:
        # Tab order: source, target, kind (Down = money), preset, unit, sub, thousand, odd, four, language, output
        gui.keys(office.display, wid, "Tab", "Tab", "Down", *(["Tab"] * 8), "Down")
        gui.dialog_shot(office, wid, args.shots, "doc-so-thanh-chu-cong-thuc")
        gui.keys(office.display, wid, "Return", "Return")  # Q1 holds the words: the first Return asks to "Ghi đè"
        thread.join(30)
        record("dialog writes a DOCTIEN formula", "DOCTIEN" in cell("Q1").getFormula().upper()
               and cell("Q1").getString() == "Mười triệu đồng chẵn", (cell("Q1").getFormula(), cell("Q1").getString()))


def save_warning(office, doc, args):
    import uno
    from com.sun.star.beans import PropertyValue
    controller = doc.getCurrentController()
    frame, cell = controller.getFrame(), controller.getActiveSheet().getCellRangeByName
    out = os.path.join(os.path.abspath(args.out), "files")
    os.makedirs(out, exist_ok=True)

    def save_as(name, keys, shot=None):
        path = os.path.join(out, name)
        if os.path.exists(path):
            os.remove(path)
        props = (PropertyValue(Name="URL", Value=uno.systemPathToFileUrl(path)),
                 PropertyValue(Name="FilterName", Value="Calc MS Excel 2007 XML"))
        thread = gui.background_dispatch(office, frame, ".uno:SaveAs", props)
        wid = gui.wait_window(office, r"^Lưu tệp Excel$")
        if wid and shot:
            gui.dialog_shot(office, wid, args.shots, shot)
        if wid:
            gui.keys(office.display, wid, *keys)
        thread.join(60)
        return wid, path

    original = cell("A1").getFormula()  # the API shows the add-in by its programmatic name
    wid, path = save_as("huy.xlsx", ["Escape"], "canh-bao-luu-xlsx")
    record("save .xlsx warns about the HST functions", wid is not None)
    record("Hủy: nothing is saved", not os.path.exists(path))
    wid, path = save_as("van-luu.xlsx", ["Tab", "Tab", "space"])
    saved = office.load(uno.systemPathToFileUrl(path), hidden=True) if os.path.exists(path) else None
    record("Vẫn lưu: the file keeps the formulas", saved is not None and
           "DOCSO" in saved.Sheets.getByIndex(0).getCellRangeByName("A1").getFormula().upper(),
           saved and saved.Sheets.getByIndex(0).getCellRangeByName("A1").getFormula())
    if saved:
        saved.close(True)
    wid, path = save_as("doi-thanh-chu.xlsx", ["Return"])
    saved = office.load(uno.systemPathToFileUrl(path), hidden=True) if os.path.exists(path) else None
    a1 = saved.Sheets.getByIndex(0).getCellRangeByName("A1") if saved else None
    record("Đổi thành chữ rồi lưu: the file has the words as text", a1 is not None and a1.getType().value == "TEXT"
           and a1.getString() == "Một trăm lẻ năm", a1 and a1.getFormula())
    if saved:
        saved.close(True)
    record("... and the open document keeps its formulas, saved state", cell("A1").getFormula() == original
           and not doc.isModified(), (cell("A1").getFormula(), doc.isModified()))
    cell("Z1").setValue(1)
    before = os.path.getmtime(path)
    thread = gui.background_dispatch(office, frame, ".uno:Save")
    wid = gui.wait_window(office, r"^Lưu tệp Excel$")
    if wid:
        gui.keys(office.display, wid, "Escape")
    thread.join(60)
    record("Ctrl+S on the .xlsx warns too; Hủy keeps the file", wid is not None and os.path.getmtime(path) == before)
    wid, path = save_as("trong-tai-lieu.xlsx", ["space", "Return"])
    record("check box: the open document gets the words too (one undo)", cell("A1").getType().value == "TEXT"
           and cell("A1").getString() == "Một trăm lẻ năm", cell("A1").getFormula())
    doc.getUndoManager().undo()
    record("... and undo brings the formula back", cell("A1").getFormula() == original, cell("A1").getFormula())


def writer(office, args):
    doc = office.load("private:factory/swriter")
    text = doc.getText()
    text.setString("Tổng cộng: 1.250.000 đồng")
    cursor = text.createTextCursor()
    cursor.gotoStart(False)
    cursor.goRight(11, False)
    cursor.goRight(9, True)
    doc.getCurrentController().select(cursor)
    thread = gui.background_dispatch(office, doc.getCurrentController().getFrame(), "org.hst.office.vi:NumberToWords")
    wid = gui.wait_window(office, r"^Đọc số thành chữ$")
    record("Writer: Đọc số thành chữ dialog opens", wid is not None)
    if wid:
        gui.dialog_shot(office, wid, args.shots, "doi-so-thanh-chu-writer")
        gui.keys(office.display, wid, "Return")
        thread.join(30)
    record("Writer: the selected number becomes words", text.getString() == "Tổng cộng: Một triệu hai trăm năm mươi nghìn đồng",
           text.getString())
    menu(office, doc, args, "writer", ["Đọc số thành chữ"])
    doc.close(True)


def menu(office, doc, args, label, expected):
    """Show the classic menu bar, open HST ▸ Tiện ích tiếng Việt, compare its items, take a screenshot."""
    office.dispatch(doc.getCurrentController().getFrame(), ".uno:Menubar")
    time.sleep(3)
    app = gui.office_app()
    hst = gui.find(app, "menu", "HST") if app else None
    if hst is None:
        return record("%s: classic HST menu found" % label, False)
    gui.click(office.display, hst)
    sub = gui.find(hst, "menu", "Tiện ích tiếng Việt", limit=3)
    items = gui.children_names(sub) if sub else []
    if sub:
        gui.hover(office.display, sub)
        os.makedirs(args.shots, exist_ok=True)
        hst_gui.screenshot(os.path.join(args.shots, "menu-hst-%s.png" % label), office.display)
    gui.xdo(office.display, "key", "Escape")
    gui.xdo(office.display, "key", "Escape")
    record("%s: HST ▸ Tiện ích tiếng Việt offers %s" % (label, expected), [i for i in items if i] == expected, items)
    office.dispatch(doc.getCurrentController().getFrame(), ".uno:Menubar")


def blank_rows(doc, host, args, said):
    """Xóa dòng trống on --rows rows of plain data (fast way) and on a sheet whose rows a formula sums (exact way)."""
    from hst_office import actions
    controller = doc.getCurrentController()
    # Xóa dòng trống on a large sheet of plain data (one row of every three is blank) and, the exact way, on a
    # sheet whose rows a formula counts
    for name, rows, total in (("Lon", args.rows, False), ("Nho", 3000, True)):
        doc.Sheets.insertNewByName(name, doc.Sheets.getCount())
        big = doc.Sheets.getByName(name)
        controller.setActiveSheet(big)
        data = tuple(((("Dòng %d" % r), float(r)) if r % 3 != 1 else ("", "")) for r in range(rows))
        big.getCellRangeByPosition(0, 0, 1, rows - 1).setDataArray(data)
        if total:
            big.getCellByPosition(1, rows).setFormula("=SUM(B1:B%d)" % rows)
        end = max(r for r in range(rows) if r % 3 != 1) + 1  # the used area ends at the last data row
        blank = sum(1 for r in range(end) if r % 3 == 1)
        doc.getUndoManager().clear()
        controller.select(big.getCellRangeByName("A1"))
        start = time.time()
        actions.COMMANDS["DeleteBlankRows"](host)
        seconds = time.time() - start
        cursor = big.createCursor()
        cursor.gotoEndOfUsedArea(False)
        left = cursor.getRangeAddress().EndRow + 1
        kept = [big.getCellByPosition(0, r).getString() for r in (0, 1, 2)]
        ok = left == end - blank + total and kept == ["Dòng 0", "Dòng 2", "Dòng 3"] and seconds < 30
        if total:
            ok = ok and big.getCellByPosition(1, left - 1).getFormula() == "=SUM(B1:B%d)" % (end - blank)
        record("Xóa dòng trống (%s): %d blank rows of %d in %.1f s" % (name, blank, rows, seconds), ok, (left, kept, said[-1:]))
        doc.getUndoManager().undo()
        cursor.gotoEndOfUsedArea(False)
        record("Xóa dòng trống (%s): one undo restores all rows" % name, cursor.getRangeAddress().EndRow + 1 == (rows if total else end) + total
               and big.getCellByPosition(0, 1).getString() == "", doc.getUndoManager().getAllUndoActionTitles()[:3])
