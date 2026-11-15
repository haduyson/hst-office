# SPDX-License-Identifier: AGPL-3.0-only
"""Pure planning of "Đọc số thành chữ" over a column of cells (Sheets): which address the user typed, which rows get
words, which are skipped and how many targets already hold data.

A source is one cell or one column of cells ("A2", "A2:A20"); each row's words go to the same row of the target
column, starting at the target cell. A source of several columns is refused: writing next to its first column would
land inside the selection itself (the second column), so no choice there is predictable."""
import re

from . import number_words
from .number_words_choice import words

_CELL = r"\$?[A-Za-z]{1,3}\$?[0-9]{1,7}"
_ADDRESS = re.compile(r"^(?:\$?'?([^.']+)'?\.)?(%s(?::%s)?)$" % (_CELL, _CELL))
_EMPTY = (None, "")


def parse_address(text, allow_range=True):
    """(sheet name or None, "A2" or "A2:A20" without $) of a typed address; None when it is not one."""
    match = _ADDRESS.match((text or "").strip())
    if not match or (":" in match.group(2) and not allow_range):
        return None
    return match.group(1), match.group(2).replace("$", "").upper()


def clip_rows(start, end, last_used):
    """Rows start..end cut at the last used row of the sheet (a whole selected column ends at the data); at least
    the first row stays, so an empty selection still names its first cell."""
    return start, max(start, min(end, last_used))


def overlaps(source, target):
    """True when two (sheet, column, first row, last row) blocks share a cell."""
    return source[:2] == target[:2] and source[2] <= target[3] and target[2] <= source[3]


class Plan:
    """writes: [(row offset, words)]; skipped: non-empty cells that are not a readable number (or have more than 15
    digits); occupied: rows to write whose target cell already holds something; error: the first such reading error."""

    def __init__(self):
        self.writes, self.skipped, self.occupied, self.error = [], 0, 0, None


def plan(values, existing, choice):
    """Plan the rows of a column: `values` are the source cells (getDataArray: float, str, "" when empty),
    `existing` the target cells' formulas ("" when empty). Empty source cells are left alone."""
    result = Plan()
    for offset, value in enumerate(values):
        if value in _EMPTY or (isinstance(value, str) and not value.strip()):
            continue
        try:
            text = words(value, choice)  # also checks the value when a formula is written
        except number_words.NumberWordsError as exc:
            result.skipped += 1
            result.error = result.error or exc
            continue
        result.writes.append((offset, text))
        if offset < len(existing) and existing[offset] not in _EMPTY:
            result.occupied += 1
    return result


def reference(column, row, sheet=None):
    """A1 reference of a source cell for a formula: "A5", or "'Sheet 2'.A5" when the source is on another sheet."""
    cell = "%s%d" % (column, row + 1)
    return "'%s'.%s" % (sheet.replace("'", "''"), cell) if sheet else cell
