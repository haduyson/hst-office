# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check: deleting every macro of a Word-made .docm, then Ctrl+S, asks and saves the text (never a silent no-op).

Usage: python3 tests/runtime/check-vba-remove-all-macros.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-remove-all] [--display :91] [--port 22995]

The X display must already run. With no macro left, Ctrl+S first asks whether to keep the file's format
(a title-less dialog; the question is skipped while macros exist); keeping it asks whether to save without
the macro edits, because a Word file keeps the project it was read with. Answering both saves the text.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python"))
import hst_gui  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def viewable_dialogs(display):
    """Title-less dialogs of the office that are on screen: (width, height, x, y)."""
    env = dict(os.environ, DISPLAY=display)
    tree = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
    found = set()
    for line in tree.splitlines():
        m = re.match(r'\s+(0x[0-9a-f]+) \(has no name\): \("soffice" "Soffice"\)\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', line)
        if m and 500 < int(m.group(2)) < 1400 and int(m.group(3)) > 150:
            state = subprocess.run(["xwininfo", "-id", m.group(1)], env=env, capture_output=True, text=True).stdout
            if "IsViewable" in state:
                found.add(tuple(int(x) for x in m.groups()[1:]))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/vba-remove-all"))
    parser.add_argument("--display", default=":91")
    parser.add_argument("--port", type=int, default=22995)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    import uno
    import msoffice_save_steps as steps
    from shortcut_keys import Keys, wait
    from vba_save_format_steps import press, pv, warning_window
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    office = hst_gui.Office(args.instdir, out, args.port, display=args.display).start()
    keys = Keys(office)
    try:
        office.load("private:factory/swriter")
        wait(lambda: office.close_welcome(), 25)
        source = os.path.join(hst_gui.ROOT, "upstream/libreoffice/sw/qa/core/data/docm/testFind.docm")
        path = os.path.join(out, "remove-all.docm")
        shutil.copyfile(source, path)
        subprocess.run(["chown", "hstbuild", path], check=False)
        doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (pv("MacroExecutionMode", 4),))
        steps.focus_document(office, keys)
        library = doc.BasicLibraries.getByName(doc.BasicLibraries.ProjectName)
        for name in [n for n in library.ElementNames if library.getModuleInfo(n).ModuleType == 1]:
            library.removeByName(name)
        doc.Text.getEnd().setString(" HST text edit")
        office.raise_windows()
        before = viewable_dialogs(args.display)
        keys.send("ctrl+s")
        wait(lambda: viewable_dialogs(args.display) - before or not doc.isModified(), 120)
        dialog = sorted(viewable_dialogs(args.display) - before)
        check("no macro left: Ctrl+S asks whether to keep the format", bool(dialog), str(keys.windows()))
        if dialog:
            w, h, x, y = dialog[0]  # the button on the right keeps the file's format
            subprocess.run(["xdotool", "mousemove", str(x + w - 160), str(y + h - 32), "click", "1"],
                           env=dict(os.environ, DISPLAY=args.display), check=False)
        asked = wait(lambda: warning_window(keys) is not None, 30)
        check("keeping it asks about the macro edits", asked, str(keys.windows()))
        if asked:
            press(keys, warning_window(keys), "shift+Tab", "Return")
        check("saving without the edits saves", wait(lambda: not doc.isModified(), 60), str(keys.windows()))
        with zipfile.ZipFile(path) as package:
            check("the text edit is in the file", b"HST text edit" in package.read("word/document.xml"))
            check("the project read from the file stays", "word/vbaProject.bin" in package.namelist())
        steps.close(doc)
    finally:
        office.stop()
    print(f"SUMMARY {sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
