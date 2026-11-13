# SPDX-License-Identifier: AGPL-3.0-only
"""The cells of "Đọc số thành chữ" in Sheets: the source cell or column and the target column it writes to, read and
read a block at a time (getDataArray/getFormulaArray) and written cell by cell. Planning is pure
(number_words_range.py); this module only talks to the sheet."""
from . import utilities_texts as T
from .number_words_choice import formula
from .number_words_range import clip_rows, overlaps, parse_address, reference


def find_range(doc, sheet, address, allow_range=True):
    """The cell or cell range at `address` ("B2", "$B$2", "B2:B9", "Sheet2.B2"); ValueError with the user message."""
    parsed = parse_address(address, allow_range)
    if parsed is None:
        raise ValueError(T.MESSAGES["bad-cell"] % address)
    try:
        if parsed[0]:
            sheet = doc.getSheets().getByName(parsed[0])
        return sheet.getCellRangeByName(parsed[1])
    except Exception:  # noqa: BLE001 - unknown sheet or address outside the sheet
        raise ValueError(T.MESSAGES["bad-cell"] % address) from None


def column_name(sheet, column):
    return sheet.getColumns().getByIndex(column).getName()


def last_used_row(sheet):
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(False)
    return cursor.getRangeAddress().EndRow


def selection_fields(sheet, address):
    """(source text, target text) the dialog opens with: the selected cell or column, cut at the data, and the cell
    to the right of its first row. ValueError when several columns are selected."""
    if address.StartColumn != address.EndColumn:
        raise ValueError(T.MESSAGES["number-column"])
    first, last = clip_rows(address.StartRow, address.EndRow, last_used_row(sheet))
    column = column_name(sheet, address.StartColumn)
    source = "%s%d" % (column, first + 1) + (":%s%d" % (column, last + 1) if last > first else "")
    right = min(address.StartColumn + 1, sheet.getColumns().getCount() - 1)
    return source, "%s%d" % (column_name(sheet, right), first + 1)


class Job:
    """Where one run of the dialog reads and writes: `source` and `target` are one-column cell ranges of the same
    number of rows; `source_sheet_name` is set when the source lies on another sheet than the target."""

    def __init__(self, source, target, source_sheet_name):
        self.source, self.target, self.source_sheet_name = source, target, source_sheet_name

    def values(self):
        return [row[0] for row in self.source.getDataArray()]

    def existing(self):
        return [row[0] for row in self.target.getFormulaArray()]


def resolve(doc, sheet, choice):
    """The Job of the dialog's source and target fields; ValueError with the user message when they do not fit."""
    source = find_range(doc, sheet, choice["source"])
    target_cell = find_range(doc, sheet, choice["target"], allow_range=False)
    a, t = source.getRangeAddress(), target_cell.getRangeAddress()
    if a.StartColumn != a.EndColumn:
        raise ValueError(T.MESSAGES["number-column"])
    sheets = doc.getSheets()
    source_sheet, target_sheet = sheets.getByIndex(a.Sheet), sheets.getByIndex(t.Sheet)
    first, last = clip_rows(a.StartRow, a.EndRow, last_used_row(source_sheet))
    end = t.StartRow + last - first
    if end >= target_sheet.getRows().getCount():
        raise ValueError(T.MESSAGES["target-outside"])
    if overlaps((a.Sheet, a.StartColumn, first, last), (t.Sheet, t.StartColumn, t.StartRow, end)):
        raise ValueError(T.MESSAGES["target-overlap"])
    other = source_sheet.getName() if a.Sheet != t.Sheet else None
    return Job(source_sheet.getCellRangeByPosition(a.StartColumn, first, a.StartColumn, last),
               target_sheet.getCellRangeByPosition(t.StartColumn, t.StartRow, t.StartColumn, end), other)


def first_value(doc, sheet, text):
    """Value of the first cell of the typed source (preview): float, text, or "" when empty."""
    return find_range(doc, sheet, text).getCellByPosition(0, 0).getDataArray()[0][0]


def write(job, plan, choice, file_layer=None):
    """Write the planned rows: the words, or a DOCSO/DOCTIEN formula on each row's own source cell. Cell by cell:
    Calc does not undo setDataArray/setFormulaArray into cells that were empty (measured on HST Sheets 1.0.1,
    tests/runtime/check-vietnamese-calc-undo.py), and the whole column must go back with one undo. A formula leaves out what `file_layer`
    (the file's default) reads the same way. Call inside one undo step."""
    a = job.source.getRangeAddress()
    column = column_name(job.source.getSpreadsheet(), a.StartColumn) if choice["formula"] else ""
    for offset, text in plan.writes:
        cell = job.target.getCellByPosition(0, offset)
        if choice["formula"]:
            cell.setFormula(formula(choice, reference(column, a.StartRow + offset, job.source_sheet_name), file_layer))
        else:
            cell.setString(text)
