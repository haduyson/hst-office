# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets command "Xóa dòng trống": delete the rows with no content in the used area (or in the selected rows).

Two ways, both one undo step:
  - Calc's own "Delete Rows" over one multi-range selection: exact for formulas, notes, drawings, conditional formats;
    its cost grows with every separate block of blank rows (about 90 s for 16 667 blocks in 50 000 rows);
  - for plain data (no formula on the sheet, no formula or named range elsewhere naming it, no notes, drawings,
    conditional formats or hidden rows) with many blocks: one stable sort on a temporary rank column moves the blank rows below the data, then one delete
    removes them; 50 000 rows take a few seconds.
No UNO cell-ranges object may stay alive during a deletion: Calc updates each live one on every deleted block.
"""
from . import utilities_texts as T
from . import vietnamese_calc_logic as logic
from .undo import undo_step
from .vietnamese_calc import _is_single_cell, _property, _ranges, _ready

CONTENT, FORMULA = 1 | 2 | 4 | 8 | 16, 16  # com.sun.star.sheet.CellFlags: VALUE|DATETIME|STRING|ANNOTATION|FORMULA
NATIVE_LIMIT = 300  # up to this many blocks, Calc's Delete Rows is fast enough (well under a second)


def _blank_runs(sheet, ranges, used, single_cell):
    """[(start, count)] of the blank rows and the row spans looked at."""
    if single_cell:
        spans = [(used.StartRow, used.EndRow)]
    else:
        spans = [(r.getRangeAddress().StartRow, min(r.getRangeAddress().EndRow, used.EndRow)) for r in ranges]
    runs = []
    for first, last in spans:
        if first <= last:
            found = sheet.getCellRangeByPosition(0, first, used.EndColumn, last).queryContentCells(CONTENT)
            runs += logic.blank_runs(first, last, [(x.StartRow, x.EndRow) for x in found.getRangeAddresses()])
    return runs, spans


def _referenced(doc, sheet):
    """True when a formula on the sheet, a formula on another sheet or a named range may point into the sheet."""
    if sheet.queryContentCells(FORMULA).getCount():
        return True
    name = sheet.getName()
    sheets = doc.getSheets()
    for index in range(sheets.getCount()):
        found = sheets.getByIndex(index).queryContentCells(FORMULA)
        for block in range(found.getCount()):
            if any(name in text for row in found.getByIndex(block).getFormulaArray() for text in row):
                return True
    ranges = doc.NamedRanges
    return any(name in ranges.getByName(n).getContent() for n in ranges.getElementNames())


def _plain_data(doc, sheet, area):
    """True when sorting rows cannot change anything but their order (see the module docstring)."""
    if _referenced(doc, sheet):
        return False
    try:
        if sheet.getAnnotations().getCount() or sheet.getDrawPage().getCount() or sheet.ConditionalFormats.getLength():
            return False
    except Exception:  # noqa: BLE001 - unknown sheet features: keep the exact way
        return False
    return area.queryVisibleCells().getCount() == 1  # no hidden or filtered rows


def _select_rows(host, sheet, runs):
    """Select the whole rows of `runs` as one multi-range selection; the ranges object dies with this call."""
    import uno
    addresses = []
    for start, count in runs:
        address = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        address.Sheet, address.StartColumn = sheet.getRangeAddress().Sheet, 0
        address.EndColumn, address.StartRow, address.EndRow = sheet.getColumns().getCount() - 1, start, start + count - 1
        addresses.append(address)
    rows = host.doc.createInstance("com.sun.star.sheet.SheetCellRanges")
    rows.addRangeAddresses(tuple(addresses), False)
    host.controller.select(rows)


def _delete_native(host, sheet, runs):
    _select_rows(host, sheet, runs)
    dispatcher = host.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", host.ctx)
    dispatcher.executeDispatch(host.frame, ".uno:DeleteRows", "", 0, ())  # one Calc undo step for all blocks


def _delete_by_sort(host, sheet, runs, last_row, last_column):
    """Rank column right of the used area: data rows keep their order, blank rows go last; then one block delete."""
    import uno
    first = runs[0][0]
    blank = set()
    for start, count in runs:
        blank.update(range(start, start + count))
    ranks, kept = [], 0
    for row in range(first, last_row + 1):
        if row in blank:
            ranks.append((float(len(ranks) + 10 ** 9),))
        else:
            ranks.append((float(kept),))
            kept += 1
    helper = last_column + 1
    with undo_step(host.doc, T.UNDO["blank"]):
        sheet.getCellRangeByPosition(helper, first, helper, last_row).setDataArray(tuple(ranks))
        field = uno.createUnoStruct("com.sun.star.table.TableSortField")
        field.Field, field.IsAscending = helper, True
        descriptor = (_property("SortFields", uno.Any("[]com.sun.star.table.TableSortField", (field,))),
                      _property("ContainsHeader", False), _property("BindFormatsToContent", True))
        uno.invoke(sheet.getCellRangeByPosition(0, first, helper, last_row), "sort", (descriptor,))
        sheet.getCellRangeByPosition(helper, first, helper, last_row).clearContents(CONTENT)
        sheet.getRows().removeByIndex(first + kept, len(blank))


def delete_blank_rows(host, selection):
    """Rows with no content anywhere in the used area, inside the selected rows (or the used area for one cell)."""
    if not _ready(host, selection):
        return
    sheet = host.controller.getActiveSheet()
    cursor = sheet.createCursor()
    cursor.gotoStartOfUsedArea(False)
    cursor.gotoEndOfUsedArea(True)
    used = cursor.getRangeAddress()
    ranges = _ranges(selection)
    runs, spans = _blank_runs(sheet, ranges, used, len(ranges) == 1 and _is_single_cell(ranges[0]))
    del ranges, selection  # no UNO ranges object may stay alive during the deletion
    if not runs:
        return host.say(T.MESSAGES["blank-none"])
    first, last = runs[0][0], spans[-1][1]
    area = sheet.getCellRangeByPosition(0, first, used.EndColumn, last)
    if len(runs) > NATIVE_LIMIT and len(spans) == 1 and _plain_data(host.doc, sheet, area):
        del area
        _delete_by_sort(host, sheet, runs, last, used.EndColumn)
    else:
        del area
        _delete_native(host, sheet, runs)
    host.controller.select(sheet.getCellRangeByPosition(0, first, 0, first))
    host.say(T.MESSAGES["blank-done"] % sum(count for _, count in runs))
