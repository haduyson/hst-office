# SPDX-License-Identifier: AGPL-3.0-only
"""Convert legacy-encoded text cells of a Calc selection to Unicode as ONE undo step (UNO objects are passed in).

Bulk path: each block of string cells with one font is read with getDataArray, converted, and written back with
setDataArray (formulas, numbers, dates and empty cells are never part of a block). Cells holding rich text (several
formatting runs) are converted run by run so their formatting survives. Legacy fonts become the Unicode equivalent
the Writer path uses. Formula cells are only counted. Optional: sheet names and comments (notes).
"""
from . import encoding_calc_ranges as rg
from .encoding import font_policy
from .encoding_writer import plan, rewrite_portion
from .undo import undo_step

STRING, FORMULA, FORMATTED = 4, 16, 512  # com.sun.star.sheet.CellFlags
SAMPLE_CELLS = 300


def check(doc, sheet_indexes):
    reasons = []
    if doc.isReadonly():
        reasons.append("read-only")
    if any(doc.Sheets.getByIndex(i).isProtected() for i in sheet_indexes):
        reasons.append("sheet-protected")
    return reasons


def selection_rects(selection):
    """Rects of a cell/range/ranges selection, or None for any other selection (shapes, text ...)."""
    if selection is None:
        return None
    if selection.supportsService("com.sun.star.sheet.SheetCellRanges"):
        addresses = selection.getRangeAddresses()
    elif selection.supportsService("com.sun.star.sheet.SheetCellRange"):
        addresses = [selection.getRangeAddress()]
    else:
        return None
    return [(a.Sheet, a.StartColumn, a.StartRow, a.EndColumn, a.EndRow) for a in addresses]


def used_area(doc, sheet_index):
    cursor = doc.Sheets.getByIndex(sheet_index).createCursor()
    cursor.gotoEndOfUsedArea(False)
    address = cursor.getRangeAddress()
    return address.EndColumn, address.EndRow


def target_rects(doc, rects, whole_sheet_index=None):
    """Disjoint rects clipped to the used area; `whole_sheet_index` replaces the selection by that sheet's used area."""
    if whole_sheet_index is not None:
        rects = [(whole_sheet_index, 0, 0, 1 << 30, 1 << 30)]
    used = {i: used_area(doc, i) for i in {r[0] for r in rects}}
    return rg.normalize(rects, used)


def _range(doc, rect):
    return doc.Sheets.getByIndex(rect[0]).getCellRangeByPosition(*rect[1:])


def _query(doc, rects, flags):
    """Disjoint rects of cells holding `flags` content inside `rects`."""
    found = []
    for rect in rects:
        for a in _range(doc, rect).queryContentCells(flags).getRangeAddresses():
            found.append((a.Sheet, a.StartColumn, a.StartRow, a.EndColumn, a.EndRow))
    return found


def _uniform_font(doc, rect):
    """Yield (rect, font name) splitting `rect` until each part has one font (a mixed range, flagged AMBIGUOUS_VALUE, is halved)."""
    target = _range(doc, rect)
    s, c0, r0, c1, r1 = rect
    if (c0 == c1 and r0 == r1) or target.getPropertyState("CharFontName").value != "AMBIGUOUS_VALUE":
        yield rect, target.CharFontName
    elif r1 > r0:
        mid = (r0 + r1) // 2
        yield from _uniform_font(doc, (s, c0, r0, c1, mid))
        yield from _uniform_font(doc, (s, c0, mid + 1, c1, r1))
    else:
        mid = (c0 + c1) // 2
        yield from _uniform_font(doc, (s, c0, r0, mid, r1))
        yield from _uniform_font(doc, (s, mid + 1, r0, c1, r1))


def sample(doc, rects, limit=SAMPLE_CELLS):
    """First text cells as [{'text','font'}] for the wizard preview (no writes)."""
    items = []
    for rect in _query(doc, rects, STRING):
        for part in rg.chunks(rect, limit):
            for row in _range(doc, part).getDataArray():
                items += [{"text": v, "font": ""} for v in row if isinstance(v, str) and v]
            if len(items) >= limit:
                return items[:limit]
    return items


def _rich_items(cell):
    """Text runs of a cell with in-cell formatting (rich text), as plan() items."""
    items = []
    paragraphs = cell.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        portions = paragraphs.nextElement().createEnumeration()
        while portions.hasMoreElements():
            run = portions.nextElement()
            if run.TextPortionType == "Text":
                items.append({"range": run, "text": run.getString(), "font": run.CharFontName})
    return items


def _rich_positions(target, rect):
    """{(row, col)} relative to rect of cells with in-cell formatting (CellFlags.FORMATTED = edit-text cells: one query, no per-cell cost)."""
    found = set()
    for a in target.queryContentCells(FORMATTED).getRangeAddresses():
        found.update((r - rect[2], c - rect[1]) for r in range(a.StartRow, a.EndRow + 1) for c in range(a.StartColumn, a.EndColumn + 1))
    return found


def _convert_chunk(doc, rect, key, font, convert):
    """Convert one chunk; returns number of cells changed."""
    upper, new_font = font_policy(key, font)
    target = _range(doc, rect)
    new_grid, changed = rg.convert_grid(target.getDataArray(), convert, upper)
    sheet = doc.Sheets.getByIndex(rect[0])
    formatted = _rich_positions(target, rect)
    rich = changed & formatted
    for row, col in sorted(rich):  # rich cells are converted run by run so bold/italic/colour survive
        rows, _ = plan(_rich_items(sheet.getCellByPosition(rect[1] + col, rect[2] + row)), key)
        for item in reversed([r for r in rows if r["new"] != r["text"] or r["new_font"]]):
            rewrite_portion(item)
    if changed:
        for col, first, last in rg.runs(len(new_grid), len(new_grid[0]), rich):
            piece = sheet.getCellRangeByPosition(rect[1] + col, rect[2] + first, rect[1] + col, rect[2] + last)
            piece.setDataArray(tuple((new_grid[r][col],) for r in range(first, last + 1)))
    if new_font:  # a cell-level font change would strip the in-cell formatting of rich cells, so they are skipped
        for col, first, last in rg.runs(rect[4] - rect[2] + 1, rect[3] - rect[1] + 1, formatted):
            sheet.getCellRangeByPosition(rect[1] + col, rect[2] + first, rect[1] + col, rect[2] + last).CharFontName = new_font
    return len(changed)


def _extras(doc, rects, convert):
    """Sheet names and comments (notes) of the sheets touched; returns (names changed, notes changed)."""
    names = notes = 0
    for index in sorted({r[0] for r in rects}):
        sheet = doc.Sheets.getByIndex(index)
        annotations = sheet.getAnnotations()
        for i in range(annotations.getCount()):
            note = annotations.getByIndex(i)
            position = note.getPosition()
            new = convert(note.getString()) if rg.contains(rects, index, position.Column, position.Row) else None
            if new is not None and new != note.getString():
                note.setString(new)
                notes += 1
        new_name = convert(sheet.Name)
        if new_name != sheet.Name and not doc.Sheets.hasByName(new_name):
            try:
                sheet.Name = new_name
                names += 1
            except Exception:  # noqa: BLE001 - an invalid name leaves the sheet name unchanged
                pass
    return names, notes


def apply(doc, rects, key, names_and_notes=False, progress=None, undo_title="Chuyển mã"):
    """Convert text cells in the disjoint `rects`; returns {'cells','formulas','unicode','names','notes'}."""
    convert = rg.TextConverter(key)
    blocks = _query(doc, rects, STRING)
    formulas = rg.cell_count(_query(doc, rects, FORMULA))
    total, done, cells = rg.cell_count(blocks), 0, 0
    if progress:
        progress.start(total)
    try:
        with undo_step(doc, undo_title):
            for block in blocks:
                for part, font in _uniform_font(doc, block):
                    for piece in rg.chunks(part):
                        cells += _convert_chunk(doc, piece, key, font, convert)
                        done += rg.cell_count([piece])
                        if progress:
                            progress.update(done)
            names, notes = _extras(doc, rects, convert) if names_and_notes else (0, 0)
    finally:
        if progress:
            progress.end()
    return {"cells": cells, "formulas": formulas, "unicode": convert.unicode_skipped, "names": names, "notes": notes}
