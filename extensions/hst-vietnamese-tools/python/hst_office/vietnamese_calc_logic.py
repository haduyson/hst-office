# SPDX-License-Identifier: AGPL-3.0-only
"""Pure decisions of the Sheets utilities (no uno): blank row runs, header and name-column detection, sort order."""
import re

from . import vietnamese_text

FUNCTION_NAMES = ("DOCSO", "DOCTIEN", "BODAU", "TACHHO", "TACHTEN")  # the Sheets functions of calc_functions.py
# in a formula text: "=DOCSO(A1)", and the programmatic form "ORG.HST.OFFICE.VI.CALCFUNCTIONS.DOCSO(A1)"
USES_HST_FUNCTION = re.compile(r"\b(%s)\s*\(" % "|".join(FUNCTION_NAMES), re.I)


def functions_used(formulas):
    """HST function names used in the given formula texts, in FUNCTION_NAMES order."""
    found = set()
    for text in formulas:
        found.update(name.upper() for name in USES_HST_FUNCTION.findall(text or ""))
    return sorted(found, key=FUNCTION_NAMES.index)


def blank_runs(first_row, last_row, content_rows):
    """[(start, count)] of the rows in first_row..last_row covered by none of the (start, end) row intervals of the
    cells with content, in ascending order. Few intervals (Calc returns one per block), so 50 000 rows stay instant."""
    runs, row = [], first_row
    for start, end in sorted(content_rows):
        if end < row:
            continue
        if start > last_row:
            break
        if start > row:
            runs.append((row, start - row))
        row = max(row, end + 1)
    if row <= last_row:
        runs.append((row, last_row - row + 1))
    return runs


def _plain(value):
    return vietnamese_text.remove_diacritics(value).strip().lower() if isinstance(value, str) else ""


def looks_like_name_header(value):
    """"Họ và tên", "Họ tên", "Tên", "Full name" … (any case, with or without diacritics)."""
    text = _plain(value)
    return bool(text) and ("ten" in text.split() or "name" in text)


def name_columns(rows):
    """(has header, column of the full name or None, (family column, given column) or None) for a table given as rows
    of cell values. Two columns: headers "Họ đệm"/"Họ và đệm" left of "Tên". Without a header: the first column that
    holds mostly text."""
    if not rows:
        return False, None, None
    header = [_plain(v) for v in rows[0]]
    for index, text in enumerate(header):
        if text in ("ten", "given name", "first name") and index and header[index - 1].startswith("ho"):
            return True, None, (index - 1, index)
    for index, value in enumerate(rows[0]):
        if looks_like_name_header(value):
            return True, index, None
    body = rows[1:] if len(rows) > 1 else rows
    for index in range(len(rows[0])):
        values = [r[index] for r in body if r[index] not in ("", None)]
        if values and sum(isinstance(v, str) for v in values) * 2 > len(values):
            return False, index, None
    return False, None, None


def sort_order(rows, full_column=None, parts=None):
    """Row indexes of `rows` sorted by given name, then family name (stable: equal names keep their order)."""
    def key(index):
        row = rows[index]
        if parts:
            return vietnamese_text.name_sort_key(family=str(row[parts[0]]), given=str(row[parts[1]]))
        return vietnamese_text.name_sort_key(str(row[full_column]))
    return sorted(range(len(rows)), key=key)


def split_rows(values):
    """((họ đệm, tên), …) for the cell values of a name column (non-text cells give empty parts)."""
    return tuple(vietnamese_text.split_name(v) if isinstance(v, str) else ("", "") for v in values)


def strip_rows(rows):
    """(new rows, changed cell count) with diacritics removed from every text value."""
    changed, result = 0, []
    for row in rows:
        new = tuple(vietnamese_text.remove_diacritics(v) if isinstance(v, str) else v for v in row)
        changed += sum(a != b for a, b in zip(row, new))
        result.append(new)
    return tuple(result), changed
