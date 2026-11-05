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
            # the space after a ruled paragraph belongs under the rule
            items = [({**block, "spacing_after_pt": 0}, False)]
            items.append(({**block, "runs": [RULE_RUN], "spacing_before_pt": 2, "align": "center",
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


def uno_page_before():
    import uno
    return uno.Enum("com.sun.star.style.BreakType", "PAGE_BEFORE")


def _plain_cell(cell, valign, borders):
    line = border(0.75 if borders else 0.0)
    for side in ("TopBorder", "BottomBorder", "LeftBorder", "RightBorder"):
        setattr(cell, side, line)
    distance = 50 if borders else 0
    cell.LeftBorderDistance = cell.RightBorderDistance = cell.TopBorderDistance = cell.BottomBorderDistance = distance
    cell.VertOrient = VALIGN[valign]


def _write_grid(doc, text, cur, block, text_mm, section_style=None):
    pcts = block["widthsPct"]
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(len(block["rows"]), len(pcts))
    text.insertTextContent(cur, table, False)
    if block.get("widthMm"):
        table.HoriOrient, table.LeftMargin, table.RightMargin = 3, 0, max(0, int((text_mm - block["widthMm"]) * 100))  # LEFT
    else:
        table.HoriOrient = 6  # FULL: stretch to the text area
    if block.get("new_section"):
        if section_style:
            table.PageDescName, table.PageNumberOffset = section_style, 1
        else:
            table.BreakType = uno_page_before()
    if block.get("repeatHeader"):
        table.RepeatHeadline, table.HeaderRowCount = True, 1
    table.TopMargin = pt_to_mm100(block.get("spacing_before_pt", 0))
    table.BottomMargin = pt_to_mm100(block.get("spacing_after_pt", 0))
    table.Split = block.get("name") != "Signature"
    separators, position = table.TableColumnSeparators, 0.0
    for index, pct in enumerate(pcts[:-1]):
        position += pct
        separators[index].Position = int(round(position * table.TableColumnRelativeSum / 100.0))
    table.TableColumnSeparators = separators
    for row_index, row in enumerate(block["rows"]):
        row_props = table.getRows().getByIndex(row_index)
        row_props.IsSplitAllowed = False
        if row.get("heightMm"):
            row_props.IsAutoHeight, row_props.Height = True, int(row["heightMm"] * 100)
        if row.get("merged"):
            selection = table.createCursorByCellName("A%d" % (row_index + 1))
            selection.goRight(len(pcts) - 1, True)
            selection.mergeRange()
        for column, (paragraphs, pct) in enumerate(zip(row["cells"], [100] if row.get("merged") else pcts)):
            cell = table.getCellByPosition(column, row_index)
            _plain_cell(cell, row.get("valign", "top"), block.get("borders", False))
            cell_text = cell.getText()
            cell_cursor = cell_text.createTextCursor()
            _write_paragraphs(cell_text, cell_cursor, paragraphs or [{"align": "left", "runs": [RULE_RUN]}], text_mm * pct / 100.0)


def _start_cursor(doc, text):
    """A cursor in a new paragraph before everything else: form 3.2 puts the signing line above the document."""
    first = text.createEnumeration().nextElement()
    if first.supportsService("com.sun.star.text.TextTable"):
        text.insertTextContentBefore(doc.createInstance("com.sun.star.text.Paragraph"), first)
        return text.createTextCursorByRange(text.getStart())
    cur = text.createTextCursorByRange(text.getStart())
    text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
    cur.goLeft(1, False)
    return cur


def _position(doc, text, view_cursor, flow):
    """The cursor to write at: at the cursor's paragraph; at the end of the document for a copy block; or at its start."""
    if flow == "prepend":
        return _start_cursor(doc, text)
    if flow == "append":
        view_cursor.gotoEnd(False)
    cur = text.createTextCursorByRange(view_cursor.getStart())
    probe = text.createTextCursorByRange(cur)
    probe.gotoStartOfParagraph(False)
    probe.gotoEndOfParagraph(True)
    if probe.getString():
        cur.gotoEndOfParagraph(False)
        text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
    return cur


def _write_blocks(doc, text, cur, layout, section_style):
    text_mm = layout["textWidthMm"]
    for block in layout["blocks"]:
        if block["type"] == "grid":
            _write_grid(doc, text, cur, block, text_mm, section_style)
            continue
        if block.get("new_section"):
            if section_style:
                cur.PageDescName, cur.PageNumberOffset = section_style, 1
            else:
                cur.BreakType = uno_page_before()
        _write_paragraphs(text, cur, [block], text_mm)
        text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
        if block.get("new_section"):
            cur.BreakType = uno_break_none()


def uno_break_none():
    import uno
    return uno.Enum("com.sun.star.style.BreakType", "NONE")


def insert_layout(doc, view_cursor, layout, margins_mm=None, apply_page=False, page_numbers=True,
                  undo_title="Insert ND30 document"):
    """Insert `layout` after the cursor's paragraph (or into its empty paragraph) as one undo step; a copy block goes
    where its form says. Returns {'blockers': [...]} without writing if the insertion point is not acceptable."""
    blockers = check_insertion_point(doc, view_cursor)
    if blockers:
        return {"blockers": blockers}
    text = doc.getText()
    result = {"blockers": [], "page": None}
    flow = layout.get("flow")
    section_style = None
    if layout.get("page"):
        result["page"] = nd30_page.apply_custom_page(doc, view_cursor, layout["page"])
    elif apply_page and not flow:  # before the undo step: page styles are not undoable (see nd30_page)
        result["page"] = nd30_page.apply_page_layout(doc, view_cursor, margins_mm, page_numbers, layout.get("profile", "nd30"))
        if page_numbers and not result["page"]["headerSkipped"] and any(b.get("new_section") for b in layout["blocks"]):
            section_style = nd30_page.section_style(doc, view_cursor)
    with undo_step(doc, undo_title):
        _write_blocks(doc, text, _position(doc, text, view_cursor, flow), layout, section_style)
    return result
