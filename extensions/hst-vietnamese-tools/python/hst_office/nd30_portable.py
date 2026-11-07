# SPDX-License-Identifier: AGPL-3.0-only
"""The layout blocks as both renderers (.ott templates, wizard) write them, so long documents and their DOCX/DOC copies
keep their layout page after page (pure logic, no `uno`)."""


SECTION_START_PT = 0.1  # 0.04 mm: the paragraph carrying the page break of an attached document takes no visible room


def _gap(pt):
    """An empty paragraph of `pt` in all: its own line of SECTION_START_PT and the rest as space under it."""
    return {"type": "paragraph", "align": "left", "runs": [{"text": "", "size": 1, "bold": False, "italic": False}],
            "role": "TableGap", "line_exact_pt": SECTION_START_PT, "spacing_after_pt": round(pt - SECTION_START_PT, 2)}


def _shift(block, key, pt):
    return {**block, key: block.get(key, 0) + pt}


def _cells_edge(grid, pt, first):
    """Add `pt` before the first (or after the last) paragraph of every cell of the first (or last) row."""
    rows = [dict(r) for r in grid["rows"]]
    index, key = (0, "spacing_before_pt") if first else (-1, "spacing_after_pt")
    cells = []
    for cell in rows[index]["cells"]:
        if not cell:
            cells.append(cell)
            continue
        cell = list(cell)
        cell[0 if first else -1] = _shift(cell[0 if first else -1], key, pt)
        cells.append(cell)
    rows[index] = {**rows[index], "cells": cells}
    return {**grid, "rows": rows}


def portable_blocks(layout):
    """The blocks as both renderers write them, so a DOCX or DOC copy lays out like the original:

    - a table carries no space above or below (Word has no such property, the space was lost on export): the space goes to
      the paragraph next to it, or into the first/last paragraph of the cells of a borderless table; the space above a
      borderless table that follows a paragraph goes to an empty gap paragraph of its own between them, which stays at
      the foot of the page when the table moves on, so a signature block that opens a page starts at the top margin (in
      a cell the space would stay at the top of the page, and on the paragraph before every paragraph typed after it
      would copy it);
    - a page break that starts an attached document sits on an empty paragraph, not on a table (the DOC filter drops a
      page break carried by a table); its fixed line height is too small to see, so the header block of the attached
      document starts at the top margin like the one on page 1;
    - a closing table keeps with the empty paragraph Writer adds after it (no blank last page);
    - the contact details of an official letter (Decree 30, Annex I, I.III.4: on the first page) are returned apart, for
      the first-page footer.
    Returns (blocks, first_page_footer_blocks)."""
    footer = [{**b, "spacing_before_pt": 0} for b in layout["blocks"] if b.get("role") == "Contact"]
    blocks = []
    for b in layout["blocks"]:
        if b.get("role") == "Contact":
            continue
        if b["type"] == "grid" and b.get("new_section"):
            blocks.append({"type": "paragraph", "align": "left", "runs": [{"text": "", "size": 1, "bold": False, "italic": False}],
                           "role": "SectionStart", "line_exact_pt": SECTION_START_PT, "new_section": True})
            b = {k: v for k, v in b.items() if k != "new_section"}
        blocks.append(b)
    out = []
    for i, b in enumerate(blocks):
        if b["type"] != "grid":
            out.append(b)
            continue
        before, after = b.get("spacing_before_pt", 0), b.get("spacing_after_pt", 0)
        b = {k: v for k, v in b.items() if k not in ("spacing_before_pt", "spacing_after_pt")}
        if before:
            if out and out[-1]["type"] == "paragraph" and b.get("borders"):
                out[-1] = _shift(out[-1], "spacing_after_pt", before)
            elif out and out[-1]["type"] == "paragraph":
                out.append(_gap(before))
            else:
                b = _cells_edge(b, before, True)
        if after:
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt is not None and nxt["type"] == "paragraph":
                blocks[i + 1] = _shift(nxt, "spacing_before_pt", after)
            elif not b.get("borders"):
                b = _cells_edge(b, after, False)
        out.append(b)
    if out and out[-1]["type"] == "grid" and out[-1].get("name") == "Signature":
        # Writer keeps an empty paragraph after a closing table: the signature block (never split) goes with it, so it
        # cannot leave that paragraph alone on a blank page. Not for a register table: the DOCX filter writes a table's
        # keep-with-next on every row, which glues a long register into one block that can no longer split.
        out[-1] = {**out[-1], "keep_with_next": True}
    # Word has no table property for it: it keeps a table with the next paragraph when its last row keeps with next
    return [_keep_last_row(b) if b["type"] == "grid" and b.get("keep_with_next") else b for b in out], footer


def _keep_last_row(grid):
    rows = list(grid["rows"])
    rows[-1] = {**rows[-1], "cells": [[{**p, "keep_with_next": True} for p in cell] for cell in rows[-1]["cells"]]}
    return {**grid, "rows": rows}
    return out, footer
