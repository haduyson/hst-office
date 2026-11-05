# SPDX-License-Identifier: AGPL-3.0-only
"""Render a layout (hst_office.nd30_layout.build_layout) into Writer at the cursor, as ONE undo step.
Page layout (optional) is applied first and is not part of Undo, see nd30_page.

Grids become tables without cell padding; the horizontal rules are empty 1pt paragraphs whose indents centre a bottom
border of the computed width, exactly as the .ott renderer (scripts/templates/writer.py) writes them. Callers must run
`check_insertion_point` first: nothing is written when it reports blockers.
"""
from . import nd30_page
from .nd30_text import PARAGRAPH_BREAK, border, format_paragraph, format_run, pt_to_mm100
from .undo import undo_step

RULE_RUN = {"text": "", "size": 1, "bold": False, "italic": False}
VALIGN = {"top": 1, "center": 2, "bottom": 3}  # com.sun.star.text.VertOrientation


def check_insertion_point(doc, view_cursor):
    """Reasons insertion is refused before any mutation: read-only, selection, not main body text."""
    reasons = []
    if doc.isReadonly():
        reasons.append("read-only")
    if view_cursor.getString():
        reasons.append("selection")  # replacing a selection silently is not allowed
    if view_cursor.getText() != doc.getText():
        reasons.append("not-body-text")  # table cell, frame, header/footer, footnote
    return reasons


def _write_paragraphs(text, cur, paragraphs, cell_mm):
    """Write paragraphs at `cur` (an empty paragraph); rule paragraphs follow their text paragraph."""
    first = True
    for block in paragraphs:
        items = [(block, False)]
        if block.get("rule_mm"):
            items.append(({**block, "runs": [RULE_RUN], "spacing_before_pt": 0, "spacing_after_pt": 0, "align": "center",
                           "line_spacing": 1.0, "line_exact_pt": None, "top_rule": False}, True))
        for item, rule in items:
            if not first:
                text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
            first = False
            format_paragraph(cur, item, cell_mm, bottom_rule=rule)
            for run in item["runs"]:
                if run["text"]:
                    text.insertString(cur, run["text"], True)
                format_run(cur, run)
                cur.collapseToEnd()


def _plain_cell(cell, valign, borders):
    line = border(0.75 if borders else 0.0)
    for side in ("TopBorder", "BottomBorder", "LeftBorder", "RightBorder"):
        setattr(cell, side, line)
    distance = 50 if borders else 0
    cell.LeftBorderDistance = cell.RightBorderDistance = cell.TopBorderDistance = cell.BottomBorderDistance = distance
    cell.VertOrient = VALIGN[valign]


def _write_grid(doc, text, cur, block, text_mm):
    pcts = block["widthsPct"]
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(len(block["rows"]), len(pcts))
    text.insertTextContent(cur, table, False)
    table.HoriOrient = 6  # FULL: stretch to the text area
    table.TopMargin = pt_to_mm100(block.get("spacing_before_pt", 0))
    table.BottomMargin = 0
    table.Split = block.get("name") != "Signature"
    separators, position = table.TableColumnSeparators, 0.0
    for index, pct in enumerate(pcts[:-1]):
        position += pct
        separators[index].Position = int(round(position * table.TableColumnRelativeSum / 100.0))
    table.TableColumnSeparators = separators
    for row_index, row in enumerate(block["rows"]):
        table.getRows().getByIndex(row_index).IsSplitAllowed = False
        for column, (paragraphs, pct) in enumerate(zip(row["cells"], pcts)):
            cell = table.getCellByPosition(column, row_index)
            _plain_cell(cell, row.get("valign", "top"), block.get("borders", False))
            cell_text = cell.getText()
            cell_cursor = cell_text.createTextCursor()
            _write_paragraphs(cell_text, cell_cursor, paragraphs or [{"align": "left", "runs": [RULE_RUN]}], text_mm * pct / 100.0)


def insert_layout(doc, view_cursor, layout, margins_mm=None, apply_page=False, page_numbers=True,
                  undo_title="Insert ND30 document"):
    """Insert `layout` after the cursor's paragraph (or into its empty paragraph) as one undo step.
    Returns {'blockers': [...]} without writing if the insertion point is not acceptable."""
    blockers = check_insertion_point(doc, view_cursor)
    if blockers:
        return {"blockers": blockers}
    text = doc.getText()
    result = {"blockers": [], "page": None}
    if apply_page:  # before the undo step: page styles are not undoable (see nd30_page)
        result["page"] = nd30_page.apply_page_layout(doc, view_cursor, margins_mm, page_numbers, layout.get("profile", "nd30"))
    with undo_step(doc, undo_title):
        cur = text.createTextCursorByRange(view_cursor.getStart())
        probe = text.createTextCursorByRange(cur)
        probe.gotoStartOfParagraph(False)
        probe.gotoEndOfParagraph(True)
        if probe.getString():
            cur.gotoEndOfParagraph(False)
            text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
        text_mm = layout["textWidthMm"]
        for block in layout["blocks"]:
            if block["type"] == "grid":
                _write_grid(doc, text, cur, block, text_mm)
            else:
                _write_paragraphs(text, cur, [block], text_mm)
                text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
    return result
