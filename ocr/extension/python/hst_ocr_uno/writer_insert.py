# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Insert recognised items (blocks.Item) at the cursor of a Writer document, as one undo step.

Text items become paragraphs; table items become a Writer table (one paragraph before it keeps the cursor's
paragraph intact). When formulas ("$$…$$" paragraphs) were inserted, the inserted range is selected and HST's
own "Chuyển TeX ⇄ công thức" (org.hst.office.vi:TexToggle, HST Vietnamese tools 1.0.3+) turns them into Công
thức objects; without that extension the LaTeX simply stays as text.
"""
import uno

from .blocks import has_formula

PARAGRAPH_BREAK = 0  # com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK
TEX_TOGGLE = "org.hst.office.vi:TexToggle"


def insert_items(ctx, doc, items, undo_title):
    """Insert items at the view cursor; returns True when formulas were handed to Chuyển TeX ⇄ công thức."""
    controller = doc.getCurrentController()
    view = controller.getViewCursor()
    cursor = view.getText().createTextCursorByRange(view.getStart())
    undo = doc.getUndoManager()
    undo.enterUndoContext(undo_title)
    try:
        start = cursor.getText().createTextCursorByRange(cursor)
        start_mark = start.getStart()
        for n, item in enumerate(items):
            if n:
                cursor.getText().insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            if item.kind == "text":
                cursor.getText().insertString(cursor, item.value, False)
            else:
                _insert_table(doc, cursor, item.value)
        inserted = cursor.getText().createTextCursorByRange(start_mark)
        inserted.gotoRange(cursor, True)
    finally:
        undo.leaveUndoContext()
    if not has_formula(items):
        view.gotoRange(cursor.getEnd(), False)
        return False
    controller.select(inserted)
    converted = _dispatch(ctx, controller.getFrame(), TEX_TOGGLE)
    view.gotoRange(cursor.getEnd(), False)
    return converted


def _insert_table(doc, cursor, rows):
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(len(rows), max(len(r) for r in rows))
    cursor.getText().insertTextContent(cursor, table, False)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.getCellByPosition(c, r).setString(value)


def _dispatch(ctx, frame, command):
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = command
    transformer = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
    _, url = transformer.parseStrict(url)
    if frame.queryDispatch(url, "", 0) is None:  # HST Vietnamese tools not installed: keep the LaTeX text
        return False
    helper.executeDispatch(frame, command, "", 0, ())
    return True
