# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: a VBA project read from a real Word file is written back with every stream unchanged.

Usage: python3 tests/runtime/check-vba-keep-word-project.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/vba-keep-word] [--port 22993]

Word does not open a project written by VbaExport, so saving a Word-made .docm in HST must keep its
vbaProject.bin, with the macros unchanged and also after they were edited in HST (which Writer warns
about). This says nothing about what real Word does with any file.
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
from vba_cfb import Cfb  # noqa: E402

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
    """{stream path: bytes}: the import rewrites the compound file around the same streams."""
    with zipfile.ZipFile(path) as package:
        cfb = Cfb(package.read("word/vbaProject.bin"))

    def walk(entry, prefix):
        out = {}
        for name, item in cfb.children(entry).items():
            if item["type"] == 1:
                out.update(walk(item, prefix + name + "/"))
            else:
                out[prefix + name] = cfb.read(item)
        return out
    return walk(cfb.entries[0], "")


def save_copy(office, source, out, edit):
    import uno
    name = os.path.basename(source)
    work = os.path.join(out, ("edited-" if edit else "plain-") + name)
    doc = office.load(source)
    try:
        if edit:
            libs = doc.BasicLibraries
            library = libs.getByName(libs.ProjectName)
            module = library.ElementNames[0]
            library.replaceByName(module, library.getByName(module) + "\nSub HstEdited()\nEnd Sub\n")
        doc.storeToURL(uno.systemPathToFileUrl(work), (check_vba.pv("FilterName", "MS Word 2007 XML VBA"),))
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
    finally:
        office.stop()
    shutil.rmtree(os.path.join(args.out, "__pycache__"), ignore_errors=True)
    print(f"SUMMARY {sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
