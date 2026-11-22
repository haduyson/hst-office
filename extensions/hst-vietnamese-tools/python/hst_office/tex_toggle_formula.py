# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức in HST Writer: one formula in and out of the text. A span becomes a formula anchored as a
character, on the text baseline, at the paragraph's font size, its span kept as its description; display math gets a
centred paragraph of its own. A formula turns back into that span when its formula is still what the span gives,
otherwise into LaTeX written from its MathML."""
from . import formula_ole, formula_size, mathml_to_tex, tex_math_spans, tex_to_starmath
from .tex_toggle_scan import OBJECT_MARK

NONE = 0  # com.sun.star.text.VertOrient.NONE
CENTER = 3  # com.sun.star.style.ParagraphAdjust.CENTER
PARAGRAPH_BREAK = 0  # com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK
HIGHLIGHT = 0xFFFF00


def insert_formula(doc, cursor, starmath, span):
    """Replace the text under cursor by a formula; returns the formula object."""
    text = cursor.getText()
    first = text.createTextCursorByRange(cursor.getStart())
    first.goRight(1, True)
    height = first.getPropertyValue("CharHeight")
    obj = doc.createInstance("com.sun.star.text.TextEmbeddedObject")
    obj.CLSID = formula_ole.MATH
    obj.AnchorType = _as_character()
    text.insertTextContent(cursor, obj, True)
    model = obj.getEmbeddedObject()
    model.Formula = starmath
    model.BaseFontHeight = max(1, round(height or 12))
    obj.Description = span
    place(obj)
    return obj


def place(obj):
    """Size the frame to the formula and put the formula's baseline on the text baseline."""
    obj.Size = formula_size.visual_size(obj.EmbeddedObject)
    obj.VertOrient = NONE
    obj.VertOrientPosition = -int(obj.getEmbeddedObject().BaseLine)


def settle(ctx, made):
    """Let the office finish the layout deferred while the views were locked, then place the new formulas again: the
    layout resizes them. Both stay in the command's undo step."""
    try:
        ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).processEventsToIdle()
    except Exception:  # noqa: BLE001 - an office without it lays out later, as usual
        pass
    for obj in made:
        place(obj)


def _as_character():
    import uno
    return uno.Enum("com.sun.star.text.TextContentAnchorType", "AS_CHARACTER")


def make_display(obj):
    """Put a display formula in a paragraph of its own, centred; spaces next to it go. The anchor of a formula
    anchored as a character is the position before it."""
    anchor = obj.getAnchor()
    text = anchor.getText()
    for forward in (True, False):
        cursor = text.createTextCursorByRange(obj.getAnchor().getStart())
        if forward:
            cursor.goRight(1, False)
        _drop_spaces(cursor, forward)
        at_edge = cursor.isEndOfParagraph() if forward else cursor.isStartOfParagraph()
        if not at_edge:
            text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
    paragraph = text.createTextCursorByRange(obj.getAnchor())
    paragraph.setPropertyValue("ParaAdjust", CENTER)


def _drop_spaces(cursor, forward):
    while True:
        move = cursor.goRight if forward else cursor.goLeft
        if not move(1, True) or not cursor.getString().isspace() or "\n" in cursor.getString():
            cursor.collapseToStart() if forward else cursor.collapseToEnd()
            return
        cursor.setString("")


def formula_tex(ctx, obj):
    """The LaTeX span a formula turns back into."""
    model = obj.getEmbeddedObject()
    stored = obj.Description or ""
    spans = tex_math_spans.find_spans(stored)
    if len(spans) == 1 and spans[0].start == 0 and spans[0].end == len(stored):
        try:
            if tex_to_starmath.convert(spans[0].body, spans[0].display) == model.Formula:
                return stored
        except tex_to_starmath.TexError:
            pass
    return tex_math_spans.wrap(mathml_to_tex.tex(_mathml(ctx, model)), _is_display(obj))


def _mathml(ctx, model):
    import uno
    from com.sun.star.beans import PropertyValue
    stream = ctx.ServiceManager.createInstanceWithContext("com.sun.star.io.SequenceOutputStream", ctx)
    args = (PropertyValue(Name="FilterName", Value="MathML XML (Math)"),
            PropertyValue(Name="OutputStream", Value=stream))
    model.storeToURL("private:stream", args)
    data = stream.getWrittenBytes()
    return bytes(data.value if isinstance(data, uno.ByteSequence) else data)


def _is_display(obj):
    """A formula alone in a centred paragraph."""
    anchor = obj.getAnchor()
    cursor = anchor.getText().createTextCursorByRange(anchor)
    cursor.gotoStartOfParagraph(False)
    cursor.gotoEndOfParagraph(True)
    return cursor.getString().strip() in ("", OBJECT_MARK) and cursor.getPropertyValue("ParaAdjust") == CENTER


def revert_formula(ctx, obj):
    """Turn a formula into its LaTeX text; False when its MathML cannot be written as LaTeX."""
    try:
        tex = formula_tex(ctx, obj)
    except mathml_to_tex.TexBackError:
        return False
    anchor = obj.getAnchor()
    text = anchor.getText()
    cursor = text.createTextCursorByRange(anchor.getStart())
    obj.dispose()
    text.insertString(cursor, tex, False)
    return True


def highlight(cursor):
    try:
        cursor.setPropertyValue("CharHighlight", HIGHLIGHT)
    except Exception:  # noqa: BLE001 - an older office without CharHighlight
        cursor.setPropertyValue("CharBackColor", HIGHLIGHT)


