# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check: a document with macros is not saved into a format that loses them without a warning.

Usage: python3 tests/runtime/check-vba-save-format.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-save-format] [--display :91] [--port 22989]

New documents default to .docx/.xlsx/.pptx, which hold no macros. Each file is checked on disk:
  - VBA in Writer/Sheets: Ctrl+S proposes .docm/.xlsm and the file has the project.
  - Plain Basic (VBA formats do not write it) and macros in Slides (.pptm only copies a project read
    from a file): Ctrl+S proposes .odt/.ods/.odp and the reopened file has the module.
  - An open .docx that gained a macro: Ctrl+S warns; going back opens Save As on .docm; "Save without
    Macros" keeps .docx with no project.
  - Save As to a named .docx file: warns, and going back writes nothing.
  - No macros, or only comments: .docx with no warning.
  - A Word-made .docm with edited macros: asked before saving; its VBA project stays.
Exit 1 when any check fails.
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
import msoffice_save_steps as steps  # noqa: E402
from shortcut_keys import RESULTS, Keys, check, wait  # noqa: E402
from vba_save_format_steps import (add_vba, check_edited_word_file, check_named_file, check_open_docx, has_vba_project, press, pv,  # noqa: E402
                                   saved_as, type_name, warning_window)


def standard_library(doc):
    libs = doc.BasicLibraries
    if not libs.hasByName("Standard"):
        libs.createLibrary("Standard")
    libs.loadLibrary("Standard")
    return libs.getByName("Standard")


def add_basic(doc, _app):
    standard_library(doc).insertByName("HstBasic", "Sub Hello\n  Print 1\nEnd Sub\n")


def add_comment_only(doc, _app):
    standard_library(doc).insertByName("HstNote", "' chỉ là ghi chú\nRem không có mã\n")


def add_nothing(_doc, _app):
    pass


def new_save(office, keys, files, case):
    """A new document, its macros added, Ctrl+S, a name typed without an extension."""
    factory, app, add, stem, expected, label = case
    doc = office.load(f"private:factory/{factory}")
    wait(lambda: keys.doc_window() is not None, 20)
    add(doc, app)
    steps._touch(doc)
    steps.focus_document(office, keys)
    path = os.path.join(files, stem)
    picker = keys.dialog_after("ctrl+s")
    check(f"{label}: Ctrl+S opens the file dialog", picker is not None, str(keys.windows()))
    if picker:
        type_name(keys, picker[0], path)
        wait(lambda: saved_as(path) or warning_window(keys), 15)
        warned = warning_window(keys)
        check(f"{label}: the proposed format needs no warning", not warned, str(keys.windows()))
        if warned:
            press(keys, warned, "Escape")
            time.sleep(1)
        found = saved_as(path)
        check(f"{label}: proposed format is {expected}", found == [expected], f"{found} {keys.windows()}")
    steps.close(doc)
    return path + expected


CASES = (("swriter", "writer", add_vba, "vba-writer", ".docm", "Writer VBA"),
         ("scalc", "calc", add_vba, "vba-calc", ".xlsm", "Sheets VBA"),
         ("swriter", "writer", add_basic, "basic-writer", ".odt", "Writer Basic"),
         ("scalc", "calc", add_basic, "basic-calc", ".ods", "Sheets Basic"),
         ("simpress", "impress", add_basic, "basic-slides", ".odp", "Slides Basic"),
         ("swriter", "writer", add_nothing, "plain-writer", ".docx", "No macros"),
         ("swriter", "writer", add_comment_only, "comment-writer", ".docx", "Comments only"))


def run(office, keys, files):
    import uno
    for case in CASES:
        path = new_save(office, keys, files, case)
        label, expected = case[5], case[4]
        if not os.path.exists(path):
            continue
        if expected in (".docm", ".xlsm"):
            check(f"{label}: the file has the VBA project", has_vba_project(path))
        if expected in (".odt", ".ods", ".odp"):
            # the test's own file: without a macro mode the security prompt would wait for an answer
            doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0,
                                                        (pv("MacroExecutionMode", 4),))
            check(f"{label}: the module is in the reopened file", standard_library(doc).hasByName("HstBasic"))
            steps.close(doc)
    check_open_docx(office, keys, files)
    check_named_file(office, keys, files)
    check_edited_word_file(office, keys, os.path.join(hst_gui.ROOT, "upstream/libreoffice/sw/qa/core/data/docm/testFind.docm"), files)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/vba-save-format"))
    parser.add_argument("--display", default=":91")
    parser.add_argument("--port", type=int, default=22989)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    files = os.path.join(work, f"files-{os.getpid()}")
    os.makedirs(files, exist_ok=True)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, work], check=False)
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[("/org.openoffice.Office.Impress/Misc", "StartWithTemplate", "false")])
    try:
        office.start()
        run(office, Keys(office), files)
    except Exception as error:  # noqa: BLE001
        check("run completed", False, repr(error))
    finally:
        office.stop()
    failed = [result for result in RESULTS if not result[1]]
    print(f"SUMMARY {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
