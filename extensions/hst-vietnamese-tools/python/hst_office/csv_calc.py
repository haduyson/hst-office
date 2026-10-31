# SPDX-License-Identifier: AGPL-3.0-only
"""Write parsed CSV rows into a Calc sheet as ONE undo step (uno objects are passed in).

Text mode (default) sets the Text number format on the destination first, so values like 00123, =1+1 or +84...
stay literal even if the user later edits the cell. Nothing is evaluated and no link is fetched. Refused before
any write: read-only document, protected sheet, destination outside the sheet, or non-empty destination
without explicit overwrite consent. A failure inside the write is rolled back through the undo manager.
"""
from .csv_import import typed_cell
from .undo import undo_step

TEXT_FORMAT = 4  # com.sun.star.util.NumberFormat.TEXT
CONTENT = 1 | 2 | 4 | 16  # VALUE | DATETIME | STRING | FORMULA


def destination_range(sheet, column, row, n_rows, n_cols):
    return sheet.getCellRangeByPosition(column, row, column + n_cols - 1, row + n_rows - 1)


def check_destination(doc, sheet, column, row, n_rows, n_cols, overwrite_ok):
    """Return (range_or_None, reasons). Reasons: read-only, sheet-protected, outside-sheet, overwrite-needed."""
    reasons = []
    if doc.isReadonly():
        reasons.append("read-only")
    if sheet.isProtected():
        reasons.append("sheet-protected")
    rng = None
    try:
        rng = destination_range(sheet, column, row, n_rows, n_cols)
    except Exception:  # noqa: BLE001 - IndexOutOfBounds from the UNO bridge means the data does not fit the sheet
        reasons.append("outside-sheet")
    if rng is not None and not reasons and rng.queryContentCells(CONTENT).getCount() and not overwrite_ok:
        reasons.append("overwrite-needed")
    return (rng if not reasons else None), reasons


def write_cells(sheet, column, row, rows, mode):
    """Per-cell writes: setString stores text literally (no parsing) and, unlike XCellRangeData.setDataArray,
    is reliably recorded by Calc's undo (setDataArray leaves the data in place on Undo, verified on 24.2)."""
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            if not value:
                continue
            kind, typed = typed_cell(value, mode)
            cell = sheet.getCellByPosition(column + c, row + r)
            cell.setString(typed) if kind == "s" else cell.setValue(typed)


def write_rows(doc, sheet, column, row, rows, mode="text", overwrite_ok=False, undo_title="Import CSV"):
    """Write `rows` at (column,row). Returns {'blockers': [...]} (nothing written) or {'blockers': [], 'cells': n}."""
    n_rows, n_cols = len(rows), len(rows[0])
    rng, reasons = check_destination(doc, sheet, column, row, n_rows, n_cols, overwrite_ok)
    if reasons:
        return {"blockers": reasons}
    import uno
    doc.lockControllers()  # no repaint per cell
    try:
        with undo_step(doc, undo_title):
            if mode == "text":
                locale = uno.createUnoStruct("com.sun.star.lang.Locale")
                rng.NumberFormat = doc.getNumberFormats().getStandardFormat(TEXT_FORMAT, locale)
            write_cells(sheet, column, row, rows, mode)
    finally:
        doc.unlockControllers()
    return {"blockers": [], "cells": n_rows * n_cols, "range": rng.AbsoluteName}
