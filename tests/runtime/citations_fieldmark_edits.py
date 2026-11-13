# SPDX-License-Identifier: AGPL-3.0-only
"""What editing does to a citation field: typing or deleting inside it, Backspace/Delete next to
it, deleting a selection holding it, Undo/Redo, copy/cut and paste. Each case starts from a fresh
paragraph "Trước [1] sau." with one citation, driven through the same commands as the keyboard."""
from citations_fieldmark_uno import CITATION_PREFIX, prop, scan

CODE = CITATION_PREFIX + '{"v":1,"citationID":"e1","items":[{"id":"x"}]}'
RESULT = "[1]"
PLAIN = "Trước [1] sau."


def fresh(session):
    doc = session.doc
    doc.getText().setString("Trước ¤ sau.")
    doc.getUndoManager().clear()
    session.insert_field(session.markers()[0], CODE, RESULT)
    session.drop_markers()
    doc.getUndoManager().clear()


def state(session):
    """(paragraph text, [codes of HST fields])"""
    return session.doc.getText().getString(), [f.code for f in scan(session.doc)]


def cursor_after_field(session, offset=0):
    """View cursor right after the field end (offset moves it further right)."""
    field = scan(session.doc)[0]
    session.view_cursor.gotoRange(field.mark.getAnchor().getEnd(), False)
    if offset:
        session.view_cursor.goRight(offset, False)


def cursor_before_field(session):
    session.view_cursor.gotoRange(scan(session.doc)[0].mark.getAnchor().getStart(), False)


def run(rec, session):
    undo = session.doc.getUndoManager()
    whole = (PLAIN, [CODE])

    fresh(session)  # typing inside the result is refused
    cursor_before_field(session)
    session.view_cursor.goRight(2, False)
    session.dispatch("InsertText", prop("Text", "Z"))
    rec.check("edit-type-inside-refused", state(session) == whole, state(session))

    fresh(session)  # deleting a character inside the result is refused
    cursor_before_field(session)
    session.view_cursor.goRight(2, False)
    session.dispatch("Delete")
    rec.check("edit-delete-inside-refused", state(session) == whole, state(session))

    fresh(session)  # a selection crossing the field boundary is refused
    session.view_cursor.gotoStart(False)
    session.view_cursor.goRight(8, True)
    session.dispatch("Delete")
    rec.check("edit-partial-selection-refused", state(session) == whole, state(session))

    fresh(session)  # Backspace just after: selects the field, the second press deletes it
    cursor_after_field(session)
    session.dispatch("SwBackspace")
    first = state(session)
    selected = session.view_cursor.getString()
    session.dispatch("SwBackspace")
    second = state(session)
    undo.undo()
    rec.check("edit-backspace-after-selects", first == whole and selected == RESULT, {"after": first, "selected": selected})
    rec.check("edit-backspace-twice-deletes", second == ("Trước  sau.", []), second)
    rec.check("edit-backspace-undo-keeps-code", state(session) == whole, state(session))

    fresh(session)  # Delete just before: same, mirrored
    cursor_before_field(session)
    session.dispatch("Delete")
    first, selected = state(session), session.view_cursor.getString()
    rec.check("edit-delete-before-selects", first == whole and selected == RESULT, {"after": first, "selected": selected})

    fresh(session)  # delete a selection holding the field, then Undo and Redo
    session.view_cursor.gotoStart(False)
    session.view_cursor.gotoEnd(True)
    session.dispatch("Delete")
    deleted = state(session)
    undo.undo()
    rec.check("edit-delete-selection", deleted == ("", []), deleted)
    rec.check("edit-delete-undo-keeps-code", state(session) == whole, state(session))
    undo.redo()
    undo.undo()
    rec.check("edit-delete-redo-undo-keeps-code", state(session) == whole, state(session))

    fresh(session)  # insert, Undo, Redo
    session.doc.getText().setString("Trước ¤ sau.")
    undo.clear()
    session.insert_field(session.markers()[0], CODE, RESULT)
    undo.undo()
    undone = state(session)
    undo.redo()
    rec.check("edit-insert-undo-removes", undone == ("Trước ¤ sau.", []), undone)
    rec.check("edit-insert-redo-keeps-code", state(session)[1] == [CODE], state(session))

    fresh(session)  # copy and paste: the copy keeps the code (same citationID: refresh re-IDs it)
    session.view_cursor.gotoStart(False)
    session.view_cursor.gotoEnd(True)
    session.dispatch("Copy")
    session.view_cursor.gotoEnd(False)
    session.dispatch("Paste")
    rec.check("edit-copy-paste-keeps-code", state(session) == (PLAIN + PLAIN, [CODE, CODE]), state(session))

    fresh(session)  # cut and paste back
    session.view_cursor.gotoStart(False)
    session.view_cursor.gotoEnd(True)
    session.dispatch("Cut")
    session.dispatch("Paste")
    rec.check("edit-cut-paste-keeps-code", state(session) == whole, state(session))

    fresh(session)  # typing right after the field goes outside it
    cursor_after_field(session)
    session.dispatch("InsertText", prop("Text", "Z"))
    rec.check("edit-type-after-outside", state(session) == ("Trước [1]Z sau.", [CODE])
              and scan(session.doc)[0].result == RESULT, state(session))
