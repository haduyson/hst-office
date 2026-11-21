#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: MathType equations smaller than an inch keep their size when they become formulas.

Usage:
    python3 tests/runtime/check-formula-small-equations.py --soffice PATH --docx WORD.docx [--out DIR] [--port 2107]

WORD.docx is a .docx Word saved with MathType equations at 100 %, many smaller than an inch (s037 of the corpus;
files are never stored in the repository). The WMF reader sizes an MM_ANISOTROPIC WMF smaller than its "inch" field
to one inch, so that preview is no measure of the equation: taken as one, it drew "m=0" at 23 %. The size comes from
the WMF's placeable header. The check also writes a copy with every equation shown at 150 % (its v:shape style).
Opened with "tự chuyển khi mở" on, and converted with Chèn > Công thức > Chuyển công thức after the pages are drawn
(the previews are loaded then), no formula of the file may be drawn below half or above twice its size, and each
formula of the copy must be 1.5 times its formula in the file.
"""
import argparse
import importlib.util
import os
import re
import sys
import zipfile

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


OBJECT = re.compile(r"<w:object\b.*?</w:object>", re.S)
LENGTH = re.compile(r"(width|height):([0-9.]+)(pt|in)")


def shown_at(source, target, factor):
    """A copy of the .docx with every equation's shown size times factor, as Word writes a resize."""
    def grow_length(match):
        return "%s:%.3f%s" % (match.group(1), float(match.group(2)) * factor, match.group(3))

    def grow(match):
        return re.sub(r'(<v:shape\b[^>]*?style=")([^"]*)', lambda m: m.group(1) + LENGTH.sub(grow_length, m.group(2)),
                      match.group(0), count=1)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as new:
        for item in old.infolist():
            data = old.read(item.filename)
            if item.filename == "word/document.xml":
                data = OBJECT.sub(grow, data.decode("utf-8")).encode("utf-8")
            new.writestr(item, data)


def scales(doc):
    """{object name: Word scale of its formula} of the formulas."""
    found = doc.getEmbeddedObjects()
    result = {}
    for name in found.getElementNames():
        item = found.getByName(name)
        if item.CLSID.upper() == base.MATH:
            control = item.ExtendedControlOverEmbeddedObject
            control.changeState(1)  # RUNNING
            result[name] = shown.scale_of(control.getComponent().Formula)
    return result


def formulas(office, path, convert):
    """Scales of the formulas of path, opened with the option on, or converted after the pages are drawn."""
    base.set_option(office, not convert)
    doc = office.load(office.url(path))
    if convert:
        office.store(doc, office.url(path + ".pdf"), FilterName="writer_pdf_Export")
        base.convert_all(office, doc)
    result = scales(doc)
    doc.close(True)
    return result


def compare(office, path, grown, convert):
    how = "converted" if convert else "opened"
    at_100, at_150 = formulas(office, path, convert), formulas(office, grown, convert)
    wrong = [(n, s) for n, s in at_100.items() if not 0.5 <= s <= 2]
    base.record("%s %s: no equation drawn below half or above twice its size" % (os.path.basename(path), how),
                at_100 and not wrong, {"formulas": len(at_100), "wrong": wrong[:5]})
    off = [(n, at_100[n], s) for n, s in at_150.items() if n in at_100 and abs(s / at_100[n] - 1.5) > 0.05]
    base.record("%s %s: every equation shown at 150 %% is 1.5 times as large" % (os.path.basename(path), how),
                at_150 and not off and len(at_150) == len(at_100), {"formulas": len(at_150), "off": off[:5]})


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
        path = os.path.join(workdir, os.path.basename(args.docx))
        with open(args.docx, "rb") as source, open(path, "wb") as target:
            target.write(source.read())
        grown = path.replace(".docx", "-150.docx")
        shown_at(path, grown, 1.5)
        for convert in (False, True):
            compare(office, path, grown, convert)
    finally:
        office.stop()
    failed = [row for row, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
