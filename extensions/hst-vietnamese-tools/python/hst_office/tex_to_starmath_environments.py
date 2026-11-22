# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức: LaTeX environments with rows and columns (cases, array, aligned, matrices) for
tex_to_starmath. Rows end at \\\\, cells at &. One column becomes a stack, more become a matrix; every cell is
aligned as LaTeX aligns it: cases and array columns as declared ({ll}, {rcl}), aligned/split columns right then left
around each &, so "a &= b" lines up at the =, matrices centred. An empty cell (the left of "&= c") is empty text,
not an empty group: saved to .docx and opened again, an empty group would vanish and move the row's cells left."""
from . import tex_starmath_symbols as sym
from .tex_starmath_pieces import ORD, Piece, TexError, join

ALIGN = {"l": "alignl", "c": "alignc", "r": "alignr"}
ALIGNED = ("aligned", "align", "align*", "alignedat", "split", "eqnarray", "eqnarray*")


def _columns(name, reader):
    """Alignment of each column ("l"/"c"/"r"), repeated when a row has more cells; None for centred."""
    if name == "array":
        spec = reader.raw_group()
        letters = [c for c in spec if c in "lcr"]
        if not letters:
            raise TexError("array columns")
        return letters
    if name == "alignedat":
        reader.raw_group()
    if name in ALIGNED:
        return ["r", "l"]
    if name == "cases":
        return ["l", "l"]
    if name in ("gathered", "gather", "gather*"):
        return ["c"]
    return None


def _rows(reader, name):
    rows, cells = [], []
    while True:
        pieces, stop = reader.sequence(("&", "\\", "end"))
        cells.append(join(pieces))
        if stop == "&":
            continue
        rows.append(cells)
        cells = []
        if stop == "end":
            break
        if stop is None:
            raise TexError("\\begin{%s} without \\end" % name)
        reader._skip_optional()  # \\[2mm]
    if reader.raw_group().strip() != name:
        raise TexError("\\end does not match \\begin{%s}" % name)
    while rows and rows[-1] == [""]:  # a \\ before \end
        rows.pop()
    if not rows:
        raise TexError("empty %s" % name)
    return rows


def environment(reader, name):
    if name not in sym.MATRIX_FENCES:
        raise TexError("\\begin{%s}" % name)
    columns = _columns(name, reader)
    rows = _rows(reader, name)
    width = max(len(row) for row in rows)

    def cell(text, column):
        text = "{%s}" % text if text else '""'  # an empty group would not survive a .docx save and reopen
        if columns is None:
            return text
        return "%s %s" % (ALIGN[columns[column % len(columns)]], text)

    if width == 1:
        body = "stack{%s}" % " # ".join(cell(row[0], 0) for row in rows)
    else:
        body = "matrix{%s}" % " ## ".join(
            " # ".join(cell(row[c] if c < len(row) else "", c) for c in range(width)) for row in rows)
    fences = sym.MATRIX_FENCES[name]
    if fences is not None:
        body = "left %s %s right %s" % (fences[0], body, fences[1])
    return Piece(ORD, "{%s}" % body)
