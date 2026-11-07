# SPDX-License-Identifier: AGPL-3.0-only
"""Apply A4 + ND30 margins (and page numbers hidden on the first page) to the current Writer page style.

ND30 I.1 A4; I.3 margins top/bottom 20-25, left 30-35, right 15-20 mm; I.7 page number centred in the top
margin, size 13-14, not shown on page 1. LibreOffice puts a header below the top margin, so the style's top
margin is reduced by the header height + gap and the body still starts at the requested ND30 top margin. The .ott
templates (scripts/templates/writer_styles.py) use the same band, on page 1 and after a DOCX round trip alike.

Undo limits (verified on LibreOffice 24.2, same upstream code in 26.8): page-style changes are not undoable;
setting them with undo enabled wipes the whole undo stack, so they run under `undo_locked`. Creating a header
shifts node positions recorded by older undo actions (redo then crashes Writer), therefore page numbers also
clear the undo history first. Margins-only keeps the history. Nothing is changed if the values are invalid,
and a failure while applying restores the previous style values.

Two-sided printing ("In hai mặt", nd30_duplex): ND30 Phụ lục I, Phần I, Mục I, khoản 3 (margins) and khoản 7 (page
number) set no back-page margins, so ND30 pages are never mirrored; only Party documents mirror them (Hướng dẫn
05-HD/VPTW, IV.4.2). PageStyleLayout is copied with the other values, so an attached document keeps the choice.
"""
from .nd30 import profile_rules, validate_margins
from .undo import style_snapshot, undo_locked

MM = 100  # UNO lengths are in 1/100 mm
HEADER_HEIGHT_MM = 10.0  # LibreOffice writes DOCX w:top = TopMargin + header height; the gap is dropped, so keep it 0
HEADER_GAP_MM = 0.0
PROPERTIES = ("IsLandscape", "Width", "Height", "TopMargin", "BottomMargin", "LeftMargin", "RightMargin",
              "HeaderIsOn", "FirstIsShared", "HeaderIsDynamicHeight", "HeaderHeight", "HeaderBodyDistance",
              "FooterIsOn", "FooterIsDynamicHeight", "FooterHeight", "FooterBodyDistance", "PageStyleLayout")
FOOTER_HEIGHT_MM = 10.0  # the first-page footer (contact details of an official letter) is a band in the bottom margin


def mm(value):
    return int(round(float(value) * MM))


def page_style_for(doc, cursor):
    name = cursor.PageStyleName
    return name, doc.getStyleFamilies().getByName("PageStyles").getByName(name)


def plan_properties(margins_mm, page_numbers, existing_header_mm=0.0, profile="nd30", footer=False):
    """Desired property values (margins validated first). `existing_header_mm` is the height + gap of a header the
    style already has: the body must still start at the ND30 top margin, so it is subtracted from TopMargin.
    Raises ValueError listing out-of-range sides."""
    data = profile_rules(profile)
    check = validate_margins(margins_mm, data)
    if not check["ok"]:
        raise ValueError("invalid-margins: %s" % ", ".join("%s:%s" % (e["field"], e["code"]) for e in check["errors"]))
    size = data["pageSizeMm"]
    top = float(margins_mm["top"])
    values = {"IsLandscape": False, "Width": mm(size["width"]), "Height": mm(size["height"]),
              "TopMargin": mm(max(0.0, top - existing_header_mm)), "BottomMargin": mm(margins_mm["bottom"]),
              "LeftMargin": mm(margins_mm["left"]), "RightMargin": mm(margins_mm["right"])}
    if page_numbers:
        values.update({"HeaderIsOn": True, "FirstIsShared": False, "HeaderIsDynamicHeight": False,
                       "HeaderHeight": mm(HEADER_HEIGHT_MM), "HeaderBodyDistance": mm(HEADER_GAP_MM),
                       "TopMargin": mm(top - HEADER_HEIGHT_MM - HEADER_GAP_MM)})
    if footer:  # Decree 30, Annex I, I.III.4: contact details on the first page; the body still ends at the bottom margin
        values.update({"FooterIsOn": True, "FirstIsShared": False, "FooterIsDynamicHeight": True, "FooterHeight": mm(FOOTER_HEIGHT_MM),
                       "FooterBodyDistance": 0, "BottomMargin": mm(float(margins_mm["bottom"]) - FOOTER_HEIGHT_MM)})
    return values


def _write_page_number(doc, style, profile="nd30"):
    from .nd30_text import format_paragraph, format_run
    header = style.HeaderText
    header.setString("")
    cur = header.createTextCursor()
    format_paragraph(cur, {"align": "center"}, 0)
    field = doc.createInstance("com.sun.star.text.TextField.PageNumber")
    field.NumberingType = 4  # ARABIC
    field.SubType = 1        # CURRENT
    header.insertTextContent(cur, field, False)
    cur.gotoStart(False)
    cur.gotoEnd(True)
    format_run(cur, {"size": profile_rules(profile)["typography"]["pageNumber"], "bold": False, "italic": False})


def _write_first_footer(style, blocks, text_mm):
    from .nd30_text import PARAGRAPH_BREAK, format_paragraph, format_run
    style.FooterText.setString("")
    footer = style.FooterTextFirst
    footer.setString("")
    cur = footer.createTextCursor()
    for index, block in enumerate(blocks):
        if index:
            footer.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
        format_paragraph(cur, block, text_mm)
        for item in block["runs"]:
            footer.insertString(cur, item["text"], True)
            format_run(cur, item)
            cur.collapseToEnd()


def _is_user_footer(style):
    if not style.FooterIsOn:
        return False
    return any(t.getString().strip() for t in (style.FooterText, style.FooterTextFirst) if t is not None)


def _is_user_header(style):
    """A header only counts as the user's when it says something; an empty one or a lone page number is ours to set."""
    text = style.HeaderText.getString().strip() if style.HeaderIsOn else ""
    return bool(text) and not text.isdigit()


def apply_page_layout(doc, cursor, margins_mm=None, page_numbers=True, profile="nd30", first_footer=(), text_mm=None):
    """Apply the layout to the cursor's page style (not undoable, see module doc). Returns a summary dict.
    `first_footer` (paragraph blocks) goes into the first-page footer unless the style already has a footer of the user."""
    name, style = page_style_for(doc, cursor)
    header_skipped = bool(page_numbers and _is_user_header(style))
    if header_skipped:
        page_numbers = False  # never overwrite a header the user already has
    footer = bool(first_footer) and not _is_user_footer(style)
    existing = (style.HeaderHeight + style.HeaderBodyDistance) / MM if style.HeaderIsOn else 0.0
    wanted = plan_properties(margins_mm or profile_rules(profile)["defaultMarginsMm"], page_numbers, existing, profile, footer)
    before = style_snapshot(style, PROPERTIES)
    cleared = False
    if page_numbers:
        doc.getUndoManager().clear()  # recorded node positions would be stale once the header exists
        cleared = True
    try:
        with undo_locked(doc):
            for key in PROPERTIES:
                if key in wanted:
                    style.setPropertyValue(key, wanted[key])
            if page_numbers:
                _write_page_number(doc, style, profile)
            if footer:
                _write_first_footer(style, first_footer, text_mm or (style.Width - style.LeftMargin - style.RightMargin) / MM)
    except BaseException:
        with undo_locked(doc):
            for key in PROPERTIES:
                if key in before:
                    style.setPropertyValue(key, before[key])
        raise
    body_top = style.TopMargin + (style.HeaderHeight + style.HeaderBodyDistance if style.HeaderIsOn else 0)
    return {"pageStyle": name, "pageNumbers": page_numbers, "headerSkipped": header_skipped, "firstFooter": footer,
            "undoHistoryCleared": cleared, "bodyTopMm": body_top / MM}


def apply_custom_page(doc, cursor, page):
    """A form with its own paper (the envelope): size and margins only, no page number. Not undoable, see module doc."""
    name, style = page_style_for(doc, cursor)
    with undo_locked(doc):
        for key, value in (("HeaderIsOn", False), ("IsLandscape", True), ("Width", mm(page["width"])), ("Height", mm(page["height"])), ("TopMargin", mm(page["top"])),
                           ("BottomMargin", mm(page["bottom"])), ("LeftMargin", mm(page["left"])), ("RightMargin", mm(page["right"]))):
            style.setPropertyValue(key, value)
    return {"pageStyle": name, "pageNumbers": False, "headerSkipped": False, "undoHistoryCleared": False, "bodyTopMm": page["top"]}


def section_style(doc, cursor):
    """Page style of an attached document or annex: a copy of the current one, so it can number its pages from 1."""
    name, style = page_style_for(doc, cursor)
    target = "HST " + name + " kèm theo"
    styles = doc.getStyleFamilies().getByName("PageStyles")
    if not styles.hasByName(target):
        with undo_locked(doc):
            copy = doc.createInstance("com.sun.star.style.PageStyle")
            styles.insertByName(target, copy)
            for key in PROPERTIES:
                copy.setPropertyValue(key, style.getPropertyValue(key))
            _write_page_number(doc, copy, _profile_of(style))
            style.FollowStyle = name
            copy.FollowStyle = target
    return target


def _profile_of(style):
    """Page number size follows the header already written: 13 pt only in the QPPL profile."""
    header = style.HeaderText.createTextCursor()
    header.gotoEnd(True)
    return "qppl" if abs(header.CharHeight - 13) < 0.1 else "nd30"
