#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets dialogs follow Excel's structure: tab order, key controls, and edits that reach the document.

Usage: check-dialogs-sheets.py [--instdir DIR] [--work DIR] [dialog ...]   (default: every dialog)
Needs a built instdir with the vi language pack. Runs on a private Xvfb with a fresh profile.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import (Checks, DialogHarness, click, props, select_entry, select_tab, state,  # noqa: E402
                               tab_titles, visible)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def check_page_setup(h, c):
    doc, sheet = new_sheet(h, "A1")
    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    titles = tab_titles(dlg)
    page = titles.index("Trang")
    c.equal("page setup: Excel's order", titles[page:page + 4], ["Trang", "Đầu trang", "Chân trang", "Trang tính"])
    select_tab(dlg, titles.index("Trang tính"))
    type_text(dlg, "entryRepeatRows", "$1:$2")
    type_text(dlg, "entryRepeatCols", "$A:$B")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("page setup: rows repeat", sheet.PrintTitleRows, True)
    c.equal("page setup: rows 1-2", (sheet.TitleRows.StartRow, sheet.TitleRows.EndRow), (0, 1))
    c.equal("page setup: columns repeat", sheet.PrintTitleColumns, True)
    c.equal("page setup: columns A-B", (sheet.TitleColumns.StartColumn, sheet.TitleColumns.EndColumn), (0, 1))

    # Switching tabs and cancelling must not touch the sheet.
    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    select_tab(dlg, titles.index("Trang tính"))
    type_text(dlg, "entryRepeatRows", "$3:$4")
    select_tab(dlg, titles.index("Trang"))
    click(dlg, "cancel")
    h.wait_idle()
    c.equal("page setup: cancel keeps rows", (sheet.TitleRows.StartRow, sheet.TitleRows.EndRow), (0, 1))
    doc.close(True)


def wait_for_widget(h, widget, timeout=40):
    """A modeless dialog has no ID of its own here: wait until one of its widgets can be reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        close_welcome(h)
        top = h.ui.getTopFocusWindow()
        if widget in top.getChildren():
            return top
        time.sleep(0.3)
    raise AssertionError(f"{widget} did not appear")


def check_conditional_format(h, c):
    doc, sheet = new_sheet(h, "A1:A5")
    for row in range(5):
        sheet.getCellByPosition(0, row).setValue(row + 1)
    h.ui.executeDialog(".uno:ConditionalFormatDialog")
    dlg = wait_for_widget(h, "ConditionalFormatDialog")
    c.equal("conditional format: seven rule types", state(dlg.getChild("type"))["EntryCount"], "7")
    select_entry(dlg, "type", 2)
    h.wait_idle(2)
    dlg = wait_for_widget(h, "typeis")
    c.equal("conditional format: ranked conditions only", state(dlg.getChild("typeis"))["EntryCount"], "4")
    click(dlg, "ok")
    h.wait_idle()
    formats = sheet.ConditionalFormats.getConditionalFormats()
    c.equal("conditional format: rule applied", len(formats), 1)

    dlg = h.open_dialog(".uno:ConditionalFormatManagerDialog", "CondFormatManager")
    first = state(dlg.getChild("CONTAINER").getChild("0"))["Text"]
    c.equal("manager: the rule comes first", first.startswith("A1"), False)
    click(dlg, "ok")
    doc.close(True)


def check_name_manager(h, c):
    doc, sheet = new_sheet(h, "A1")
    sheet.getCellRangeByName("A1").setValue(42)
    origin = sheet.getCellRangeByName("A1").getCellAddress()
    doc.NamedRanges.addNewByName("Thue", f"$'{sheet.Name}'.$A$1", origin, 0)
    doc.NamedRanges.addNewByName("Khoi", f"$'{sheet.Name}'.$A$1:$B$2", origin, 0)
    h.ui.executeDialog(".uno:DefineName")
    dlg = wait_for_widget(h, "names")
    h.wait_idle(2)
    names = dlg.getChild("names")
    c.equal("name manager: rows listed", state(names)["Children"], "2")
    rows = dict(state(names.getChild(str(i)))["Text"].split("\t")[:2] for i in range(2))
    c.equal("name manager: value of one cell", rows["Thue"], "42")
    c.equal("name manager: value of a block", rows["Khoi"], "{...}")
    click(dlg, "cancel")
    doc.close(True)


def check_sort(h, c):
    doc, sheet = new_sheet(h, "A1:B4")
    rows = (("Tên", "Số"), ("Bình", 2), ("An", 3), ("Chi", 1))
    for r, row in enumerate(rows):
        sheet.getCellByPosition(0, r).setString(row[0])
        if r:
            sheet.getCellByPosition(1, r).setValue(row[1])
    sheet.getCellByPosition(1, 0).setString("Số")
    dlg = h.open_dialog(".uno:DataSort", "SortDialog")
    c.equal("sort: tabs", len(tab_titles(dlg)), 2)
    c.equal("sort: Add Level shown", visible(dlg, "btnAddLevel"), True)
    c.equal("sort: Delete Level shown", visible(dlg, "btnDeleteLevel"), True)
    click(dlg, "btnAddLevel")
    click(dlg, "btnDeleteLevel")
    select_entry(dlg, "sortlb", 1)
    click(dlg, "ok")
    h.wait_idle()
    c.equal("sort: sorted by the first column", sheet.getCellByPosition(0, 1).getString(), "An")
    doc.close(True)


CHECKS = {
    "conditional-format": check_conditional_format,
    "name-manager": check_name_manager,
    "format-cells-tabs": check_format_cells_tabs,
    "format-cells-font-command": check_format_cells_font_command,
    "merge-cells": check_merge_cells,
    "accounting": check_accounting,
    "page-setup": check_page_setup,
    "sort": check_sort,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/dialogs-sheets"))
    parser.add_argument("dialogs", nargs="*", choices=[[], *CHECKS], default=[])
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, 22981, ":81")
    checks = Checks()
    try:
        for name in args.dialogs or CHECKS:
            CHECKS[name](harness, checks)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
