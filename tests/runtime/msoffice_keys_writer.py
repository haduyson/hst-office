# SPDX-License-Identifier: AGPL-3.0-only
"""HST Writer part of check-msoffice-shortcuts.py: the Microsoft Word keys and their effect."""
from shortcut_keys import check, wait


def dialog_check(office, keys, combo, name):
    found = keys.dialog_after(combo)
    check(f"{name} ({combo} opens a dialog)", found is not None)
    if found:
        print(f"      dialog title: {found[1]!r}")
        keys.close_dialog(found[0])
    office.raise_windows()


def _iterate(text):
    enum = text.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def _count(fields):
    enum, n = fields.createEnumeration(), 0
    while enum.hasMoreElements():
        enum.nextElement()
        n += 1
    return n


def writer_checks(office, keys):
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
    doc = office.load("private:factory/swriter")
    text = doc.getText()
    cur = text.createTextCursor()
    text.insertString(cur, "Xin chào HST Office", False)
    text.insertControlCharacter(cur, PARAGRAPH_BREAK, False)
    text.insertString(cur, "Đoạn hai", False)
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()
    ctrl = doc.getCurrentController()
    paras = lambda: list(_iterate(text))  # noqa: E731
    p1 = lambda: paras()[0]  # noqa: E731
    p2 = lambda: paras()[1]  # noqa: E731

    def caret_in(index):
        para = paras()[index]
        ctrl.select(text.createTextCursorByRange(para.getStart()))

    caret_in(0)
    keys.send("ctrl+2")
    check("Writer Ctrl+2 double line spacing", wait(lambda: p1().ParaLineSpacing.Height == 200, 5), p1().ParaLineSpacing.Height)
    keys.send("ctrl+5")
    check("Writer Ctrl+5 1.5 line spacing", wait(lambda: p1().ParaLineSpacing.Height == 150, 5), p1().ParaLineSpacing.Height)
    keys.send("ctrl+1")
    check("Writer Ctrl+1 single line spacing", wait(lambda: p1().ParaLineSpacing.Height == 100, 5), p1().ParaLineSpacing.Height)
    keys.send("ctrl+e")
    check("Writer Ctrl+E centers", wait(lambda: p1().ParaAdjust == 3, 5), p1().ParaAdjust)
    keys.send("ctrl+l")
    keys.send("ctrl+alt+1")
    check("Writer Ctrl+Alt+1 Heading 1", wait(lambda: p1().ParaStyleName == "Heading 1", 5), p1().ParaStyleName)
    keys.send("ctrl+alt+2")
    check("Writer Ctrl+Alt+2 Heading 2", wait(lambda: p1().ParaStyleName == "Heading 2", 5), p1().ParaStyleName)
    keys.send("ctrl+alt+3")
    check("Writer Ctrl+Alt+3 Heading 3", wait(lambda: p1().ParaStyleName == "Heading 3", 5), p1().ParaStyleName)
    caret_in(1)
    keys.send("F4")
    check("Writer F4 repeats the last action", wait(lambda: p2().ParaStyleName == "Heading 3", 5), p2().ParaStyleName)
    keys.send("ctrl+shift+n")
    check("Writer Ctrl+Shift+N Normal style", wait(lambda: p2().ParaStyleName == "Standard", 5), p2().ParaStyleName)
    caret_in(0)
    keys.send("ctrl+shift+n")

    keys.send("ctrl+m")
    check("Writer Ctrl+M indents", wait(lambda: p1().ParaLeftMargin > 0, 5), p1().ParaLeftMargin)
    keys.send("ctrl+shift+m")
    check("Writer Ctrl+Shift+M removes the indent", wait(lambda: p1().ParaLeftMargin == 0, 5), p1().ParaLeftMargin)
    keys.send("ctrl+t")
    check("Writer Ctrl+T hanging indent", wait(lambda: p1().ParaFirstLineIndent < 0, 5), p1().ParaFirstLineIndent)
    keys.send("ctrl+z")
    keys.send("ctrl+shift+l")
    check("Writer Ctrl+Shift+L bulleted list", wait(lambda: bool(p1().NumberingIsNumber), 5))
    keys.send("ctrl+z")

    ctrl.select(p1())  # the first paragraph selected
    sel = lambda: ctrl.getSelection().getByIndex(0)  # noqa: E731
    size = sel().CharHeight
    keys.send("ctrl+shift+period")
    check("Writer Ctrl+Shift+> grows the font", wait(lambda: sel().CharHeight > size, 5), f"{size} -> {sel().CharHeight}")
    keys.send("ctrl+shift+comma")
    check("Writer Ctrl+Shift+< shrinks the font", wait(lambda: sel().CharHeight == size, 5), f"{size} -> {sel().CharHeight}")
    keys.send("ctrl+equal")
    check("Writer Ctrl+= subscript", wait(lambda: sel().CharEscapement < 0, 5), sel().CharEscapement)
    keys.send("ctrl+shift+equal")
    check("Writer Ctrl+Shift+= superscript", wait(lambda: sel().CharEscapement > 0, 5), sel().CharEscapement)
    keys.send("ctrl+b")
    keys.send("ctrl+space")
    check("Writer Ctrl+Space removes character formatting",
          wait(lambda: sel().CharWeight < 150 and sel().CharEscapement == 0, 5), f"{sel().CharWeight} {sel().CharEscapement}")
    keys.send("ctrl+shift+d")
    check("Writer Ctrl+Shift+D double underline", wait(lambda: sel().CharUnderline == 2, 5), sel().CharUnderline)
    keys.send("ctrl+z")

    # Ctrl+Shift+V pastes text only: copy the bold first paragraph, paste at the end of the second.
    keys.send("ctrl+b")
    keys.send("ctrl+c")
    end = text.createTextCursorByRange(p2().getEnd())
    ctrl.select(end)
    keys.send("ctrl+shift+v")
    pasted = lambda: p2().getString().endswith("Xin chào HST Office")  # noqa: E731
    ok = wait(pasted, 8)
    last = text.createTextCursorByRange(p2().getEnd())
    last.goLeft(1, True)
    check("Writer Ctrl+Shift+V pastes text only", ok and last.CharWeight < 150, f"{p2().getString()!r} {last.CharWeight}")

    fields_before = _count(doc.getTextFields())
    keys.send("alt+shift+d")
    check("Writer Alt+Shift+D inserts a date field", wait(lambda: _count(doc.getTextFields()) > fields_before, 5))

    dialog_check(office, keys, "ctrl+d", "Writer Ctrl+D Font dialog")
    dialog_check(office, keys, "F12", "Writer F12 Save As dialog")
    doc.setModified(False)
