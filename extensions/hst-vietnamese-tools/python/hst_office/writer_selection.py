# SPDX-License-Identifier: AGPL-3.0-only
"""What the user has selected in a Writer view, read without the view cursor's text methods.

The view cursor's getText/getStart/gotoEnd/... throw RuntimeException("no text selection") whenever the view's
selection is not plain text (sw/source/uibase/uno/unotxvw.cxx SwXTextViewCursor::IsTextSelection): table cells
selected (table mode), a picture/frame/OLE object or a drawing shape selected, a comment being edited. HST commands
decide from the controller's getSelection() instead, whose implementation tells which case it is (SwXTextView::
getSelection): SwXTextRanges for text, SwXTextTableCursor for cells, SwXTextFrame/SwXTextGraphicObject/
SwXTextEmbeddedObject or a shape collection for objects, nothing while a comment has the focus.
"""
TEXT, CELLS, OBJECT = "text", "cells", "object"
TABLE = "com.sun.star.text.TextTable"


def _supports(obj, *services):
    try:
        return any(obj.supportsService(s) for s in services)
    except Exception:  # noqa: BLE001 - a selection object without XServiceInfo
        return False


def selection(controller):
    """(kind, selection): TEXT with the text ranges, CELLS with the table cursor, OBJECT for anything else (object,
    shape, comment, unknown; the selection may then be None). Never raises for what the user has selected."""
    try:
        sel = controller.getSelection()
    except Exception:  # noqa: BLE001 - a view without a selection supplier
        return OBJECT, None
    if sel is None:
        return OBJECT, None
    if _supports(sel, "com.sun.star.text.TextRanges"):
        return TEXT, sel
    if _supports(sel, "com.sun.star.text.TextTableCursor"):
        return CELLS, sel
    return OBJECT, sel


def single_text_range(controller):
    """(range, reason): the one selected text range, or None and why not: 'unsupported-selection' (cells, object,
    shape, comment) or 'multiple-selections'."""
    kind, sel = selection(controller)
    if kind != TEXT:
        return None, "unsupported-selection"
    if sel.getCount() != 1:
        return None, "multiple-selections"
    return sel.getByIndex(0), None


def cursor_property(view_cursor, name):
    """A property of the view cursor's position (TextTable, TextFrame, TextSection, ...); None if unset. Property
    reads use the shell cursor directly (SwXTextViewCursor::getPropertyValue) and work in every selection mode."""
    try:
        return view_cursor.getPropertyValue(name)
    except Exception:  # noqa: BLE001 - unknown property or a view that went away
        return None


def _elements(text):
    paragraphs = text.createEnumeration()
    while paragraphs.hasMoreElements():
        yield paragraphs.nextElement()


def _holds(table, name):
    """Whether a cell of `table` holds the table `name`, at any depth."""
    for cell in table.getCellNames():
        for element in _elements(table.getCellByName(cell)):
            if element.supportsService(TABLE) and (element.getName() == name or _holds(element, name)):
                return True
    return False


def body_table(body, table):
    """The table of the main text `body` that is `table` or holds it in one of its cells; None when `table` is in a
    frame, header, footer or note. Found by walking the main text: a table's anchor does not tell which text holds it
    (its getText() is empty)."""
    name = table.getName()
    tables = [e for e in _elements(body) if e.supportsService(TABLE)]
    return next((t for t in tables if t.getName() == name), None) or next((t for t in tables if _holds(t, name)), None)


def same_text(a, b):
    try:
        return a is not None and b is not None and a == b
    except Exception:  # noqa: BLE001 - comparing a disposed proxy
        return False


def protected(rng):
    """Whether `rng` lies in a protected section (or one nested in a protected section)."""
    section = cursor_property(rng, "TextSection")
    while section is not None:
        if section.IsProtected:
            return True
        section = section.ParentSection
    return False
