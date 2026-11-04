# SPDX-License-Identifier: AGPL-3.0-only
"""Shared steps of check-dialogs-sheets.py and its Format Cells checks (tabs, Merge cells, Accounting)."""
import time

from hst_dialog_uitest import click, props, select_entry, select_tab, state, tab_titles, visible

FORMAT_CELLS = (".uno:FormatCellDialog", "FormatCellsDialog")
NUMBER_TAB, ALIGNMENT_TAB = 0, 1


def type_text(dialog, widget, text):
    """Replace the text of an entry; no Tab key, so nothing else lands in the field."""
    field = dialog.getChild(widget)
    field.executeAction("FOCUS", ())
    field.executeAction("SELECT", props(FROM="0", TO="99"))
    field.executeAction("TYPE", props(KEYCODE="BACKSPACE"))
    field.executeAction("TYPE", props(TEXT=text))
    time.sleep(0.2)


def close_welcome(h):
    """The first-run welcome is modal and can open late on a fresh profile: it would take the focus."""
    top = h.ui.getTopFocusWindow()
    if "chào đón" in state(top).get("Text", "") and "ok" in top.getChildren():
        top.getChild("ok").executeAction("CLICK", ())
        time.sleep(1)


def new_sheet(h, ranges):
    """A new spreadsheet with the given A1-style range selected."""
    doc = h.new_document("scalc")
    sheet = doc.Sheets.getByIndex(0)
    doc.getCurrentController().select(sheet.getCellRangeByName(ranges))
    h.wait_idle()
    close_welcome(h)
    return doc, sheet


def merged(sheet, cell):
    """Is this cell the start of a merged block? Cursor-based, as a macro would ask."""
    cursor = sheet.createCursorByRange(sheet.getCellRangeByName(cell))
    return cursor.getIsMerged()


def check_format_cells_tabs(h, c):
    doc, sheet = new_sheet(h, "A1:B2")
    dlg = h.open_dialog(*FORMAT_CELLS)
    titles = tab_titles(dlg)
    c.equal("format cells: Excel's six tabs", titles, ["Số", "Căn chỉnh", "Phông chữ", "Viền", "Tô màu", "Bảo vệ"])
    width, height = (int(part) for part in state(dlg)["Size"].split("x"))
    c.equal("format cells: fits a 1366x768 screen", width <= 1366 and height <= 768, True)
    select_tab(dlg, titles.index("Phông chữ"))
    for kept in ("edWestFontName", "fontcolorlb", "underlinelb", "strikeoutlb"):
        c.equal(f"format cells: {kept} on the Font tab", visible(dlg, kept), True)
    c.equal("format cells: no superscript for a cell", visible(dlg, "checkHST_SUPERSCRIPT"), False)
    select_entry(dlg, "underlinelb", 1)
    click(dlg, "ok")
    h.wait_idle()
    c.equal("format cells: underline applied", sheet.getCellRangeByName("A1").CharUnderline != 0, True)
    doc.close(True)


def check_format_cells_font_command(h, c):
    doc, _sheet = new_sheet(h, "A1")
    dlg = h.open_dialog(".uno:FontEffectsDialog", "FormatCellsDialog")
    c.equal("format cells: font effects command opens Font", state(dlg.getChild("tabcontrol"))["CurrPageTitle"], "Phông chữ")
    click(dlg, "cancel")
    doc.close(True)


def check_merge_cells(h, c):
    doc, sheet = new_sheet(h, "A1:B2")
    sheet.getCellRangeByName("A1").setString("Tiêu đề")
    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, ALIGNMENT_TAB)
    c.equal("merge: checkbox shown", visible(dlg, "checkMergeCells"), True)
    c.equal("merge: off for plain cells", state(dlg.getChild("checkMergeCells")).get("Selected"), "false")
    click(dlg, "checkMergeCells")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("merge: A1:B2 merged", merged(sheet, "A1:B2"), True)
    c.equal("merge: text kept", sheet.getCellRangeByName("A1").getString(), "Tiêu đề")

    doc.getCurrentController().select(sheet.getCellRangeByName("A1:B2"))
    h.wait_idle()
    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, ALIGNMENT_TAB)
    c.equal("merge: on for a merged block", state(dlg.getChild("checkMergeCells")).get("Selected"), "true")
    click(dlg, "checkMergeCells")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("merge: unmerged again", merged(sheet, "A1:B2"), False)

    # A selection that holds a merged block next to plain cells merges as one block, as in Excel.
    sheet.getCellRangeByName("A1:B1").merge(True)
    doc.getCurrentController().select(sheet.getCellRangeByName("A1:C3"))
    h.wait_idle()
    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, ALIGNMENT_TAB)
    click(dlg, "checkMergeCells")  # mixed -> off
    click(dlg, "checkMergeCells")  # off -> on
    click(dlg, "ok")
    h.wait_idle()
    c.equal("merge: mixed selection becomes one block", merged(sheet, "A1:C3"), True)
    doc.close(True)

    # A single plain cell offers nothing to merge.
    doc, sheet = new_sheet(h, "D4")
    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, ALIGNMENT_TAB)
    c.equal("merge: disabled for one cell", state(dlg.getChild("checkMergeCells")).get("Enabled"), "false")
    click(dlg, "cancel")
    doc.close(True)


def check_accounting(h, c):
    doc, sheet = new_sheet(h, "A1:A2")
    sheet.getCellRangeByName("A1").setValue(1234.5)
    sheet.getCellRangeByName("A2").setValue(-7)
    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, NUMBER_TAB)
    categories = dlg.getChild("categorylb")
    names = [state(categories.getChild(str(i)))["Text"] for i in range(int(state(categories)["Children"]))]
    c.equal("accounting: follows Currency", names[names.index("Tiền tệ") + 1], "Kế toán")
    select_entry(dlg, "categorylb", names.index("Kế toán"))
    code = state(dlg.getChild("formatted"))["Text"] if "formatted" in dlg.getChildren() else ""
    c.equal("accounting: code fills up to the digits", code.startswith("_-") and "* " in code, True)
    click(dlg, "ok")
    h.wait_idle()
    key = sheet.getCellRangeByName("A1").NumberFormat
    stored = doc.getNumberFormats().getByKey(key).FormatString
    c.equal("accounting: format applied", stored.startswith("_-") and "* " in stored, True)
    c.equal("accounting: four sections like Excel", stored.count(";"), 3)

    dlg = h.open_dialog(*FORMAT_CELLS)
    select_tab(dlg, NUMBER_TAB)
    c.equal("accounting: reopens on its row", state(dlg.getChild("categorylb"))["SelectEntryText"], "Kế toán")
    click(dlg, "cancel")
    doc.close(True)
