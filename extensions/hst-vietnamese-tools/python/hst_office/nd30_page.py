# SPDX-License-Identifier: AGPL-3.0-only
"""Apply A4 + ND30 margins (and page numbers hidden on the first page) to the current Writer page style.

ND30 I.1 A4; I.3 margins top/bottom 20-25, left 30-35, right 15-20 mm; I.7 page number centred in the top
margin, size 13-14, not shown on page 1. LibreOffice puts a header below the top margin, so the style's top
margin is reduced by the header height + gap and the body still starts at the requested ND30 top margin.

Undo limits (verified on LibreOffice 24.2, same upstream code in 26.8): page-style changes are not undoable;
setting them with undo enabled wipes the whole undo stack, so they run under `undo_locked`. Creating a header
shifts node positions recorded by older undo actions (redo then crashes Writer), therefore page numbers also
clear the undo history first. Margins-only keeps the history. Nothing is changed if the values are invalid,
and a failure while applying restores the previous style values.
"""
from .nd30 import rules, validate_margins
from .undo import style_snapshot, undo_locked

MM = 100  # UNO lengths are in 1/100 mm
HEADER_HEIGHT_MM = 10.0  # LibreOffice writes DOCX w:top = TopMargin + header height; the gap is dropped, so keep it 0
HEADER_GAP_MM = 0.0
PROPERTIES = ("IsLandscape", "Width", "Height", "TopMargin", "BottomMargin", "LeftMargin", "RightMargin",
              "HeaderIsOn", "FirstIsShared", "HeaderIsDynamicHeight", "HeaderHeight", "HeaderBodyDistance")


def mm(value):
    return int(round(float(value) * MM))


def page_style_for(doc, cursor):
    name = cursor.PageStyleName
    return name, doc.getStyleFamilies().getByName("PageStyles").getByName(name)


def plan_properties(margins_mm, page_numbers, existing_header_mm=0.0):
    """Desired property values (margins validated first). `existing_header_mm` is the height + gap of a header the
    style already has: the body must still start at the ND30 top margin, so it is subtracted from TopMargin.
    Raises ValueError listing out-of-range sides."""
    check = validate_margins(margins_mm)
    if not check["ok"]:
        raise ValueError("invalid-margins: %s" % ", ".join("%s:%s" % (e["field"], e["code"]) for e in check["errors"]))
    size = rules()["pageSizeMm"]
    top = float(margins_mm["top"])
    values = {"IsLandscape": False, "Width": mm(size["width"]), "Height": mm(size["height"]),
              "TopMargin": mm(max(0.0, top - existing_header_mm)), "BottomMargin": mm(margins_mm["bottom"]),
              "LeftMargin": mm(margins_mm["left"]), "RightMargin": mm(margins_mm["right"])}
    if page_numbers:
        values.update({"HeaderIsOn": True, "FirstIsShared": False, "HeaderIsDynamicHeight": False,
                       "HeaderHeight": mm(HEADER_HEIGHT_MM), "HeaderBodyDistance": mm(HEADER_GAP_MM),
                       "TopMargin": mm(top - HEADER_HEIGHT_MM - HEADER_GAP_MM)})
    return values


def _write_page_number(doc, style):
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
    format_run(cur, {"size": rules()["typography"]["signerName"], "bold": False, "italic": False})


def apply_page_layout(doc, cursor, margins_mm=None, page_numbers=True):
    """Apply the layout to the cursor's page style (not undoable, see module doc). Returns a summary dict."""
    name, style = page_style_for(doc, cursor)
    header_skipped = bool(page_numbers and style.HeaderIsOn)
    if header_skipped:
        page_numbers = False  # never overwrite a header the user already has
    existing = (style.HeaderHeight + style.HeaderBodyDistance) / MM if style.HeaderIsOn else 0.0
    wanted = plan_properties(margins_mm or rules()["defaultMarginsMm"], page_numbers, existing)
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
                _write_page_number(doc, style)
    except BaseException:
        with undo_locked(doc):
            for key in PROPERTIES:
                if key in before:
                    style.setPropertyValue(key, before[key])
        raise
    body_top = style.TopMargin + (style.HeaderHeight + style.HeaderBodyDistance if style.HeaderIsOn else 0)
    return {"pageStyle": name, "pageNumbers": page_numbers, "headerSkipped": header_skipped,
            "undoHistoryCleared": cleared, "bodyTopMm": body_top / MM}
