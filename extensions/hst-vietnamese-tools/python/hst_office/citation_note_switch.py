# SPDX-License-Identifier: AGPL-3.0-only
"""Move citations into or out of footnotes when the document switches between a note style (Chicago notes) and an
in-text style (UNO). Note styles keep every HST citation alone in its own footnote (engine contract, phase 03);
in-text styles keep them in the text. Runs inside the caller's Undo context, before the refresh that reformats.

- to notes: each citation in body text, a table or a frame becomes a footnote at the same place, holding it;
- to the text: each footnote that holds nothing but one HST citation is replaced by the citation at the footnote's
  anchor, after a space when the previous character is not one (Writer numbers the remaining footnotes itself).
"""
from . import citation_document as document


def _select_field(doc, mark):
    """Select the whole field (start to end) with the view cursor, as Backspace does next to it."""
    view = doc.getCurrentController().getViewCursor()
    anchor = mark.getAnchor()
    view.gotoRange(anchor.getStart(), False)
    view.gotoRange(anchor.getEnd(), True)
    return view


def _in_note(field):
    text = field["mark"].getAnchor().getText()
    return text is not None and (text.supportsService("com.sun.star.text.Footnote")
                                 or text.supportsService("com.sun.star.text.Endnote"))


def to_notes(ctx, doc):
    """Put every in-text citation into its own footnote; returns how many moved."""
    moved = 0
    for field in reversed(document.scan(doc)):  # from the end: earlier positions stay valid
        if field["kind"] != "citation" or _in_note(field):
            continue
        code, html = field["code"], document.plain_html(field["result"])
        _select_field(doc, field["mark"])
        document.dispatch(ctx, doc, "Delete")
        document.insert_field(ctx, doc, code, html, "Footnote")
        moved += 1
    return moved


def _only_citation(footnote, field):
    """True when the footnote's text is just this citation (spaces around it allowed)."""
    return footnote.getString().strip() == field["result"].strip()


def to_text(ctx, doc):
    """Replace footnotes that hold only a citation by the citation itself; returns how many moved."""
    moved = 0
    for field in reversed(document.scan(doc)):
        if field["kind"] != "citation" or not _in_note(field):
            continue
        footnote = field["mark"].getAnchor().getText()
        if not _only_citation(footnote, field):
            continue  # the user wrote more in this footnote: leave it where it is
        code, html = field["code"], document.plain_html(field["result"])
        anchor = footnote.getAnchor()
        body = anchor.getText()
        place = body.createTextCursorByRange(anchor.getStart())
        body.removeTextContent(footnote)
        view = doc.getCurrentController().getViewCursor()
        view.gotoRange(place.getStart(), False)
        before = body.createTextCursorByRange(place.getStart())
        if before.goLeft(1, True) and not before.getString().isspace():
            body.insertString(view, " ", False)
        document.insert_field(ctx, doc, code, html)
        moved += 1
    return moved


def switch(ctx, doc, to_note):
    return to_notes(ctx, doc) if to_note else to_text(ctx, doc)
