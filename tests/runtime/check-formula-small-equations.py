#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: MathType equations smaller than an inch keep their size when they become formulas.

Usage:
    python3 tests/runtime/check-formula-small-equations.py --soffice PATH --docx WORD.docx [--out DIR] [--port 2107]

WORD.docx is a .docx Word saved with MathType equations at 100 %, many smaller than an inch (s037 of the corpus;
files are never stored in the repository). The WMF reader sizes an MM_ANISOTROPIC WMF smaller than its "inch" field
to one inch, so the preview of such an equation is no measure of its size: taken as one, it drew "m=0" at 23 %.
Opened with "tự chuyển khi mở" on, and converted with Chèn > Công thức > Chuyển công thức after the pages are drawn
(the previews are loaded then), no formula may carry a Word scale.
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("check_formula_mathtype", "check-formula-mathtype.py")
shown = load("check_formula_shown_size", "check-formula-shown-size.py")


def scaled(doc):
    """[(height, formula)] of the formulas drawn at a Word scale."""
    found = doc.getEmbeddedObjects()
    result = []
    for name in found.getElementNames():
        item = found.getByName(name)
        if item.CLSID.upper() != base.MATH:
            continue
        control = item.ExtendedControlOverEmbeddedObject
        control.changeState(1)  # RUNNING
        formula = control.getComponent().Formula
        if shown.scale_of(formula) != 1.0:
            result.append((item.Size.Height, formula[:40]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--docx", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "formula-small-equations"))
    parser.add_argument("--port", type=int, default=2107)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    workdir = os.path.abspath(args.out)
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        name = os.path.basename(args.docx)
        base.set_option(office, True)
        doc = office.load(office.url(args.docx))
        wrong = scaled(doc)
        base.record("%s opened: small equations keep their size" % name, not wrong, wrong[:5])
        doc.close(True)
        base.set_option(office, False)
        doc = office.load(office.url(args.docx))
        doc.storeToURL(office.url(os.path.join(workdir, name + ".pdf")),
                       headless_office.props(FilterName="writer_pdf_Export"))  # draws, so loads, every preview
        base.convert_all(office, doc)
        wrong = scaled(doc)
        base.record("%s converted: small equations keep their size" % name, not wrong, wrong[:5])
        doc.close(True)
    finally:
        office.stop()
    failed = [row for row, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
