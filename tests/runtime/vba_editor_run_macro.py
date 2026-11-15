# SPDX-License-Identifier: AGPL-3.0-only
"""Part of check-vba-editor.py: a Basic macro runs only when the user asks (HST Slides and HST Draw).

- Run from the editor: "Macro VBA" opens Module1 with the cursor in Sub XinChao; F5 (the editor's
  "Chạy") runs it and its MsgBox, titled with the app name, appears.
- Run from Alt+F8: the Basic Macros dialog opens with the library tree focused on the user's
  Standard.Module1; Tab moves to its macro list (Main selected) and Enter presses the default button
  "Chạy", so the macro's MsgBox appears.
Every key goes to a window this office owns and was found by its title (never to the bare focus).
"""
import re
import time

RUN_TITLE = "HST kiểm tra Alt+F8"
MAIN_CODE = f'Sub Main\n    MsgBox "Chạy từ hộp thoại Macro", 0, "{RUN_TITLE}"\nEnd Sub\n'


def _close_box(ed, office, title):
    """Close the MsgBox found by its exact title with Enter (its only button, OK)."""
    box = ed.window(office, "^" + re.escape(title) + "$")
    if box:
        ed.keys(office, box[0], "Return")
        ed.wait(lambda: ed.window(office, "^" + re.escape(title) + "$") is None, 10)


def check_run_from_editor(ed, office, doc, app, product):
    frame = doc.getCurrentController().getFrame()
    office.dispatch(frame, "org.hst.office.vi:EditVba")
    ide = ed.wait(lambda: ed.window(office, r"HST Office Basic$") is not None, 15)
    if ide:
        time.sleep(2)  # the editor finishes loading the module before it takes keys
        ed.keys(office, ed.window(office, r"HST Office Basic$")[0], "F5")
    shown = ide and ed.wait(lambda: ed.window(office, "^" + re.escape(product) + "$") is not None, 15)
    ed.check(f"{app}: F5 in the editor runs Sub XinChao (its MsgBox shows)", shown, str(ed.hst_gui.toplevels(office.display, office.pid)))
    if shown:
        _close_box(ed, office, product)
    ed.close_ide(office)


def check_run_from_macro_dialog(ed, office, app, title):
    libs = office.service("com.sun.star.script.ApplicationScriptLibraryContainer")
    libs.loadLibrary("Standard")
    standard = libs.getByName("Standard")
    if standard.hasByName("Module1"):
        standard.replaceByName("Module1", MAIN_CODE)
    else:
        standard.insertByName("Module1", MAIN_CODE)
    found = ed.window(office, title)
    if found:
        ed.keys(office, found[0], "alt+F8")
    dialog = found and ed.wait(lambda: ed.window(office, r"Macro Basic|Basic Macros|BASIC Macro") is not None, 10)
    if dialog:
        time.sleep(1.5)
        dialog_wid = ed.window(office, r"Macro Basic|Basic Macros|BASIC Macro")[0]
        ed.keys(office, dialog_wid, "Tab")
        time.sleep(0.8)
        ed.keys(office, dialog_wid, "Return")
    shown = dialog and ed.wait(lambda: ed.window(office, "^" + re.escape(RUN_TITLE) + "$") is not None, 15)
    ed.check(f"{app}: Alt+F8, Chạy runs the selected Basic macro", shown, str(ed.hst_gui.toplevels(office.display, office.pid)))
    if shown:
        _close_box(ed, office, RUN_TITLE)
    left = ed.window(office, r"Macro Basic|Basic Macros|BASIC Macro")
    if left:
        ed.keys(office, left[0], "Escape")
