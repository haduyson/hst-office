# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the recipient list in memory. Pure Python (no UNO), shared by the dialogs, the preview and the staging
copy the engine merges from.

A Table has `headers`, a column kind per header (mail_merge_format COL_*) and `rows` of values: str for text,
float for numbers and dates (spreadsheet day numbers), None for empty cells. Each row has a stable key (its content
hash plus a counter for identical rows) so the choice of recipients survives a re-read of the file and a new
sort order. The document stores the keys of the recipients the user unchecked, never the data itself."""
import hashlib
import re

from . import mail_merge_format as fmt
from .vietnamese_text import name_sort_key, remove_diacritics, sort_key

FILE_COLUMN = "Tên tệp (HST)"  # computed column the engine names separate files from
SORT_FILE, SORT_GIVEN_NAME = "", "\x00given"  # file order / by given name (Vietnamese), else a header name
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_PATTERN = re.compile(r"\{([^{}]+)\}")
MAX_FILE_NAME = 120


class Table:
    def __init__(self, headers, kinds, rows):
        self.headers, self.kinds, self.rows = list(headers), list(kinds), [tuple(r) for r in rows]
        self.keys = row_keys(self.rows)

    def column(self, header):
        return self.headers.index(header)

    def kind(self, header):
        return self.kinds[self.column(header)]

    def value(self, row, header):
        return row[self.column(header)]

    def text(self, row, header):
        index = self.column(header)
        return fmt.display(self.kinds[index], row[index])


def clean_headers(raw):
    """Header texts trimmed; an empty or repeated header becomes "Cột n" (n = column number) so every column can
    be inserted as a field."""
    result = []
    for index, name in enumerate(raw):
        name = " ".join(str(name or "").split())
        if not name or name in result or name == FILE_COLUMN:
            name = "Cột %d" % (index + 1)
        result.append(name)
    return result


def column_kinds(cells_by_column):
    """Kind of each column from the cell kinds read ("text", "number", "date", "" = empty): number or date only
    when every filled cell is one, else text (a phone number typed as text keeps its leading zero)."""
    kinds = []
    for cells in cells_by_column:
        filled = {kind for kind in cells if kind}
        kinds.append(filled.pop() if len(filled) == 1 and filled <= {fmt.COL_NUMBER, fmt.COL_DATE} else fmt.COL_TEXT)
    return kinds


def row_keys(rows):
    seen, keys = {}, []
    for row in rows:
        digest = hashlib.sha1(repr(row).encode("utf-8")).hexdigest()[:12]
        seen[digest] = seen.get(digest, 0) + 1
        keys.append("%s-%d" % (digest, seen[digest]))
    return keys


def _name_column(table):
    for header in table.headers:
        plain = remove_diacritics(header).lower()
        if plain in ("ho va ten", "ho ten", "ten", "full name", "name", "nguoi nhan"):
            return header
    return None


def order(table, by=SORT_FILE, descending=False):
    """Row indexes in the chosen order: file order, a column (Vietnamese collation, numbers by value) or by given
    name then family name (the column "Họ và tên"/"Họ tên"/"Tên" found by its header)."""
    indexes = list(range(len(table.rows)))
    if by == SORT_GIVEN_NAME:
        header = _name_column(table)
        if header is None:
            return indexes
        column = table.column(header)
        indexes.sort(key=lambda i: name_sort_key(str(table.rows[i][column] or "")), reverse=descending)
    elif by in table.headers:
        column, kind = table.column(by), table.kind(by)
        if kind == fmt.COL_TEXT:
            indexes.sort(key=lambda i: sort_key(str(table.rows[i][column] or "")), reverse=descending)
        else:
            indexes.sort(key=lambda i: (table.rows[i][column] is None, table.rows[i][column] or 0), reverse=descending)
    elif descending:
        indexes.reverse()
    return indexes


def matches(table, row, text):
    """Search without diacritics or case: "ngoc" finds "Trần Thị Bích Ngọc"."""
    needle = remove_diacritics(text or "").lower().strip()
    if not needle:
        return True
    return any(needle in remove_diacritics(table.text(row, h)).lower() for h in table.headers)


def checked_indexes(table, excluded, by=SORT_FILE, descending=False):
    """Indexes of the recipients that take part, in the chosen order."""
    skip = set(excluded or ())
    return [i for i in order(table, by, descending) if table.keys[i] not in skip]


def pattern_columns(pattern):
    return _PATTERN.findall(pattern or "")


def file_name(pattern, table, row):
    """File name (without extension) from a pattern such as "Giấy mời - {Họ và tên}"; unknown {names} stay as typed,
    characters no file system accepts become "-"."""
    def value(match):
        name = match.group(1).strip()
        return table.text(row, name) if name in table.headers else match.group(0)
    text = _UNSAFE.sub("-", _PATTERN.sub(value, pattern or ""))
    text = " ".join(text.split()).strip(" .")[:MAX_FILE_NAME].strip(" .")
    return text or "Văn bản"


def unique_names(names):
    """Second and later equal names get " (2)", " (3)", … (compared without case: Windows and macOS)."""
    seen, result = {}, []
    for name in names:
        count = seen.get(name.lower(), 0) + 1
        seen[name.lower()] = count
        result.append(name if count == 1 else "%s (%d)" % (name, count))
    return result


def staging(table, indexes, pattern="", words=None):
    """(headers, kinds, rows) of the copy the engine merges from: the chosen rows in order, plus for each number
    column its two word columns and, with a pattern, the file-name column."""
    numbers = [h for h, k in zip(table.headers, table.kinds) if k == fmt.COL_NUMBER]
    extra = [fmt.word_column(h, kind) for h in numbers for kind in (fmt.WORDS, fmt.MONEY_WORDS)]
    headers = table.headers + extra + [FILE_COLUMN]
    kinds = table.kinds + [fmt.COL_TEXT] * (len(extra) + 1)
    names = unique_names([file_name(pattern, table, table.rows[i]) for i in indexes])
    rows = []
    for name, index in zip(names, indexes):
        row = table.rows[index]
        computed = [fmt.render(kind, table.value(row, h), words) for h in numbers for kind in (fmt.WORDS, fmt.MONEY_WORDS)]
        rows.append(tuple(row) + tuple(computed) + (name,))
    return headers, kinds, rows
