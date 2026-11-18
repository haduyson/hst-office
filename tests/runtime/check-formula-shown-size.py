#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: a MathType equation resized in Word keeps the scale Word shows it at once it becomes a formula,
opened from .rtf, .docx and .doc with "tự chuyển khi mở" on, and with Chèn > Công thức > Chuyển công thức.

Usage:
    python3 tests/runtime/check-formula-shown-size.py --soffice PATH --rtf ONE_EQUATION.rtf [--doc WORD.doc ...]
        [--out DIR] [--port 2105]

ONE_EQUATION.rtf is an .rtf Word saved with one MathType 4-7 equation at 100 %; WORD.doc are .doc files Word saved
with MathType equations, some resized (files are never stored in the repository). The check writes the .rtf shown at
60 % and 140 % as Word does (\\objw/\\objh, \\picwgoal/\\pichgoal) and saves each as .docx with the option off. With
the option on, and with the convert command on the .rtf files, the formula at 60 % / 140 % must be that share of the
formula at 100 %, which stays as MathType made it. In the .doc files every converted formula must be drawn at the
scale Word shows its equation at: shown size over the OLE object's own size (PICF scale), none near 100 %.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_formula_mathtype",
                                       os.path.join(HERE, "check-formula-mathtype.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

SCALES = (60, 100, 140)
TOLERANCE = 0.08
FORMATS = (("docx", "MS Word 2007 XML"),)  # LibreOffice drops a foreign OLE object saved to .doc
DIGITS = re.compile(r"(\d+)")  # Object2 before Object10
GOALS = re.compile(rb"\\(objw|objh|picwgoal|pichgoal)(\d+)")


def scaled_rtf(data, percent):
    return GOALS.sub(lambda m: b"\\%s%d" % (m.group(1), round(int(m.group(2)) * percent / 100)), data)


def objects(doc):
    """[(is a formula, height in mm100, OLE object's own height or formula text)] of the Writer objects."""
    found = doc.getEmbeddedObjects()
    result = []
    for name in sorted(found.getElementNames(), key=lambda n: [int(t) if t.isdigit() else t for t in DIGITS.split(n)]):
        item = found.getByName(name)
        control = item.ExtendedControlOverEmbeddedObject
        if item.CLSID.upper() == base.MATH:
            control.changeState(1)  # RUNNING
            result.append((True, item.Size.Height, control.getComponent().Formula))
            continue
        try:
            own = control.getVisualAreaSize(1).Height if control.getMapUnit(1) == 0 else None  # mm100
        except Exception:  # noqa: BLE001 - .docx/.rtf objects have no own size
            own = None
        result.append((False, item.Size.Height, own))
    return result


def scale_of(formula):
    match = re.match(r"size \*([0-9.]+) \{", formula)
    return float(match.group(1)) if match else 1.0


def prepare(args, workdir):
    """The .rtf shown at every scale and its .docx copy, the equation still an OLE object (option off)."""
    with open(args.rtf, "rb") as stream:
        source = stream.read()
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        base.set_option(office, False)
        for percent in SCALES:
            rtf = os.path.join(workdir, "shown-%d.rtf" % percent)
            with open(rtf, "wb") as stream:
                stream.write(scaled_rtf(source, percent))
            paths = [rtf]
            doc = office.load(office.url(rtf))
            for extension, filter_name in FORMATS:
                paths.append(os.path.join(workdir, "shown-%d.%s" % (percent, extension)))
                doc.storeToURL(office.url(paths[-1]), headless_office.props(FilterName=filter_name))
            doc.close(True)
            for path in paths:
                doc = office.load(office.url(path))
                found = objects(doc)
                doc.close(True)
                base.record("OLE equation kept %s" % os.path.basename(path), [f[0] for f in found] == [False], found)
    finally:
        office.stop()


def compare(name, heights):
    """heights: {percent: formula height}; 60 % and 140 % must be that share of 100 %."""
    for percent in (60, 140):
        ratio = heights[percent] / heights[100] if heights[100] else 0
        base.record("%s %d %%" % (name, percent), abs(ratio / (percent / 100) - 1) <= TOLERANCE, heights)
    return heights


def formula_heights(office, paths, on, convert=False):
    result = {}
    base.set_option(office, on)
    for percent, path in paths.items():
        doc = office.desktop.loadComponentFromURL(office.url(path), "_blank", 0, ())
        if convert:
            base.convert_all(office, doc)
        found = objects(doc)
        doc.close(True)
        result[percent] = found[0][1] if len(found) == 1 and found[0][0] else 0
        if percent == 100 and len(found) == 1 and found[0][0]:
            base.record("left as MathType made it %s" % os.path.basename(path), scale_of(found[0][2]) == 1.0, found)
    return result


def check_doc(office, path):
    """Every converted formula carries Word's scale of its equation (shown / own size), none near 100 %."""
    base.set_option(office, False)
    doc = office.load(office.url(path))
    before = objects(doc)
    doc.close(True)
    base.set_option(office, True)
    doc = office.load(office.url(path))
    after = objects(doc)
    doc.close(True)
    wrong, scaled = [], 0
    for (was_math, shown, own), (is_math, _, formula) in zip(before, after):
        if was_math or not is_math or not own:
            continue
        expected = shown / own if abs(shown / own - 1) > 0.05 else 1.0
        scaled += expected != 1.0
        if abs(scale_of(formula) - expected) > 0.03:
            wrong.append((shown, own, formula[:40]))
    base.record("Word's scale %s" % os.path.basename(path), not wrong and len(before) == len(after),
                {"objects": len(before), "resized": scaled, "wrong": wrong[:5]})
    return {"resized": scaled, "wrong": len(wrong)}


def check(args, workdir):
    result = {}
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        for extension in ("rtf",) + tuple(e for e, _ in FORMATS):
            paths = {p: os.path.join(workdir, "shown-%d.%s" % (p, extension)) for p in SCALES}
            result["open " + extension] = compare("open keeps Word's scale ." + extension,
                                                  formula_heights(office, paths, True))
        paths = {p: os.path.join(workdir, "shown-%d.rtf" % p) for p in SCALES}
        result["convert rtf"] = compare("convert keeps Word's scale .rtf", formula_heights(office, paths, False, True))
        for path in args.doc:
            result[os.path.basename(path)] = check_doc(office, path)
    finally:
        office.stop()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--rtf", required=True)
    parser.add_argument("--doc", action="append", default=[])
    parser.add_argument("--out", default=os.path.join("tests", "output", "formula-shown-size"))
    parser.add_argument("--port", type=int, default=2105)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    workdir = os.path.abspath(args.out)
    headless_office.import_uno(args.soffice)
    prepare(args, workdir)
    report = check(args, workdir)
    with open(os.path.join(workdir, "result.json"), "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=1)
    failed = [name for name, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
