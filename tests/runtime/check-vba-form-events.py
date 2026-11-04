# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check of VBA UserForm behaviour in HST Sheets and HST Writer (GTK3, X display must already run).

Usage: python3 tests/runtime/check-vba-form-events.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-form-events] [--display :91] [--port 22985]

  - A dialog inserted in the editor is a UserForm that VBA code can use and show.
  - A real mouse click on CommandButton1 runs CommandButton1_Click, on a new form and on a form
    reopened from .xlsm, .xls, .docm and .doc (the handler reads TextBox1 and writes to the document).
  - Saving a form with only common controls shows no warning; a form with an image control warns.
Exit 1 when any check fails.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import threading
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
from vba_form_fixture import BODY, EXTRA, add_form  # noqa: E402

SPEC = importlib.util.spec_from_file_location("check_vba_editor", os.path.join(HERE, "check-vba-editor.py"))
editor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(editor)
check, wait, ide_frame, close_ide, keys = editor.check, editor.wait, editor.ide_frame, editor.close_ide, editor.keys
vba, vba_template = editor.vba, editor.vba_template
FORM_TITLE = "Biểu mẫu HST"
HINT_TITLE = "Macro VBA"
EXPECTED = "đã bấm: nội dung"
# CommandButton1 centre as a share of the 230 x 170 form (see BODY)
BUTTON_X, BUTTON_Y = 40 / 230, 15 / 170


def check_userform(office, kind, app):
    """A dialog inserted in the editor of a VBA-mode document is a UserForm that VBA code can use."""
    doc = office.load(f"private:factory/{kind}")
    office.dispatch(doc.getCurrentController().getFrame(), "org.hst.office.vi:EditVba")
    wait(lambda: ide_frame(office) is not None)
    office.dispatch(ide_frame(office), ".uno:NewDialog")
    project = vba_template.project_name(app)
    dialogs = doc.DialogLibraries
    ok = wait(lambda: dialogs.hasByName(project) and dialogs.getByName(project).hasByName("UserForm1"), 10)
    lib = doc.BasicLibraries.getByName(project)
    form = lib.hasByName("UserForm1") and lib.getModuleInfo("UserForm1").ModuleType == 3
    check(f"{app}: a new dialog in the editor is UserForm1 with its form module", ok and form,
          f"dialog={ok} module={lib.hasByName('UserForm1')}")
    close_ide(office)
    vba.add_module(lib, "HstForm", vba_template.OPTION_LINE + '\nFunction T()\n  UserForm1.Caption = "Biểu mẫu HST"\n'
                   '  T = UserForm1.Caption\n  Unload UserForm1\nEnd Function\n')
    try:
        got = doc.getScriptProvider().getScript(
            f"vnd.sun.star.script:{project}.HstForm.T?language=Basic&location=document").invoke((), (), ())[0]
    except Exception as error:  # noqa: BLE001
        got = repr(error)
    check(f"{app}: VBA code uses the new UserForm (UserForm1.Caption, Unload)", got == "Biểu mẫu HST", got)
    # UserForm1.Show is modal: the form window appears until it is closed
    import threading
    vba.add_module(lib, "HstShow", vba_template.OPTION_LINE + '\nSub HienForm()\n  UserForm1.Caption = "Biểu mẫu HST"\n  UserForm1.Show\nEnd Sub\n')
    show = doc.getScriptProvider().getScript(f"vnd.sun.star.script:{project}.HstShow.HienForm?language=Basic&location=document")
    runner = threading.Thread(target=lambda: show.invoke((), (), ()), daemon=True)
    runner.start()
    shown = wait(lambda: window(office, FORM_TITLE) is not None, 15)
    check(f"{app}: UserForm1.Show shows the form", shown, str(hst_gui.toplevels(office.display, office.pid)))
    if shown:
        hst_gui.send_close_request(window(office, FORM_TITLE)[0], office.display)
    runner.join(15)
    doc.close(True)


def window(office, title):
    """The window with this title. A caption read from Windows-1258 has combining marks: compare in NFC."""
    title = title.lstrip("^").rstrip("$")
    for wid, name in hst_gui.toplevels(office.display, office.pid):
        if unicodedata.normalize("NFC", name) == title or (title.startswith("HST") and name.endswith(title)):
            return wid, name
    return None


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


def doc_value(doc, app):
    if app == "calc":
        return doc.Sheets.getByIndex(0).getCellRangeByName("A1").String
    return doc.Text.String.strip()


def same_text(a, b):
    """Text from a macro stored in Windows-1258 has combining marks: compare in NFC."""
    return unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b)


def click_button(office, doc, project, app, label):
    """Show the form, click CommandButton1 with the mouse, and check what the handler wrote."""
    show = doc.getScriptProvider().getScript(f"vnd.sun.star.script:{project}.HstForms.ShowForm?language=Basic&location=document")
    runner = threading.Thread(target=lambda: show.invoke((), (), ()), daemon=True)
    runner.start()
    shown = wait(lambda: window(office, FORM_TITLE) is not None, 20)
    check(f"{label}: the form window opens", shown, str(hst_gui.toplevels(office.display, office.pid)))
    if not shown:
        return
    wid = window(office, FORM_TITLE)[0]
    env = dict(os.environ, DISPLAY=office.display)
    geometry = subprocess.run(["xdotool", "getwindowgeometry", "--shell", wid], env=env, capture_output=True, text=True,
                              check=False, timeout=15).stdout
    size = dict(line.split("=") for line in geometry.split())
    x, y = int(int(size["WIDTH"]) * BUTTON_X), int(int(size["HEIGHT"]) * BUTTON_Y)
    time.sleep(1)
    subprocess.run(["xdotool", "mousemove", "--window", wid, str(x), str(y), "click", "1"], env=env, check=False, timeout=15)
    ran = wait(lambda: same_text(doc_value(doc, app), EXPECTED), 10)
    if not ran:
        office.screenshot(os.path.join(office.workdir, f"click-failed-{label.replace(' ', '_').replace('.', '')}.png"))
    check(f"{label}: CommandButton1_Click runs on a mouse click", ran, repr(doc_value(doc, app)))
    if window(office, FORM_TITLE) is not None:
        hst_gui.send_close_request(window(office, FORM_TITLE)[0], office.display)
    runner.join(15)


def check_click(office, kind, app, ext, filter_name):
    import uno
    label = f"{app} .{ext}"
    doc = office.load(f"private:factory/{kind}")
    add_form(office.ctx, doc, app, BODY)
    project = vba_template.project_name(app)
    if ext == "xlsm" or ext == "docm":
        click_button(office, doc, project, app, f"{app} new form")
        if app == "calc":
            doc.Sheets.getByIndex(0).getCellRangeByName("A1").String = ""
        else:
            doc.Text.String = ""
    path = os.path.join(office.workdir, f"click-{app}.{ext}")
    saver = threading.Thread(target=lambda: doc.storeAsURL(uno.systemPathToFileUrl(path), (pv("FilterName", filter_name),)), daemon=True)
    saver.start()
    warned = wait(lambda: window(office, HINT_TITLE) is not None, 6)
    check(f"{label}: saving common controls shows no warning", not warned)
    if warned:
        keys(office, window(office, HINT_TITLE)[0], "Return")
    saver.join(30)
    doc.close(True)
    doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (pv("MacroExecutionMode", 4),))
    click_button(office, doc, doc.BasicLibraries.ProjectName or project, app, f"{label} reopened")
    doc.close(True)


def check_warning(office, kind, app, ext, filter_name):
    """A control that cannot be written is named in a Vietnamese warning after saving."""
    import uno
    doc = office.load(f"private:factory/{kind}")
    add_form(office.ctx, doc, app, BODY + EXTRA)
    path = os.path.join(office.workdir, f"warn-{app}.{ext}")
    saver = threading.Thread(target=lambda: doc.storeAsURL(uno.systemPathToFileUrl(path), (pv("FilterName", filter_name),)), daemon=True)
    saver.start()
    warned = wait(lambda: window(office, HINT_TITLE) is not None, 20)
    check(f"{app} .{ext}: a form with an image control warns after saving", warned,
          str(hst_gui.toplevels(office.display, office.pid)))
    if warned:
        keys(office, window(office, HINT_TITLE)[0], "Return")
    saver.join(20)
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/vba-form-events"))
    parser.add_argument("--display", default=":91")
    parser.add_argument("--port", type=int, default=22985)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, args.port, display=args.display).start()
    try:
        check_userform(office, "scalc", "calc")
        check_userform(office, "swriter", "writer")
        for kind, app, ext, filter_name in (("scalc", "calc", "xlsm", "Calc MS Excel 2007 VBA XML"), ("scalc", "calc", "xls", "MS Excel 97"),
                                            ("swriter", "writer", "docm", "MS Word 2007 XML VBA"), ("swriter", "writer", "doc", "MS Word 97")):
            check_click(office, kind, app, ext, filter_name)
        check_warning(office, "scalc", "calc", "xlsm", "Calc MS Excel 2007 VBA XML")
        check_warning(office, "swriter", "writer", "docm", "MS Word 2007 XML VBA")
    finally:
        office.stop()
    failed = [name for name, ok in editor.RESULTS if not ok]
    print(f"SUMMARY {len(editor.RESULTS) - len(failed)}/{len(editor.RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
