# SPDX-License-Identifier: AGPL-3.0-only
"""Pure range and grid logic for converting legacy Vietnamese text in Calc (no `uno`).

A rect is (sheet, first_col, first_row, last_col, last_row), all inclusive and zero based. A selection may hold
overlapping ranges (or whole columns/rows); `normalize` clips them to the used area and makes them disjoint so no
cell is converted twice (converting twice would corrupt the text).
"""
from .encoding import Converter


def clip(rect, used):
    """Clip a rect to the used area of its sheet: used = {sheet: (last_col, last_row)}. None when nothing is left."""
    sheet, c0, r0, c1, r1 = rect
    last_col, last_row = used.get(sheet, (0, 0))
    c1, r1 = min(c1, last_col), min(r1, last_row)
    return (sheet, c0, r0, c1, r1) if c0 <= c1 and r0 <= r1 else None


def _subtract(a, b):
    """Pieces of rect `a` not covered by rect `b`."""
    if a[0] != b[0] or b[1] > a[3] or b[3] < a[1] or b[2] > a[4] or b[4] < a[2]:
        return [a]
    sheet, c0, r0, c1, r1 = a
    pieces = []
    if b[2] > r0:
        pieces.append((sheet, c0, r0, c1, b[2] - 1))
    if b[4] < r1:
        pieces.append((sheet, c0, b[4] + 1, c1, r1))
    top, bottom = max(r0, b[2]), min(r1, b[4])
    if b[1] > c0:
        pieces.append((sheet, c0, top, b[1] - 1, bottom))
    if b[3] < c1:
        pieces.append((sheet, b[3] + 1, top, c1, bottom))
    return pieces


def normalize(rects, used):
    """Clip every rect to the used area and return pairwise disjoint rects covering the same cells."""
    result = []
    for rect in rects:
        pieces = [r for r in [clip(rect, used)] if r]
        for existing in result:
            pieces = [p for piece in pieces for p in _subtract(piece, existing)]
        result.extend(pieces)
    return result


def cell_count(rects):
    return sum((c1 - c0 + 1) * (r1 - r0 + 1) for _, c0, r0, c1, r1 in rects)


def contains(rects, sheet, col, row):
    return any(s == sheet and c0 <= col <= c1 and r0 <= row <= r1 for s, c0, r0, c1, r1 in rects)


def chunks(rect, limit=10000):
    """Split a rect into row slices of at most `limit` cells each (progress granularity, bounded array size)."""
    sheet, c0, r0, c1, r1 = rect
    rows = max(1, limit // (c1 - c0 + 1))
    for start in range(r0, r1 + 1, rows):
        yield (sheet, c0, start, c1, min(r1, start + rows - 1))


def runs(rows, cols, excluded):
    """Vertical runs (col, first_row, last_row) of a rows x cols grid that avoid the `excluded` {(row, col)} cells."""
    for col in range(cols):
        start = None
        for row in range(rows + 1):
            free = row < rows and (row, col) not in excluded
            if free and start is None:
                start = row
            elif not free and start is not None:
                yield col, start, row - 1
                start = None


class TextConverter:
    """Cached string converter: repeated cell texts (common in data columns) are converted once."""

    def __init__(self, key):
        self.key, self.conv, self.memo, self.unicode_skipped = key, Converter(key), {}, 0

    def __call__(self, text, upper=False):
        hit = self.memo.get((text, upper))
        if hit is None:
            new, stats = self.conv.convert(text, upper=upper)
            hit = self.memo[(text, upper)] = (new, stats["skipped_unicode"])
        self.unicode_skipped += hit[1]
        return hit[0]


def convert_grid(grid, convert, upper=False):
    """Convert the text cells of a getDataArray grid. Numbers (float) and empty strings are left alone.
    Returns (new_grid as list of lists, changed {(row, col)})."""
    out, changed = [], set()
    for r, row in enumerate(grid):
        new_row = list(row)
        for c, value in enumerate(row):
            if isinstance(value, str) and value:
                new = convert(value, upper)
                if new != value:
                    new_row[c] = new
                    changed.add((r, c))
        out.append(new_row)
    return out, changed
