# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: read the recipient list the user chose (.xlsx, .xls, .ods, .csv) into a mail_merge_table.Table.

Spreadsheets open hidden in Sheets (read-only, no macros); the first filled row of the sheet holds the headers.
CSV is decoded here: UTF-8 (with or without BOM), else Windows-1258, the code page a Vietnamese Windows writes
"CSV" in; the separator is guessed. CSV values become numbers only when they look like one without a leading
zero (0901234567 stays text) and dd/mm/yyyy becomes a date, so the list reads the same as in Sheets."""
import datetime
import os
import re
import unicodedata

from . import mail_merge_format as fmt
from . import mail_merge_table as mt

SPREADSHEETS = (".xlsx", ".xls", ".ods", ".xlsm", ".fods")
CSV = (".csv", ".txt")
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:,\d+)?|-?[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?|-?(?:0|[1-9]\d*)\.\d+")
_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
DATE_FLAG = 2  # com.sun.star.util.NumberFormat.DATE (DATETIME includes it)


class SourceError(ValueError):
    """`code`: missing, unsupported, empty, unreadable (texts in mail_merge_texts)."""

    def __init__(self, code, detail=""):
        super().__init__("%s%s" % (code, ": " + detail if detail else ""))
        self.code, self.detail = code, detail


def csv_cell(text):
    """(kind, value) of one CSV value: ("number", float), ("date", day number), ("text", str) or ("", None)."""
    text = text.strip()
    if not text:
        return "", None
    if _NUMBER.fullmatch(text) and len(text.replace("-", "").replace(".", "").replace(",", "")) <= 15:
        dotted = re.fullmatch(r"-?[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?", text)  # 1.500.000 (vi grouping)
        if not dotted and "." in text:  # 1500.5: a dot as decimal point
            return fmt.COL_NUMBER, float(text)
        return fmt.COL_NUMBER, float(text.replace(".", "").replace(",", "."))
    match = _DATE.fullmatch(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            return fmt.COL_DATE, float((datetime.date(year, month, day) - fmt.NULL_DATE).days)
        except ValueError:
            pass
    return fmt.COL_TEXT, text


def decode_csv(raw):
    from . import csv_import
    try:
        return csv_import.decode_bytes(raw)[0]
    except csv_import.CsvError as exc:
        if exc.code != "invalid-utf8":
            raise SourceError("unreadable", exc.code) from exc
        # Windows-1258 writes tone marks as combining characters: compose them, as typed text is
        return unicodedata.normalize("NFC", raw.decode("cp1258", errors="replace"))


def table_from_grid(grid):
    """Table from rows of (kind, value) cells: the first non-empty row gives the headers; fully empty rows are
    dropped; a column that is not purely numbers or dates shows its values as text."""
    rows = [list(r) for r in grid if any(kind for kind, _ in r)]
    if len(rows) < 2:
        raise SourceError("empty")
    width = max(len(r) for r in rows)
    rows = [r + [("", None)] * (width - len(r)) for r in rows]
    headers = mt.clean_headers([v if k == fmt.COL_TEXT else fmt.plain_number(v) if k else "" for k, v in rows[0]])
    body = rows[1:]
    kinds = mt.column_kinds([[r[c][0] for r in body] for c in range(width)])
    values = []
    for r in body:
        values.append(tuple(v if kinds[c] != fmt.COL_TEXT or k in ("", fmt.COL_TEXT) else fmt.display(k, v)
                            for c, (k, v) in enumerate(r)))
    used = [c for c in range(width) if rows[0][c][0] or any(r[c] not in ("", None) for r in values)]
    return mt.Table([headers[c] for c in used], [kinds[c] for c in used], [tuple(r[c] for c in used) for r in values])


def read_csv(path):
    from . import csv_import
    with open(path, "rb") as handle:
        text = decode_csv(handle.read())
    try:
        rows = csv_import.parse(text, csv_import.suggest_delimiter(text))
    except csv_import.CsvError as exc:
        raise SourceError("unreadable", exc.code) from exc
    return table_from_grid([[csv_cell(v) for v in row] for row in rows])


def _load_hidden(ctx, path):
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        return PropertyValue(Name=name, Value=value)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    return desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0,
                                        (prop("Hidden", True), prop("ReadOnly", True), prop("MacroExecutionMode", 0)))


def _date_cells(sheet, area, formats):
    """{(column, row)} of the cells with a date format inside `area` (CellFormatRanges: few calls for a column)."""
    found = set()
    ranges = sheet.getCellRangeByPosition(area.StartColumn, area.StartRow, area.EndColumn, area.EndRow).CellFormatRanges
    for index in range(ranges.getCount()):
        part = ranges.getByIndex(index)
        try:
            kind = formats.getByKey(part.NumberFormat).Type
        except Exception:  # noqa: BLE001 - unknown format: not a date
            continue
        if kind & DATE_FLAG:
            a = part.RangeAddress
            found.update((c, r) for c in range(a.StartColumn, a.EndColumn + 1) for r in range(a.StartRow, a.EndRow + 1))
    return found


def sheet_grid(sheet, formats):
    cursor = sheet.createCursor()
    cursor.gotoStartOfUsedArea(False)
    cursor.gotoEndOfUsedArea(True)
    area = cursor.RangeAddress
    data = cursor.getDataArray()
    dates = _date_cells(sheet, area, formats)
    grid = []
    for r, row in enumerate(data):
        cells = []
        for c, value in enumerate(row):
            if isinstance(value, str):
                cells.append((fmt.COL_TEXT, value) if value.strip() else ("", None))
            else:
                date = (area.StartColumn + c, area.StartRow + r) in dates
                cells.append((fmt.COL_DATE if date else fmt.COL_NUMBER, float(value)))
        grid.append(cells)
    return grid


def read(ctx, path, sheet_name=None):
    """(Table, sheet names, sheet used). CSV has no sheets: ([], None)."""
    if not os.path.isfile(path):
        raise SourceError("missing", path)
    extension = os.path.splitext(path)[1].lower()
    if extension in CSV:
        return read_csv(path), [], None
    if extension not in SPREADSHEETS:
        raise SourceError("unsupported", extension)
    doc = _load_hidden(ctx, path)
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        raise SourceError("unreadable", path)
    try:
        names = list(doc.Sheets.ElementNames)
        name = sheet_name if sheet_name in names else names[0]
        return table_from_grid(sheet_grid(doc.Sheets.getByName(name), doc.NumberFormats)), names, name
    finally:
        doc.close(True)
