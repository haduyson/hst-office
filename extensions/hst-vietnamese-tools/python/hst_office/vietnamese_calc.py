# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets commands "Bỏ dấu", "Tách họ tên" and "Sắp xếp theo tên" (one undo step each; "Xóa dòng trống" is in
blank_rows_calc.py). Cells are read and written a whole range at a time (getDataArray/setDataArray)."""
from . import utilities_texts as T
from . import vietnamese_calc_logic as logic
from .undo import undo_step

STRING = 4  # com.sun.star.sheet.CellFlags.STRING


def _ranges(selection):
    if selection.supportsService("com.sun.star.sheet.SheetCellRanges"):
        return [selection.getByIndex(i) for i in range(selection.getCount())]
    return [selection]


def _is_single_cell(rng):
    a = rng.getRangeAddress()
    return a.StartColumn == a.EndColumn and a.StartRow == a.EndRow


def _table(host, selection):
    """One range: the selection, or the data region around a single selected cell; None for a multi-range selection."""
    ranges = _ranges(selection)
    if len(ranges) != 1:
        return None
    if not _is_single_cell(ranges[0]):
        return ranges[0]
    cursor = host.controller.getActiveSheet().createCursorByRange(ranges[0])
    cursor.collapseToCurrentRegion()
    return cursor


def _ready(host, selection):
    if selection is None:
        return host.say(T.MESSAGES["no-cells"], error=True)
    if host.controller.getActiveSheet().isProtected():
        return host.say(T.MESSAGES["protected"], error=True)
    return True


def remove_diacritics(host, selection):
    """Text constants of the selection lose their diacritics; numbers and formulas stay."""
    if not _ready(host, selection):
        return
    changed = 0
    with undo_step(host.doc, T.UNDO["diacritics"]):
        for rng in _ranges(selection):
            found = rng.queryContentCells(STRING)
            for index in range(found.getCount()):
                block = found.getByIndex(index)
                rows, count = logic.strip_rows(block.getDataArray())
                if count:
                    block.setDataArray(rows)
                    changed += count
    host.say(T.MESSAGES["diacritics-done"] % changed if changed else T.MESSAGES["diacritics-none"])


def split_name(host, selection):
    """Two new columns right of the name column: "Họ đệm" and "Tên" (headers when the column has one)."""
    if not _ready(host, selection):
        return
    table = _table(host, selection)
    if table is None:
        return host.say(T.MESSAGES["one-range"], error=True)
    a = table.getRangeAddress()
    if a.StartColumn != a.EndColumn and not _is_single_cell(_ranges(selection)[0]):
        return host.say(T.MESSAGES["one-column"], error=True)
    sheet = host.controller.getActiveSheet()
    column = a.StartColumn if a.StartColumn == a.EndColumn else _ranges(selection)[0].getRangeAddress().StartColumn
    values = [row[0] for row in sheet.getCellRangeByPosition(column, a.StartRow, column, a.EndRow).getDataArray()]
    header = len(values) > 1 and logic.looks_like_name_header(values[0])
    parts = logic.split_rows(values[1:] if header else values)
    with undo_step(host.doc, T.UNDO["split"]):
        sheet.getColumns().insertByIndex(column + 1, 2)
        first = a.StartRow
        if header:
            sheet.getCellRangeByPosition(column + 1, first, column + 2, first).setDataArray(((T.HEADER_FAMILY, T.HEADER_GIVEN),))
            first += 1
        if parts:
            sheet.getCellRangeByPosition(column + 1, first, column + 2, first + len(parts) - 1).setDataArray(parts)
    host.say(T.MESSAGES["split-done"] % sum(1 for p in parts if p[1]))


def _property(name, value):
    import uno
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name, prop.Value = name, value
    return prop


def _column_name(sheet, column):
    return sheet.getColumns().getByIndex(column).getName()


def sort_by_given_name(host, selection):
    """Rows of the table sorted by given name, then family name, in Vietnamese order; formats and formulas move with
    the rows (Calc's own sort on a temporary rank column)."""
    if not _ready(host, selection):
        return
    table = _table(host, selection)
    if table is None:
        return host.say(T.MESSAGES["one-range"], error=True)
    rows = table.getDataArray()
    header, full, parts = logic.name_columns(rows)
    if full is None and parts is None:
        return host.say(T.MESSAGES["sort-none"], error=True)
    body = rows[1:] if header else rows
    order = logic.sort_order(body, full, parts)
    rank = [0] * len(order)
    for position, index in enumerate(order):
        rank[index] = position
    a, sheet = table.getRangeAddress(), host.controller.getActiveSheet()
    first, helper = a.StartRow + (1 if header else 0), a.EndColumn + 1
    if first > a.EndRow:
        return host.say(T.MESSAGES["sort-none"], error=True)
    import uno
    with undo_step(host.doc, T.UNDO["sort"]):
        sheet.getColumns().insertByIndex(helper, 1)
        sheet.getCellRangeByPosition(helper, first, helper, a.EndRow).setDataArray(tuple((float(r),) for r in rank))
        field = uno.createUnoStruct("com.sun.star.table.TableSortField")
        field.Field, field.IsAscending = helper - a.StartColumn, True
        descriptor = (_property("SortFields", uno.Any("[]com.sun.star.table.TableSortField", (field,))),
                      _property("ContainsHeader", False))
        uno.invoke(sheet.getCellRangeByPosition(a.StartColumn, first, helper, a.EndRow), "sort", (descriptor,))
        sheet.getColumns().removeByIndex(helper, 1)
    used = (parts[1] if parts else full) + a.StartColumn
    host.say(T.MESSAGES["sort-done"] % (len(body), _column_name(sheet, used)))
