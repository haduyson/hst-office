# SPDX-License-Identifier: AGPL-3.0-only
"""Word's formatting keys in HST Writer, part of check-msoffice-shortcuts.py (docs/SHORTCUTS-MSOFFICE.md)."""
from msoffice_keys_helpers import dialog_check, iterate, text_field_count
from shortcut_keys import check, wait


def format_keys(office, keys, doc):
    """Ctrl+Alt+C / Ctrl+Alt+V copy character and paragraph formats; Ctrl+Q removes paragraph formatting only."""
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
    text = doc.getText()
    ctrl = doc.getCurrentController()
    cur = text.createTextCursorByRange(text.getEnd())
    for line in ("Mẫu định dạng", "Đích cả đoạn", "Đích một phần đoạn", "Đoạn để xóa"):
        text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
        text.insertString(cur, line, False)
    paras = {p.getString(): p for p in iterate(text)}
    sample = paras["Mẫu định dạng"]
    sample.CharWeight, sample.CharHeight, sample.ParaAdjust = 150.0, 18.0, 3  # bold 18 pt centered
    ctrl.select(text.createTextCursorByRange(sample.getStart()))
    keys.send("ctrl+alt+c")

    whole = paras["Đích cả đoạn"]
    ctrl.select(whole)
    keys.send("ctrl+alt+v")
    check("Writer Ctrl+Alt+V pastes character and paragraph formats on a whole paragraph",
          wait(lambda: whole.CharWeight == 150.0 and whole.CharHeight == 18.0 and whole.ParaAdjust == 3, 5),
          f"{whole.CharWeight} {whole.CharHeight} {whole.ParaAdjust}")

    part = paras["Đích một phần đoạn"]
    cursor = text.createTextCursorByRange(part.getStart())
    cursor.goRight(4, True)
    ctrl.select(cursor)
    keys.send("ctrl+alt+v")
    check("Writer Ctrl+Alt+V on part of a paragraph: character formats only",
          wait(lambda: cursor.CharWeight == 150.0, 5) and part.ParaAdjust != 3 and text.createTextCursorByRange(part.getEnd()).CharWeight != 150.0,
          f"{cursor.CharWeight} {part.ParaAdjust}")

    # The keys' copy stays for another paste, and does not switch the paintbrush on.
    state = _command_state(office, doc, ".uno:FormatPaintbrush")
    check("Writer Ctrl+Alt+C leaves the format paintbrush off", state is not True, state)

    target = paras["Đoạn để xóa"]
    target.ParaAdjust, target.ParaLeftMargin, target.CharWeight = 3, 1000, 150.0
    ctrl.select(text.createTextCursorByRange(target.getStart()))
    keys.send("ctrl+q")
    check("Writer Ctrl+Q removes direct paragraph formatting",
          wait(lambda: target.ParaAdjust != 3 and target.ParaLeftMargin == 0, 5), f"{target.ParaAdjust} {target.ParaLeftMargin}")
    check("Writer Ctrl+Q keeps character formatting", target.CharWeight == 150.0, target.CharWeight)
    check("Writer Ctrl+Q does not quit", office.pid is not None)
    keys.send("ctrl+z")
    check("Writer Ctrl+Z restores what Ctrl+Q removed", wait(lambda: target.ParaAdjust == 3 and target.ParaLeftMargin == 1000, 5),
          f"{target.ParaAdjust} {target.ParaLeftMargin}")
    keys.send("ctrl+y")

    comments = text_field_count(doc.getTextFields())
    ctrl.select(text.createTextCursorByRange(target.getEnd()))
    keys.send("ctrl+alt+m")
    check("Writer Ctrl+Alt+M inserts a comment", wait(lambda: text_field_count(doc.getTextFields()) > comments, 5))
    keys.send("Escape")
    office.raise_windows()
    dialog_check(office, keys, "ctrl+alt+shift+v", "Writer Ctrl+Alt+Shift+V Paste Special (clipboard filled above)")


def _command_state(office, doc, command):
    """The toggle state of a command through a status listener; None when it reports none."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL  # noqa: N811

    class Listener(unohelper.Base, XStatusListener):
        value = None

        def statusChanged(self, event):  # noqa: N802
            self.value = event.State

        def disposing(self, _source):
            pass

    url = URL()
    url.Complete = command
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    frame = doc.getCurrentController().getFrame()
    dispatch = frame.queryDispatch(url, "", 0)
    listener = Listener()
    dispatch.addStatusListener(listener, url)
    dispatch.removeStatusListener(listener, url)
    return listener.value
