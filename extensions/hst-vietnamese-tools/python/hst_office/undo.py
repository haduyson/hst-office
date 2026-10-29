# SPDX-License-Identifier: AGPL-3.0-only
"""One-step undo helpers for Writer and Calc (uno objects are passed in; `uno` is imported lazily).

`undo_step` wraps a mutation in XUndoManager enter/leaveUndoContext so the whole wizard action is one Undo.
If the body raises, the context is closed and any actions it recorded are undone, so a failure leaves no partial
write behind. LibreOffice does not record page-style property changes in the undo stack, so
`StylePropertiesUndoAction` registers a proper undo action for them.
"""
import contextlib


def _depth(manager):
    return len(manager.getAllUndoActionTitles())


@contextlib.contextmanager
def undo_step(doc, title):
    """Run the body as a single undo step; on exception roll back everything recorded inside."""
    manager = doc.getUndoManager()
    before = _depth(manager)
    manager.enterUndoContext(title)
    try:
        yield manager
    except BaseException:
        manager.leaveUndoContext()
        if _depth(manager) > before:
            manager.undo()
            manager.clearRedo()
        raise
    else:
        manager.leaveUndoContext()


def style_snapshot(style, names):
    """Current values; properties that are void (e.g. header settings while the header is off) are left out."""
    values = {name: style.getPropertyValue(name) for name in names}
    return {name: value for name, value in values.items() if value is not None}


@contextlib.contextmanager
def undo_locked(doc):
    """Disable undo recording while a page style is changed: Writer wipes the WHOLE undo stack when a page style
    property is set through UNO with undo enabled (sw/source/core/unocore/unostyle.cxx, 'Fix i64460')."""
    manager = doc.getUndoManager()
    manager.lock()
    try:
        yield
    finally:
        manager.unlock()
