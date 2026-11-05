# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: a VBA project read from a real Office file is written back with every stream unchanged.

Usage: python3 tests/runtime/check-vba-keep-word-project.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-keep-word] [--port 22993]

Word does not open a project written by VbaExport, so saving a Word-made .docm in HST must keep its
vbaProject.bin, with the macros unchanged and also after they were edited in HST (Save As asks first).
Excel does not load forms VbaExport writes: an Excel file keeps its project when macros are unchanged,
and when it has forms. Macros edited in an Excel file without forms are saved. This says nothing about
what real Office does with any file.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from vba_form_structure import module_sources, open_project  # noqa: E402

SPEC = importlib.util.spec_from_file_location("check_vba", os.path.join(HERE, "check-vba.py"))
check_vba = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_vba)
BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
# Word-made: docProps/app.xml names Microsoft Office Word
WORD_FILES = ("sw/qa/core/data/docm/testFind.docm", "sw/qa/core/data/docm/testVBA.docm", "sw/qa/core/data/docm/testWords.docm")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def project_streams(path):
    """{stream path: bytes}: the import of .doc, .docm and .xls rewrites the compound file around the same streams."""
    cfb, root = open_project(path)

    def walk(entry, prefix):
        out = {}
        for name, item in cfb.children(entry).items():
            if item["type"] == 1:
                out.update(walk(item, prefix + name + "/"))
            else:
                out[prefix + name] = cfb.read(item)
        return out
    return walk(root, "")


def project_part(path):
    with zipfile.ZipFile(path) as package:
        return package.read(next(n for n in package.namelist() if n.endswith("vbaProject.bin")))


def save_copy(office, source, out, edit, filter_name="MS Word 2007 XML VBA", ext=""):
    import uno
    name = os.path.basename(source)
    work = os.path.join(out, ("edited-" if edit else "plain-") + name + ext)
    doc = office.load(source)
    try:
        if edit:
            libs = doc.BasicLibraries
            library = libs.getByName(libs.ProjectName)
            module = next(n for n in library.ElementNames if library.getModuleInfo(n).ModuleType == 1 or n == "ThisDocument")
            library.replaceByName(module, library.getByName(module) + "\nSub HstEdited()\nEnd Sub\n")
        doc.storeToURL(uno.systemPathToFileUrl(work), (check_vba.pv("FilterName", filter_name),))
    finally:
        doc.close(True)
    return work


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/vba-keep-word"))
    parser.add_argument("--port", type=int, default=22993)
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
        for rel in WORD_FILES:
            source = os.path.join(ROOT, "upstream/libreoffice", rel)
            original = project_streams(source)
            name = os.path.basename(rel)
            check(f"{name}: unchanged macros: every stream of the project kept", project_streams(save_copy(office, source, args.out, False)) == original)
            check(f"{name}: edited macros: original project kept", project_streams(save_copy(office, source, args.out, True)) == original)
        xlsm, xls = ("Calc MS Excel 2007 VBA XML", ".xlsm"), ("MS Excel 97", ".xls")
        form = os.path.join(ROOT, "upstream/libreoffice/sc/qa/extras/testdocuments/MiscControlTests.xls")
        original = project_streams(form)
        for filter_name, ext in (xlsm, xls):
            check(f"Excel .xls with a form to {ext}: unchanged macros: project kept", project_streams(save_copy(office, form, args.out, False, filter_name, ext)) == original)
            check(f"Excel .xls with a form to {ext}: edited macros: project kept", project_streams(save_copy(office, form, args.out, True, filter_name, ext)) == original)
        plain = os.path.join(ROOT, "upstream/libreoffice/sc/qa/unit/data/xlsm/vba-user-function.xlsm")
        same = save_copy(office, plain, args.out, False, *xlsm)
        check("Excel .xlsm: unchanged macros: vbaProject.bin byte for byte", project_part(same) == project_part(plain))
        edited = save_copy(office, plain, args.out, True, *xlsm)
        check("Excel .xlsm without forms: edited macros are saved", any(b"HstEdited" in code for code in module_sources(edited).values()))
    finally:
        office.stop()
    shutil.rmtree(os.path.join(args.out, "__pycache__"), ignore_errors=True)
    print(f"SUMMARY {sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
