# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức in HST Writer: where to look and what is there. The scope is the selection, or the whole
document (body, tables cell by cell, text frames); each run of paragraphs is read from its text portions, so a field,
footnote or object counts as one character that no span may hold, and each LaTeX span gets a text cursor over it."""
from collections import namedtuple

from . import formula_ole, tex_math_spans

OBJECT_MARK = "\ufffc"  # a field, footnote or object in the text: never inside a span
ZERO_WIDTH = frozenset(("Bookmark", "ReferenceMark", "DocumentIndexMark", "Redline", "SoftPageBreak",
                        "InContentMetadata", "Annotation", "AnnotationEnd", "ContentControl"))



def blocks_of(enumerable):
    """Runs of consecutive paragraphs of one text ([[paragraph]]) in a text or range; a table gives one run per
    cell, so a span never runs from one cell into another."""
    blocks, current = [], []
    enumeration = enumerable.createEnumeration()
    while enumeration.hasMoreElements():
        element = enumeration.nextElement()
        if element.supportsService("com.sun.star.text.TextTable"):
            if current:
                blocks.append(current)
                current = []
            for name in element.getCellNames():
                blocks.extend(blocks_of(element.getCellByName(name).getText()))
        elif element.supportsService("com.sun.star.text.Paragraph"):
            current.append(element)
    if current:
        blocks.append(current)
    return blocks


def document_blocks(doc):
    blocks = blocks_of(doc.getText())
    frames = doc.getTextFrames()
    for name in frames.getElementNames():
        blocks.extend(blocks_of(frames.getByName(name).getText()))
    return blocks


def selection_scope(doc, controller):
    """("object", formula) for a selected formula, ("ranges", [blocks]) for selected text, ("document", blocks)."""
    selection = controller.getSelection()
    if selection is not None and selection.supportsService("com.sun.star.text.TextEmbeddedObject"):
        if formula_ole.is_math_clsid(selection.CLSID):
            return "object", selection
        return "document", document_blocks(doc)
    blocks = []
    if selection is not None and hasattr(selection, "getCount") and selection.supportsService(
            "com.sun.star.text.TextRanges"):
        for index in range(selection.getCount()):
            selected = selection.getByIndex(index)
            text = selected.getText()
            if text.compareRegionStarts(selected.getStart(), selected.getEnd()) == 0:
                continue  # a cursor, no selection
            cursor = text.createTextCursorByRange(selected)
            blocks.extend(blocks_of(cursor))
    if blocks:
        return "ranges", blocks
    return "document", document_blocks(doc)


# reading the text ----------------------------------------------------------------------------------------------------
Piece = namedtuple("Piece", "start length portion")  # offset in the block's string, a Text portion


def _read_block(block):
    """(string, [Piece], [formula objects]): the paragraphs' text joined by "\\n"."""
    parts, pieces, formulas = [], [], []
    length = 0
    for number, paragraph in enumerate(block):
        if number:
            parts.append("\n")
            length += 1
        portions = paragraph.createEnumeration()
        while portions.hasMoreElements():
            portion = portions.nextElement()
            kind = portion.TextPortionType
            if kind == "Text":
                text = portion.getString()
                pieces.append(Piece(length, len(text), portion))
                parts.append(text)
                length += len(text)
            elif kind in ZERO_WIDTH:
                continue
            else:
                formulas.extend(_formulas_in(portion) if kind == "Frame" else [])
                parts.append(OBJECT_MARK)
                length += 1
    return "".join(parts), pieces, formulas


def _formulas_in(portion):
    found = []
    try:
        contents = portion.createContentEnumeration("com.sun.star.text.TextContent")
    except Exception:  # noqa: BLE001 - a portion without anchored content
        return found
    while contents.hasMoreElements():
        content = contents.nextElement()
        if content.supportsService("com.sun.star.text.TextEmbeddedObject") and formula_ole.is_math_clsid(
                content.CLSID):
            found.append(content)
    return found


def _position(pieces, offset):
    """(portion, offset in it) for a string offset that lies in a Text portion, else None."""
    for piece in reversed(pieces):
        if piece.start <= offset <= piece.start + piece.length:
            return piece.portion, offset - piece.start
    return None


def _span_range(pieces, span):
    """A text cursor over the span, or None when its ends are not in text."""
    start, end = _position(pieces, span.start), _position(pieces, span.end)
    if start is None or end is None:
        return None
    text = start[0].getText()
    cursor = text.createTextCursorByRange(start[0].getStart())
    cursor.goRight(start[1], False)
    other = text.createTextCursorByRange(end[0].getStart())
    other.goRight(end[1], False)
    cursor.gotoRange(other.getStart(), True)
    return cursor


def _same_text(found, expected):
    return found.replace("\r\n", "\n").replace("\r", "\n") == expected


def find_work(blocks):
    """([(cursor or None, span)], [formula objects]) in document order."""
    spans, formulas = [], []
    for block in blocks:
        string, pieces, found = _read_block(block)
        formulas.extend(found)
        for span in tex_math_spans.find_spans(string):
            whole = string[span.start:span.end]
            cursor = None if OBJECT_MARK in whole else _span_range(pieces, span)
            if cursor is not None and not _same_text(cursor.getString(), whole):
                cursor = None
            spans.append((cursor, span))
    return spans, formulas

