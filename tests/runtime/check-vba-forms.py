# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: VBA UserForms survive saving as .xlsm, .xls, .docm and .doc (headless, soffice as hstbuild).

Usage: python3 tests/runtime/check-vba-forms.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-forms] [--port 22983]

A form with every common control (Label, TextBox, CommandButton, CheckBox, OptionButton, ComboBox,
ListBox, Frame with a control inside, plus Toggle, Spin, Scroll) is saved and reopened: the form module
stays a form, controls and properties match the dialog, the file passes the structural MS-OFORMS and
MS-OVBA check, and VBA code can read the controls. A form with an image control leaves that control
out of the file. Real Microsoft Office is not involved: see scripts/windows/probe-excel-userform.ps1.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "extensions/hst-vietnamese-tools/python"))
from hst_office import vba  # noqa: E402
from hst_office.vba_template import project_name, unwritable_form_content  # noqa: E402
import vba_form_structure  # noqa: E402
from vba_form_fixture import BODY, EXTRA, add_form, controls_of, dialog_xml, read_dialog  # noqa: E402
from vba_word_macro_list import check_word_macro_list  # noqa: E402

SPEC = importlib.util.spec_from_file_location("check_vba", os.path.join(HERE, "check-vba.py"))
check_vba = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_vba)
BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
RESULTS = []
TEXT_IN_BOX = ("button", "checkbox", "radio", "textfield", "combobox", "togglebutton")


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def nfc(text):
    """Only for what the fixture typed: the files must give back exactly this."""
    return unicodedata.normalize("NFC", text) if text else text


def check_saved(office, kind, app, ext, filt, out):
    import uno
    pv, run = check_vba.pv, check_vba.run
    path = os.path.join(out, f"form-{app}.{ext}")
    doc = office.new(kind)
    add_form(office.ctx, doc, app, BODY)
    before, title = controls_of(read_dialog(doc, vba.prepare_document(doc, app)[0]))
    doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", filt),))
    doc.close(True)
    if ext not in ("ods", "odt"):
        problems, forms = vba_form_structure.check_file(path)
        check(f".{ext}: file structure (MS-CFB, MS-OVBA, MS-OFORMS)", not problems, problems)
        check(f".{ext}: all controls are in the form stream", set(forms.get("UserForm1", [])) == set(before), forms)
    doc = office.load(path)
    try:
        project = doc.BasicLibraries.ProjectName or project_name(app)
        library = doc.BasicLibraries.getByName(project)
        check(f".{ext}: reopened: UserForm1 is a form module", library.getModuleInfo("UserForm1").ModuleType == 3)
        check(f".{ext}: form code kept", "CommandButton1_Click" in library.getByName("UserForm1"))
        xml = read_dialog(doc, project)
        check(f".{ext}: reopened: dialog present", xml is not None)
        if not xml:
            return
        after, new_title = controls_of(xml)
        check(f".{ext}: caption kept, composed", new_title == title, new_title)
        missing = set(before) - set(after)
        check(f".{ext}: every control kept", not missing, missing)
        for name in set(before) & set(after):
            a, b = before[name], after[name]
            # controls made in HST get the height a Tahoma 8 caption needs in a box: 660/100 mm, about 15 units
            grown = (*a["box"][:3], max(a["box"][3], 15) if a["tag"] in TEXT_IN_BOX and ext not in ("ods", "odt") else a["box"][3])
            near = all(abs(x - y) <= 2 for x, y in zip(grown, b["box"]))
            same = a["tag"] == b["tag"] and nfc(a["value"]) == nfc(b["value"]) and bool(a["checked"]) == bool(b["checked"])
            check(f".{ext}: {name} type, text and state", same, f"{a} -> {b}")
            check(f".{ext}: {name} geometry within 2 units", near, f"{a['box']} -> {b['box']}")
        if ext not in ("ods", "odt"):  # running forms from ODF files: see check-vba-form-events.py
            got = run(doc, project, "HstForms", "DocForm")
            check(f".{ext}: VBA reads the controls", got == "Biểu mẫu HST|nội dung|Nhãn tiếng Việt", got)
            same = run(doc, project, "HstForms", "SameText")
            check(f".{ext}: literals and captions compare equal to composed text", same == "True|True|True", same)
            check_resaved(office, doc, app, ext, filt, out, after)
    finally:
        doc.close(True)


def check_resaved(office, doc, app, ext, filt, out, first):
    """A form that came from a file (nested frames, imported models) is written again without change."""
    import uno
    path = os.path.join(out, f"form-{app}-again.{ext}")
    doc.storeToURL(uno.systemPathToFileUrl(path), (check_vba.pv("FilterName", filt),))
    problems, _forms = vba_form_structure.check_file(path)
    check(f".{ext}: saved again: file structure", not problems, problems)
    first_path = os.path.join(out, f"form-{app}.{ext}")
    changed = [name for name, code in vba_form_structure.module_sources(first_path).items()
               if vba_form_structure.module_sources(path).get(name) != code]
    check(f".{ext}: saved again: module bytes unchanged", not changed, changed)
    again = office.load(path)
    try:
        xml = read_dialog(again, again.BasicLibraries.ProjectName or project_name(app))
        second = controls_of(xml)[0] if xml else {}
        check(f".{ext}: saved again: same controls, text and position", second == first,
              {k: (first.get(k), second.get(k)) for k in set(first) | set(second) if first.get(k) != second.get(k)})
    finally:
        again.close(True)


def check_fixture(office, out):
    """A real form from an Excel file, written to .xlsm and .xls."""
    import uno
    source = os.path.join(ROOT, "upstream/libreoffice/sc/qa/extras/testdocuments/MiscControlTests.xls")
    doc = office.load(source)
    try:
        project = doc.BasicLibraries.ProjectName
        before = controls_of(read_dialog(doc, project))[0]
        for ext, filt in (("xlsm", "Calc MS Excel 2007 VBA XML"), ("xls", "MS Excel 97")):
            path = os.path.join(out, f"fixture.{ext}")
            doc.storeToURL(uno.systemPathToFileUrl(path), (check_vba.pv("FilterName", filt),))
            problems, _forms = vba_form_structure.check_file(path)
            check(f"Excel fixture .{ext}: file structure", not problems, problems)
            again = office.load(path)
            try:
                after = controls_of(read_dialog(again, again.BasicLibraries.ProjectName))[0]
                missing = set(before) - set(after)
                check(f"Excel fixture .{ext}: all {len(before)} controls kept", not missing, missing)
                changed = {k: (before[k]["tag"], after[k]["tag"]) for k in set(before) & set(after)
                           if before[k]["tag"] != after[k]["tag"]}
                check(f"Excel fixture .{ext}: control types kept", not changed, changed)
            finally:
                again.close(True)
    finally:
        doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/vba-forms"))
    parser.add_argument("--port", type=int, default=22983)
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", BUILD_USER, args.out], check=True)
        os.execvp("runuser", ["runuser", "-u", BUILD_USER, "--", sys.executable] + sys.argv)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    sys.path.insert(0, program)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    office = check_vba.Office(program, args.out, args.port).start()
    try:
        for kind, app, ext, filt in (("scalc", "calc", "xlsm", "Calc MS Excel 2007 VBA XML"), ("scalc", "calc", "xls", "MS Excel 97"),
                                     ("scalc", "calc", "ods", "calc8"), ("swriter", "writer", "docm", "MS Word 2007 XML VBA"),
                                     ("swriter", "writer", "doc", "MS Word 97"), ("swriter", "writer", "odt", "writer8")):
            check_saved(office, kind, app, ext, filt, args.out)
        check_fixture(office, args.out)
        check_word_macro_list(office, args.out, check, check_vba.pv, 'MS Word 2007 XML VBA')
    finally:
        office.stop()
    lost, _items = unwritable_form_content(dialog_xml(BODY + EXTRA))
    check("an image control is reported as not writable", lost == ["Image1"], lost)
    print(f"SUMMARY {sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
