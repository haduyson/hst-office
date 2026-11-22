#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Runtime check: Chèn > Công thức > Chuyển công thức keeps the page count of a document.

Usage:
    python3 tests/runtime/check-formula-convert-pages.py --soffice PATH --docx WORD.docx [--docx ...] [--out DIR]
        [--port 2108]

WORD.docx are documents with MathType equations (s002, s035, s037 of the corpus; files are never stored in the
repository). Math's box is shorter than MathType's for the same point size, so formulas sized to it shortened every
line holding one (s037: 48 pages became 46); a converted formula keeps its equation's room in the line. Each file is
copied, opened, saved as PDF, converted, saved as PDF again (to compare the lines by eye) and counted: the page count
must not change.
"""
import argparse
import importlib.util
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_formula_mathtype",
                                       os.path.join(HERE, "check-formula-mathtype.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


def pdf(office, doc, path):
    office.store(doc, office.url(path), FilterName="writer_pdf_Export")


def check(office, source, workdir):
    path = os.path.join(workdir, os.path.basename(source))
    shutil.copyfile(source, path)
    doc = office.load(office.url(path))
    before = doc.getCurrentController().PageCount
    pdf(office, doc, path + ".before.pdf")
    seconds = base.convert_all(office, doc)
    after = doc.getCurrentController().PageCount
    math = sum(doc.getEmbeddedObjects().getByName(n).CLSID.upper() == base.MATH
               for n in doc.getEmbeddedObjects().getElementNames())
    pdf(office, doc, path + ".after.pdf")
    doc.close(True)
    base.record("%s keeps its pages when converted" % os.path.basename(source), math and before == after,
                {"before": before, "after": after, "formulas": math, "seconds": seconds})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--docx", action="append", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "formula-convert-pages"))
    parser.add_argument("--port", type=int, default=2108)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    workdir = os.path.abspath(args.out)
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        base.set_option(office, False)
        for source in args.docx:
            check(office, source, workdir)
    finally:
        office.stop()
    failed = [name for name, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
