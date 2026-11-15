# SPDX-License-Identifier: AGPL-3.0-only
"""Render a layout (hst_office.nd30_layout.build_layout) into Writer at the cursor, as ONE undo step.
Page layout (optional) is applied first and is not part of Undo, see nd30_page.

Grids become tables without cell padding; the horizontal rules are empty 1pt paragraphs whose indents centre a bottom
border of the computed width, exactly as the .ott renderer (scripts/templates/writer.py) writes them. Where it goes and
when it is refused: nd30_insertion (callers check it before opening the wizard; nothing is written with blockers).
"""
from . import nd30_insertion, nd30_page
from .nd30_layout import portable_blocks
from .nd30_text import PARAGRAPH_BREAK, border, format_paragraph, format_run, pt_to_mm100
from .undo import undo_step

RULE_RUN = {"text": "", "size": 1, "bold": False, "italic": False}
VALIGN = {"top": 1, "center": 2, "bottom": 3}  # com.sun.star.text.VertOrientation


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


def uno_page_before(kind="PAGE_BEFORE"):
    import uno
    return uno.Enum("com.sun.star.style.BreakType", kind)


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
        # LEFT_AND_WIDTH: a LEFT table keeps the full text width and ignores RightMargin (the 50 mm stamp spanned the page)
        table.HoriOrient, table.LeftMargin, table.Width = 7, 0, int(round(block["widthMm"] * 100))
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
    table.KeepTogether = bool(block.get("keep_with_next"))  # keep with the next paragraph
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


def _position(doc, text, view_cursor, point, flow):
    """The cursor to write at: at the cursor's paragraph (after the table holding it); at the end of the document for a
    copy block; or at its start."""
    if flow == "prepend":
        return _start_cursor(doc, text)
    if flow == "append":
        view_cursor.gotoEnd(False)  # a text cursor here: insertion_point refused every other selection
        cur = text.createTextCursorByRange(view_cursor.getStart())
    elif point["table"] is not None:
        return nd30_insertion.after_table(doc, text, point["table"])
    else:
        cur = text.createTextCursorByRange(point["range"].getStart())
    probe = text.createTextCursorByRange(cur)
    probe.gotoStartOfParagraph(False)
    probe.gotoEndOfParagraph(True)
    if probe.getString():
        cur.gotoEndOfParagraph(False)
        text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
    return cur


def _write_blocks(doc, text, cur, layout, blocks, section_style):
    text_mm = layout["textWidthMm"]
    for block in blocks:
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
            cur.BreakType = uno_page_before("NONE")


def _shrink_end(doc, text, cur, blocks):
    """The empty paragraph left after the inserted document (Writer keeps one after a closing table) is set to 1 pt and
    the document keeps with it, so it cannot spill onto a blank last page; only at the end of the document."""
    if not blocks:
        return
    probe = text.createTextCursorByRange(cur)
    probe.gotoStartOfParagraph(False)
    probe.gotoEndOfParagraph(True)
    end = text.createTextCursorByRange(cur)
    end.gotoEndOfParagraph(False)
    if probe.getString() or text.compareRegionEnds(end, text.getEnd()) != 0:
        return
    format_paragraph(probe, {"align": "left"}, 0)
    probe.CharHeight = 1.0
    if blocks[-1]["type"] == "paragraph" and probe.gotoPreviousParagraph(False):
        probe.ParaKeepTogether, probe.ParaBottomMargin = True, 0  # its space below would push the end paragraph over


def insert_layout(doc, view_cursor, layout, margins_mm=None, apply_page=False, page_numbers=True,
                  undo_title="Insert ND30 document"):
    """Insert `layout` after the cursor's paragraph (or into its empty paragraph) as one undo step; a copy block goes
    where its form says. Returns {'blockers': [...]} without writing if the insertion point is not acceptable, else
    'afterTable' tells that the document went after the table holding the cursor."""
    point = nd30_insertion.insertion_point(doc, doc.getCurrentController())
    if point["reasons"]:
        return {"blockers": point["reasons"]}
    text = doc.getText()
    flow = layout.get("flow")
    result = {"blockers": [], "page": None, "afterTable": point["table"] is not None and not flow}
    section_style = None
    blocks, footer = portable_blocks(layout)
    if layout.get("page"):
        result["page"] = nd30_page.apply_custom_page(doc, view_cursor, layout["page"])
    elif apply_page and not flow:  # before the undo step: page styles are not undoable (see nd30_page)
        result["page"] = nd30_page.apply_page_layout(doc, view_cursor, margins_mm, page_numbers, layout.get("profile", "nd30"), footer, layout["textWidthMm"])
        if page_numbers and not result["page"]["headerSkipped"] and any(b.get("new_section") for b in blocks):
            section_style = nd30_page.section_style(doc, view_cursor)
    if footer and not (result["page"] or {}).get("firstFooter"):
        blocks = blocks + [b for b in layout["blocks"] if b.get("role") == "Contact"]  # no footer of ours: under the signature
    with undo_step(doc, undo_title):
        cur = _position(doc, text, view_cursor, point, flow)
        _write_blocks(doc, text, cur, layout, blocks, section_style)
        _shrink_end(doc, text, cur, blocks)
    return result
