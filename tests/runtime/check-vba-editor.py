# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check of the "Macro VBA" entry points in HST Sheets and HST Writer (GTK3, fresh Vietnamese profile).

Usage: python3 tests/runtime/check-vba-editor.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-editor] [--display :91] [--port 22979] [--shots DIR]

The X display must already run (e.g. Xvfb :91 -screen 0 1600x1000x24 -nolisten tcp).
  - org.hst.office.vi:EditVba (HST menu / ribbon command) in a new Calc and a new Writer document:
    the Basic IDE opens and the document gets Module1 = Option VBASupport 1 + Vietnamese template,
    in a VBA-mode project (VBAProject / Project); a second call reuses the module.
  - Alt+F11 opens the editor from a document, Alt+F8 opens the Basic Macros dialog (Sheets and Writer).
  - Opening an .xlsm with macros shows the macro security prompt (nothing runs before the answer).
--shots writes the help screenshots (macro-vba-*.png). Exit 1 when any check fails.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python"))
import hst_gui  # noqa: E402
from hst_office import vba, vba_template  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def wait(cond, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001 - UNO objects may be in flux
            pass
        time.sleep(0.4)
    return False


def ide_frame(office):
    frames = office.desktop().getFrames()
    for i in range(frames.getCount()):
        frame = frames.getByIndex(i)
        controller = frame.getController()
        model = controller.getModel() if controller else None
        if model is not None and model.supportsService("com.sun.star.script.BasicIDE"):
            return frame
    return None


def close_ide(office):
    frame = ide_frame(office)
    if frame is not None:
        frame.close(True)
        wait(lambda: ide_frame(office) is None, 10)


def keys(office, wid, combo):
    env = dict(os.environ, DISPLAY=office.display)
    subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "--clearmodifiers", combo], env=env, check=False, timeout=15)


def window(office, pattern):
    import re
    for wid, name in hst_gui.toplevels(office.display, office.pid):
        if re.search(pattern, name):
            return wid, name
    return None


def check_app(office, kind, app, title, shots):
    doc = office.load(f"private:factory/{kind}")
    frame = doc.getCurrentController().getFrame()
    office.dispatch(frame, "org.hst.office.vi:EditVba")
    check(f"{app}: Macro VBA opens the Basic IDE", wait(lambda: ide_frame(office) is not None))
    libs = doc.BasicLibraries
    project = vba_template.project_name(app)
    code = libs.getByName(project).getByName("Module1") if libs.hasByName(project) and libs.getByName(project).hasByName("Module1") else ""
    check(f"{app}: VBA-mode project {project} with Module1 from the template",
          libs.VBACompatibilityMode and libs.ProjectName == project and vba_template.same_text(code, vba_template.module_text(app)),
          f"mode={libs.VBACompatibilityMode} project={libs.ProjectName!r}")
    if shots:
        time.sleep(2)
        office.screenshot(os.path.join(shots, f"macro-vba-editor-{app}.png"))
    close_ide(office)
    office.dispatch(frame, "org.hst.office.vi:EditVba")
    wait(lambda: ide_frame(office) is not None)
    check(f"{app}: a second call reuses Module1", list(libs.getByName(project).ElementNames) == ["Module1"],
          str(list(libs.getByName(project).ElementNames)))
    close_ide(office)
    # Alt+F11 from the document window
    found = wait(lambda: window(office, title) is not None, 10)
    wid = window(office, title)[0] if found else None
    if wid:
        keys(office, wid, "alt+F11")
    check(f"{app}: Alt+F11 opens the VBA editor", wid and wait(lambda: ide_frame(office) is not None))
    close_ide(office)
    if wid:
        keys(office, wid, "alt+F8")
        dialog = wait(lambda: window(office, r"Macro Basic|Basic Macros|Macro") is not None, 10)
        check(f"{app}: Alt+F8 opens the Basic Macros dialog", dialog, str(hst_gui.toplevels(office.display, office.pid)))
        if dialog:
            if shots and app == "calc":
                office.screenshot(os.path.join(shots, "macro-vba-run.png"))
            keys(office, window(office, r"Macro Basic|Basic Macros|Macro")[0], "Escape")
    doc.close(True)


def check_security_prompt(office, out, shots):
    import uno
    from com.sun.star.beans import PropertyValue
    path = os.path.join(out, "prompt.xlsm")
    doc = office.load("private:factory/scalc")
    vba.prepare_document(doc, "calc")  # a VBA project with Module1: the saved file contains macros
    prop = PropertyValue()
    prop.Name, prop.Value = "FilterName", "Calc Office Open XML VBA"
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop,))
    doc.close(True)
    mode = PropertyValue()
    mode.Name, mode.Value = "MacroExecutionMode", 3  # USE_CONFIG: what opening a file from the UI uses
    import threading
    loader = threading.Thread(target=lambda: office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (mode,)),
                              daemon=True)
    loader.start()
    prompt = wait(lambda: window(office, r"[Bb]ảo mật|[Ss]ecurity") is not None, 30)
    check("an .xlsm with macros shows the macro security prompt", prompt, str(hst_gui.toplevels(office.display, office.pid)))
    if prompt:
        if shots:
            office.screenshot(os.path.join(shots, "macro-vba-security.png"))
        keys(office, window(office, r"[Bb]ảo mật|[Ss]ecurity")[0], "Escape")
    loader.join(30)


def check_worksheet_change(office, out):
    """Worksheet_Change of an Excel file runs when the user types into a cell."""
    import shutil
    import uno
    from com.sun.star.beans import PropertyValue
    path = os.path.join(out, "change.xlsm")
    shutil.copyfile(os.path.join(hst_gui.ROOT, "upstream/libreoffice/sc/qa/extras/testdocuments/SimpleCopyPaste.xlsm"), path)
    subprocess.run(["chown", hst_gui.BUILD_USER, path], check=False)
    mode = PropertyValue()
    mode.Name, mode.Value = "MacroExecutionMode", 4  # the test's own file; the prompt is checked separately
    doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (mode,))
    lib = doc.BasicLibraries.getByName(doc.BasicLibraries.ProjectName)
    lib.replaceByName("Sheet1", lib.getByName("Sheet1") + '\nPrivate Sub Worksheet_Change(ByVal Target As Range)\n'
                      '  If Target.Address = "$A$5" Then Range("H2").Value = Target.Value * 2\nEnd Sub\n')
    sheet = doc.Sheets.getByIndex(0)
    found = wait(lambda: window(office, r"HST Sheets$") is not None, 10)
    if found:
        env = dict(os.environ, DISPLAY=office.display)
        wid = window(office, r"HST Sheets$")[0]
        # a click in the sheet area gives the grid keyboard focus; then select A5 and type
        subprocess.run(["xdotool", "mousemove", "--window", wid, "700", "600", "click", "1"], env=env, check=False, timeout=15)
        time.sleep(1)
        doc.getCurrentController().select(sheet.getCellRangeByName("A5"))
        time.sleep(0.5)
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "type", "--delay", "80", "21"], env=env, check=False, timeout=15)
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Return"], env=env, check=False, timeout=15)
        time.sleep(1)
    if sheet.getCellRangeByName("A5").Value != 21:
        office.screenshot(os.path.join(out, "worksheet-change-failed.png"))
        print("windows:", hst_gui.toplevels(office.display, office.pid))
    check("calc: Worksheet_Change runs when the user types into a cell",
          wait(lambda: sheet.getCellRangeByName("H2").Value == 42, 10), f"A5={sheet.getCellRangeByName('A5').Value} H2={sheet.getCellRangeByName('H2').Value}")
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/vba-editor"))
    parser.add_argument("--display", default=":91")
    parser.add_argument("--port", type=int, default=22979)
    parser.add_argument("--shots")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, args.port, display=args.display).start()
    try:
        check_app(office, "scalc", "calc", r"HST Sheets$", args.shots)
        check_app(office, "swriter", "writer", r"HST Writer$", args.shots)
        check_worksheet_change(office, os.path.abspath(args.out))
        check_security_prompt(office, os.path.abspath(args.out), args.shots)
    finally:
        office.stop()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"SUMMARY {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
