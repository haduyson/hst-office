# SPDX-License-Identifier: AGPL-3.0-only
"""Where the ND30 wizard writes: decided from the view's selection (writer_selection), never from the view cursor's
text methods, which throw "no text selection" while cells, a picture, frame, shape or comment are selected.

- a text cursor in the main text: the document goes at the cursor's paragraph (nd30_writer._position);
- a cursor or selected cells in a table of the main text (the header table of an administrative document): the
  document goes into a new paragraph right after that table (the outermost one when tables are nested);
- refused before anything is written: read-only document, selected text (never replaced), a picture/frame/shape/
  comment selected, a cursor in a frame/header/footer/note, a cursor in a protected section (the office API would
  write there although the user cannot).
"""
from . import writer_selection as ws


def insertion_point(doc, controller):
    """{'reasons': [...], 'range': selected text range or None, 'table': main-text table holding the cursor or None}."""
    point = {"reasons": ["read-only"] if doc.isReadonly() else [], "range": None, "table": None}
    kind, sel = ws.selection(controller)
    if kind == ws.OBJECT:
        point["reasons"].append("not-text-cursor")
        return point
    body = doc.getText()
    inner = ws.cursor_property(controller.getViewCursor(), "TextTable")
    table = ws.body_table(body, inner) if inner is not None else None
    if kind == ws.TEXT:
        point["range"] = sel.getByIndex(0)
        if sel.getCount() != 1 or point["range"].getString():
            point["reasons"].append("selection")  # replacing a selection silently is not allowed
    point["table"] = table
    # where the document goes: after the table of the main text, else at the cursor (its own text must be the body)
    if inner is not None:
        inside = table is not None
    else:
        inside = point["range"] is not None and ws.same_text(point["range"].getText(), body)
    locked = inside and ws.protected(table.getCellByName(table.getCellNames()[0]).getStart() if table else point["range"])
    if not inside:
        point["reasons"].append("not-body-text")  # frame, header/footer, footnote (or a table in one of them)
    elif locked:
        point["reasons"].append("protected-cursor")
    return point


def after_table(doc, text, table):
    """A text cursor in a new empty paragraph directly after `table` (a table of the main text)."""
    text.insertTextContentAfter(doc.createInstance("com.sun.star.text.Paragraph"), table)
    name, found = table.getName(), False
    paragraphs = text.createEnumeration()
    while paragraphs.hasMoreElements():
        element = paragraphs.nextElement()
        if found:
            return text.createTextCursorByRange(element.getStart())
        found = element.supportsService("com.sun.star.text.TextTable") and element.getName() == name
    raise RuntimeError("no paragraph after table %s" % name)
