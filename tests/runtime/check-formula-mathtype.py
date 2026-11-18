#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of HST Công thức against a real HST Office (headless, own profile, Linux/Windows/macOS).

Usage:
    python3 tests/runtime/check-formula-mathtype.py --soffice PATH --docs DIR [--out DIR] [--port 2103]
        [--convert lechhangcongthuc.docx]

DIR holds Word files with MathType equations, e.g. the STEM corpus (tests/corpus/stem/manifest.json: s002.docx has
146 MathType 4-7 objects); files are never stored in the repository. For every .doc/.docx file:
  - option "tự chuyển khi mở" off: the file opens, nothing is converted (the OLE objects stay);
  - option on: the file opens without crashing, every MathType 4-7 object of a .docx/.doc becomes a Math formula or
    stays an OLE object, and the page count is within one page of the count with the option off.
With --convert NAME: Chèn > Công thức > Chuyển công thức (org.hst.office.vi:ConvertFormulas) on that file, run on
the office's main thread as from the menu: all equations converted, one undo step restores them, and the time.
"""
import argparse
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402

MATH = "078B7ABA-54FC-457F-8551-6147E776A997"
OPTION = ("/org.openoffice.Office.Common/Filter/Microsoft/Import", "MathType5ToMath")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def documents(folder):
    for root, _, names in os.walk(folder):
        for name in sorted(names):
            if name.lower().endswith((".doc", ".docx")):
                yield os.path.join(root, name)


def counts(doc):
    objects = doc.getEmbeddedObjects()
    ids = [objects.getByName(n).CLSID.upper() for n in objects.getElementNames()]
    return {"pages": doc.getCurrentController().PageCount, "math": ids.count(MATH), "ole": len(ids) - ids.count(MATH)}


def set_option(office, on):
    access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess", headless_office.props(nodepath=OPTION[0]))
    access.setPropertyValue(OPTION[1], on)
    access.commitChanges()


def measure(office, path):
    doc = office.load(office.url(path))
    try:
        return counts(doc)
    finally:
        doc.close(True)


def check_open(args, workdir):
    """Each file with the option off, then on, in a fresh office per file so a crash names its file."""
    result = {}
    for path in documents(args.docs):
        name = os.path.basename(path)
        row = {}
        for on in (False, True):
            office = headless_office.Office(args.soffice, workdir, args.port)
            try:
                set_option(office, on)
                row["on" if on else "off"] = measure(office, path)
            except Exception as error:  # noqa: BLE001 - a crash drops the bridge: record it as a failure
                row["on" if on else "off"] = {"error": type(error).__name__}
            finally:
                office.stop()
        result[name] = row
        off, on = row["off"], row["on"]
        record("open %s" % name, "error" not in off and "error" not in on, row)
        if "error" in off or "error" in on:
            continue
        # converted formulas sit on the Math baseline instead of Word's run position, so lines can get a little
        # shorter or taller: one page more or less is expected in long papers, more is a layout regression
        record("pages within one %s" % name, abs(off["pages"] - on["pages"]) <= 1, (off["pages"], on["pages"]))
        record("objects kept or converted %s" % name, off["ole"] + off["math"] == on["ole"] + on["math"]
               and on["math"] >= off["math"], (off, on))
    return result


def check_convert(args, workdir, name):
    import unohelper
    from com.sun.star.awt import XCallback
    path = next(p for p in documents(args.docs) if os.path.basename(p) == name)
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        set_option(office, False)
        doc = office.desktop.loadComponentFromURL(office.url(path), "_blank", 0, ())
        before = counts(doc)
        ended = threading.Event()

        class Run(unohelper.Base, XCallback):  # called on the office's main thread; URP keeps the nested
            def notify(self, data):            # dispatch on that thread, as when the user picks the command
                try:
                    office.dispatch(doc, "org.hst.office.vi:ConvertFormulas")
                finally:
                    ended.set()
        start = time.time()
        office.service("com.sun.star.awt.AsyncCallback").addCallback(Run(), None)
        ended.wait(900)
        seconds = round(time.time() - start, 1)
        after = counts(doc)
        undo = doc.getUndoManager()
        steps = len(undo.getAllUndoActionTitles())
        if steps:
            undo.undo()
        restored = counts(doc)
        doc.close(True)
    finally:
        office.stop()
    record("convert all %s" % name, after["ole"] == 0 and after["math"] == before["math"] + before["ole"],
           (before, after, "%.1f s" % seconds))
    record("one undo step", steps == 1 and restored == before, restored)
    return {"before": before, "after": after, "seconds": seconds, "restored": restored}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--docs", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "formula-mathtype"))
    parser.add_argument("--port", type=int, default=2103)
    parser.add_argument("--convert")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    workdir = os.path.abspath(args.out)
    headless_office.import_uno(args.soffice)
    report = {"open": check_open(args, workdir)}
    if args.convert:
        report["convert"] = check_convert(args, workdir, args.convert)
    with open(os.path.join(workdir, "result.json"), "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=1)
    failed = [name for name, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
