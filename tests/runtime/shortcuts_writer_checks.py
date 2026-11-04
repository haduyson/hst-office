# SPDX-License-Identifier: AGPL-3.0-only
"""Writer part of check-shortcuts.py: the standard keys on a real HST Writer window."""
import os

from shortcut_keys import check, wait


def writer_checks(office, keys, work, tag):
    from com.sun.star.beans import PropertyValue
    doc = office.load("private:factory/swriter")
    frame = doc.getCurrentController().getFrame()
    text = doc.getText()
    text.setString("Xin chào HST Office")
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()

    keys.send("ctrl+a")
    sel = lambda: doc.getCurrentController().getSelection().getByIndex(0)  # noqa: E731
    check(f"{tag} Writer Ctrl+A selects all", wait(lambda: sel().getString() == "Xin chào HST Office", 5),
          repr(sel().getString()))
    keys.send("ctrl+b")
    check(f"{tag} Writer Ctrl+B bold", wait(lambda: sel().CharWeight >= 150, 5), str(sel().CharWeight))
    keys.send("ctrl+i")
    check(f"{tag} Writer Ctrl+I italic", wait(lambda: sel().CharPosture.value != "NONE", 5), str(sel().CharPosture))
    keys.send("ctrl+u")
    check(f"{tag} Writer Ctrl+U underline", wait(lambda: sel().CharUnderline == 1, 5), str(sel().CharUnderline))
    keys.send("ctrl+z")
    check(f"{tag} Writer Ctrl+Z undo", wait(lambda: sel().CharUnderline == 0, 5), str(sel().CharUnderline))
    keys.send("ctrl+y")
    check(f"{tag} Writer Ctrl+Y redo", wait(lambda: sel().CharUnderline == 1, 5), str(sel().CharUnderline))
    if tag == "vi":
        keys.send("ctrl+a")
        keys.send("ctrl+x")
        check(f"{tag} Writer Ctrl+X cut", wait(lambda: text.getString() == "", 5), repr(text.getString()))
        keys.send("ctrl+v")
        check(f"{tag} Writer Ctrl+V paste", wait(lambda: text.getString() == "Xin chào HST Office", 8),
              repr(text.getString()))
    # Ctrl+S on a stored ODF document saves in place without any dialog.
    url = "file://" + os.path.join(work, f"shortcut-{tag}.odt")
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", "writer8"
    doc.storeAsURL(url, (arg,))
    text.getEnd().setString(" — sửa")
    check(f"{tag} Writer document modified before Ctrl+S", doc.isModified())
    before = {w for w, _ in keys.windows()}
    keys.send("ctrl+s")
    saved = wait(lambda: not doc.isModified(), 10)
    extra = [n for w, n in keys.windows() if w not in before]
    check(f"{tag} Writer Ctrl+S saves without a dialog", saved and not extra, f"modified={doc.isModified()} new={extra}")

    keys.send("ctrl+f")
    layout = frame.LayoutManager
    check(f"{tag} Writer Ctrl+F shows the find toolbar",
          wait(lambda: layout.isElementVisible("private:resource/toolbar/findbar"), 5))
    keys.send("Escape")

    dialogs = [("ctrl+h", "Find & Replace"), ("ctrl+shift+s", "Save As"), ("F12", "Save As"), ("ctrl+o", "Open"), ("ctrl+p", "Print")]
    if tag == "vi":
        dialogs.append(("F7", "Spelling"))
    for combo, what in dialogs:
        found = keys.dialog_after(combo)
        check(f"{tag} Writer {combo} opens {what}", found is not None)
        if found:
            print(f"      dialog title: {found[1]!r}")
            check(f"{tag} Writer {what} closes with Escape", keys.close_dialog(found[0]))
        office.raise_windows()
    return doc
