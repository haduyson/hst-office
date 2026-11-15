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
from hst_dialog_uitest import (Checks, DialogHarness, click, end_execute_survives, select_entry, select_tab,  # noqa: E402
                               state, tab_titles, visible)
from hst_sheets_dialog_checks import (check_accounting, check_format_cells_font_command,  # noqa: E402
                                      check_format_cells_tabs, check_merge_cells, close_welcome, new_sheet,
                                      type_text)
from hst_sheets_page_scaling import check_page_scaling  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_page_setup(h, c):
    doc, sheet = new_sheet(h, "A1")
    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    c.equal("page setup: opens on the page tab", state(dlg.getChild("tabcontrol")).get("CurrPageTitle"), "Trang")
    titles = tab_titles(dlg)
    c.equal("page setup: style organizer last", titles[-1], "Chung")
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

    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    select_tab(dlg, len(titles) - 1)
    click(dlg, "cancel")
    h.wait_idle()
    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    c.equal("page setup: reopens on the page tab after the organizer",
            state(dlg.getChild("tabcontrol")).get("CurrPageTitle"), "Trang")
    click(dlg, "cancel")
    h.wait_idle()
    c.equal("page setup: the office survives XDialog.endExecute",
            end_execute_survives(h, ".uno:PageFormatDialog", "PageTemplateDialog"), True)

    # The ribbon's Sheet Options launcher opens Page Setup on the Sheet tab.
    ui_file = os.path.join(h.office.program, "..", "share/config/soffice.cfg/modules/scalc/ui/notebookbar.ui")
    with open(ui_file, encoding="utf-8") as handle:
        launcher = handle.read().split('id="btnHstLaunchLayoutSheetOptions"', 1)[1].split("</object>", 1)[0]
    c.equal("sheet options launcher: asks for the Sheet tab", ".uno:PageFormatDialog?Page:string=sheet" in launcher, True)
    dlg = h.open_dialog(".uno:PageFormatDialog?Page:string=sheet", "PageTemplateDialog")
    c.equal("sheet options launcher: opens on the Sheet tab",
            state(dlg.getChild("tabcontrol")).get("CurrPageTitle"), "Trang tính")
    click(dlg, "cancel")
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
    "page-scaling": check_page_scaling,
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
