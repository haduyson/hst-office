#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check: "Chuyển thành giá trị khi lưu" writes the results of the HST function cells into the saved .xlsx/.xls
while the open document keeps its formulas and its state (real build, soffice as the build user).

Usage (the Xvfb display must already run; it is never started or stopped here):
    python3 tests/runtime/check-sheets-save-hst-values.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/sheets-save-hst-values] [--display :153] [--port 22953]

The profile remembers "convert" (as "Không hỏi lại" does), so the save path runs without the dialog: the save code
asks org.hst.office.vi.SaveFormatCheck, which answers with the functions to write as values
(hst-save-hst-functions-as-values.patch). Checked for Save a Copy, Save As and Save (.uno: dispatches, the GUI path):
xl/worksheets/sheet1.xml holds no DOCSO/BODAU formula but their results, other formulas stay; the open document keeps
its formulas, undo list, URL, title and modified state as after a normal save in that mode. Then: an API store()
keeps the formulas (only the GUI save asked for values), "keep" keeps them, .xls (Save a Copy) gets values too.
Exit 1 when any check fails.
"""
import argparse
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

NODE = "/org.hasontech.hstoffice.SaveFormatCheck"
CELLS = {"A1": "=DOCSO(105)", "A2": "=BODAU(\"Hà Nội\")", "A3": "=SUM(1;2)", "B1": "=LEN(A1)"}
XLSX, XLS = "Calc MS Excel 2007 XML", "MS Excel 97"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail!r}" if not ok and detail != "" else ""))


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    return PropertyValue(Name=name, Value=value)


def sheet_xml(path):
    with zipfile.ZipFile(path) as package:
        return package.read("xl/worksheets/sheet1.xml").decode("utf-8")


def check_values_file(label, path):
    if not os.path.exists(path):
        check(f"{label}: the file is written", False, path)
        return
    xml = sheet_xml(path)
    formulas = re.findall(r"<f[^>]*>([^<]*)</f>", xml)
    check(f"{label}: no DOCSO/BODAU formula in sheet1.xml", not re.search(r"DOCSO|BODAU", xml, re.I), formulas)
    check(f"{label}: other formulas stay formulas", any("SUM" in f for f in formulas) and any("LEN" in f for f in formulas),
          formulas)
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        shared = package.read("xl/sharedStrings.xml").decode("utf-8") if "xl/sharedStrings.xml" in names else ""
    check(f"{label}: the results are in the file", "Một trăm lẻ năm" in shared and "Ha Noi" in shared, shared[-300:])


def state(doc):
    sheet = doc.Sheets.getByIndex(0)
    return {"formulas": [sheet.getCellRangeByName(a).getFormula() for a in CELLS], "url": doc.getURL(),
            "title": doc.getTitle(), "modified": doc.isModified(),
            "undo": list(doc.getUndoManager().getAllUndoActionTitles())}


def same_document(label, before, after, **changes):
    expected = dict(before, **changes)
    check(f"{label}: the open document keeps its formulas", after["formulas"] == before["formulas"], after["formulas"])
    for key in ("url", "title", "modified", "undo"):
        check(f"{label}: {key} as after a normal save", after[key] == expected[key], (after[key], expected[key]))


def run(office, files):
    import uno
    doc = office.load("private:factory/scalc")
    frame = doc.getCurrentController().getFrame()
    sheet = doc.Sheets.getByIndex(0)
    for address, formula in CELLS.items():
        sheet.getCellRangeByName(address).setFormula(formula)
    check("the HST functions compute", sheet.getCellRangeByName("A1").getString() == "Một trăm lẻ năm",
          sheet.getCellRangeByName("A1").getString())
    url = lambda name: uno.systemPathToFileUrl(os.path.join(files, name))  # noqa: E731

    before = state(doc)
    office.dispatch(frame, ".uno:ExportTo", (pv("URL", url("copy.xlsx")), pv("FilterName", XLSX), pv("SaveACopy", True)))
    check_values_file("Save a Copy", os.path.join(files, "copy.xlsx"))
    same_document("Save a Copy", before, state(doc))

    before = state(doc)
    office.dispatch(frame, ".uno:SaveAs", (pv("URL", url("saved-as.xlsx")), pv("FilterName", XLSX)))
    check_values_file("Save As", os.path.join(files, "saved-as.xlsx"))
    same_document("Save As", before, state(doc), url=url("saved-as.xlsx"), title="saved-as.xlsx", modified=False)

    sheet.getCellRangeByName("Z1").setValue(1)
    before = state(doc)
    office.dispatch(frame, ".uno:Save")
    check("Save: the file is written again", 'r="Z1"' in sheet_xml(os.path.join(files, "saved-as.xlsx")))
    check_values_file("Save", os.path.join(files, "saved-as.xlsx"))
    same_document("Save", before, state(doc), modified=False)

    sheet.getCellRangeByName("Z1").setValue(2)
    doc.store()
    check("API store() keeps the formulas", "DOCSO" in sheet_xml(os.path.join(files, "saved-as.xlsx")).upper())

    office.set_config(NODE, "Remembered", "keep")
    office.dispatch(frame, ".uno:ExportTo", (pv("URL", url("kept.xlsx")), pv("FilterName", XLSX), pv("SaveACopy", True)))
    path = os.path.join(files, "kept.xlsx")
    check("remembered Vẫn lưu keeps the formulas", os.path.exists(path) and "DOCSO" in sheet_xml(path).upper())

    office.set_config(NODE, "Remembered", "convert")
    office.dispatch(frame, ".uno:ExportTo", (pv("URL", url("copy.xls")), pv("FilterName", XLS), pv("SaveACopy", True)))
    path = os.path.join(files, "copy.xls")
    saved = office.load(uno.systemPathToFileUrl(path), hidden=True) if os.path.exists(path) else None
    a1 = saved.Sheets.getByIndex(0).getCellRangeByName("A1") if saved else None
    check(".xls: A1 holds the text, not a formula", a1 is not None and a1.getType().value == "TEXT"
          and a1.getString() == "Một trăm lẻ năm", a1 and a1.getFormula())
    if saved:
        saved.close(True)
    check(".xls: the open document keeps its formulas", state(doc)["formulas"] == before["formulas"])
    doc.setModified(False)
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/sheets-save-hst-values"))
    parser.add_argument("--display", default=":153")
    parser.add_argument("--port", type=int, default=22953)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    files = os.path.join(work, f"files-{os.getpid()}")
    os.makedirs(files, exist_ok=True)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, work], check=False)
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[(NODE, "Remembered", "convert"),
                                    ("/org.openoffice.Office.Common/Save/Document", "WarnAlienFormat", "false")])
    try:
        office.start()
        run(office, files)
    except Exception as error:  # noqa: BLE001 - reported as a failed check
        check("run completed", False, repr(error))
    finally:
        office.stop()
    failed = [result for result in RESULTS if not result[1]]
    print(f"SUMMARY {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
