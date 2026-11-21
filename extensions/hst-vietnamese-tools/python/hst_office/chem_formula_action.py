# SPDX-License-Identifier: AGPL-3.0-only
"""HST ▸ Định dạng công thức hoá học (org.hst.office.vi:ChemFormula) in HST Writer, Slides and Draw.

Formats the selected text, or the word just before the cursor when nothing is selected, with chem_formula's rules,
in one undo step. Subscript and superscript are real character formatting (CharEscapement / CharEscapementHeight,
the same values as the x₂ / x² buttons), so Word and .docx keep them; only "->", "<->", the charge minus and the
hydrate dot are replaced by characters. Only this command formats: nothing happens while typing.
"""
from . import chem_formula

UNDO_TITLE = "Định dạng công thức hoá học"
# Writer's and editeng's automatic sub/superscript (DFLT_ESC_AUTO_SUB / _SUPER) at the default 58 % height
ESCAPEMENT = {chem_formula.SUB: -14000, chem_formula.SUP: 14000}
ESCAPEMENT_HEIGHT = 58
WORD_LIMIT = 80  # characters looked at before the cursor
TEXT = {"title": "Định dạng công thức hoá học",
        "nothing": "Hãy chọn văn bản có công thức hoá học (ví dụ H2SO4, SO42-, Fe3+) hoặc đặt con trỏ ngay sau công thức.",
        "readonly": "Không sửa được vùng này (tài liệu chỉ đọc hoặc vùng được bảo vệ)."}


def _string(rng):
    return rng.getString().replace("\r\n", "\n")


def _word_before(rng):
    """The text range of the run of non-space characters ending at the collapsed `rng`, or None."""
    cursor = rng.getText().createTextCursorByRange(rng.getStart())
    count = 0
    while count < WORD_LIMIT and cursor.goLeft(1, True):
        text = cursor.getString()
        if not text or text[0].isspace() or text[0] in "\r\n":
            cursor.collapseToEnd()
            cursor.goLeft(count, True)
            break
        count += 1
    if count == 0:
        return None
    return cursor


def targets(model, controller):
    """Text ranges to format: the non-empty selected ranges, the word before the cursor, or each selected shape."""
    selection = controller.getSelection()
    if selection is None:
        return []
    if selection.supportsService("com.sun.star.drawing.ShapeCollection") or selection.supportsService(
            "com.sun.star.drawing.Shapes"):
        shapes = [selection.getByIndex(i) for i in range(selection.getCount())]
        return [s for s in shapes if hasattr(s, "getString") and s.getString()]
    if selection.supportsService("com.sun.star.text.TextRanges"):
        ranges = [selection.getByIndex(i) for i in range(selection.getCount())]
    elif hasattr(selection, "getString") and hasattr(selection, "getText"):
        ranges = [selection]  # Slides/Draw while editing the text of a shape
    elif hasattr(selection, "getString"):  # one shape selected (not in edit mode)
        return [selection] if selection.getString() else []
    else:
        return []
    chosen = [r for r in ranges if r.getString()]
    if chosen:
        return chosen
    word = _word_before(ranges[0]) if ranges else None
    return [word] if word is not None else []


def _at(rng, start, length):
    """A text cursor over [start, start + length) counted in characters from the start of `rng`."""
    cursor = rng.getText().createTextCursorByRange(rng.getStart())
    cursor.goRight(start, False)
    cursor.goRight(length, True)
    return cursor


def _format(rng, start, length, kind):
    cursor = _at(rng, start, length)
    cursor.setPropertyValue("CharEscapement", ESCAPEMENT[kind] if kind else 0)
    cursor.setPropertyValue("CharEscapementHeight", ESCAPEMENT_HEIGHT if kind else 100)


def apply(rng, log=None):
    """Format one range; returns the number of changes. Right to left, so earlier offsets stay valid; a replaced
    character gets its formatting right after it is written (inserted text would take its neighbour's).
    `log` (a list) receives each operation with what it replaced, for ChemUndo."""
    edits = chem_formula.parse(_string(rng))
    order = sorted(edits, key=lambda e: (e.start, e.text is not None), reverse=True)  # replacement first per position
    for edit in order:
        length = edit.end - edit.start
        if edit.text is not None:
            cursor = _at(rng, edit.start, length)
            if log is not None:
                log.append(("text", edit.start, cursor.getString(), edit.text))
            cursor.setString(edit.text)
        else:
            if log is not None:
                old = [(c.CharEscapement, c.CharEscapementHeight) for c in (_at(rng, edit.start + i, 1)
                                                                             for i in range(length))]
                log.append(("format", edit.start, length, edit.kind, old))
            _format(rng, edit.start, length, edit.kind)
    return len(edits)


def _undo_class():
    import unohelper
    from com.sun.star.document import XUndoAction

    class ChemUndo(unohelper.Base, XUndoAction):
        """Slides and Draw record no undo for text changed through the API: this action reverses exactly the
        operations of one command (formatting back to the old values, replaced characters back to the old text)."""

        def __init__(self, items):
            self.Title, self.items = UNDO_TITLE, items

        def undo(self):
            for rng, ops in self.items:
                for op in reversed(ops):
                    if op[0] == "text":
                        _at(rng, op[1], len(op[3])).setString(op[2])
                    else:
                        for i, (escapement, height) in enumerate(op[4]):
                            cursor = _at(rng, op[1] + i, 1)
                            cursor.setPropertyValue("CharEscapement", escapement)
                            cursor.setPropertyValue("CharEscapementHeight", height)

        def redo(self):
            for rng, ops in self.items:
                for op in ops:
                    if op[0] == "text":
                        _at(rng, op[1], len(op[2])).setString(op[3])
                    else:
                        _format(rng, op[1], op[2], op[3])
    return ChemUndo


def run(host):
    """Command entry (actions.COMMANDS["ChemFormula"])."""
    from .dialogs import message_box
    doc, controller = host.doc, host.controller
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return
    ranges = targets(doc, controller)
    if not ranges:
        return message_box(host.ctx, host.peer, TEXT["title"], TEXT["nothing"])
    manager = doc.getUndoManager()
    writer = doc.supportsService("com.sun.star.text.TextDocument")  # Writer records the API changes itself
    logs = [] if writer else [(r, []) for r in ranges]
    if writer:
        manager.enterUndoContext(UNDO_TITLE)
    doc.lockControllers()
    try:
        changed = sum(apply(r) for r in ranges) if writer else sum(apply(r, log) for r, log in logs)
    except Exception:  # noqa: BLE001 - read-only document or protected section
        from . import diag_log
        diag_log.exception("chem_formula")
        changed = -1
    finally:
        doc.unlockControllers()
        if writer:
            manager.leaveUndoContext()
        elif any(log for _, log in logs):
            doc.setModified(True)
            manager.addUndoAction(_undo_class()(logs))
    if changed < 0:
        message_box(host.ctx, host.peer, TEXT["title"], TEXT["readonly"], error=True)
    elif changed == 0:
        message_box(host.ctx, host.peer, TEXT["title"], TEXT["nothing"])
