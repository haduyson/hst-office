#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check of VND()/USD() in HST Sheets (real build, soffice as the build user): typed formulas, Excel files that
call them through a Vietnamese number-words add-in, saving as .xlsx and .ods, and reopening.

Usage (the Xvfb display must already run; it is never started or stopped here):
    python3 tests/runtime/check-sheets-vnd-usd.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/sheets-vnd-usd] [--display :153] [--port 22954]

Files opened: .xlsx written here part by part as Excel writes these calls (excel_addin_fixtures.py): the add-in
workbook's external name with an absolute, a Library-relative (xlLibrary) and an XLSTART link, the XLL "_xll." prefix,
a bare name; tests/fixtures/excel-addins/*.xls (BIFF8: add-in SupBook, external-workbook SupBook). Each must open
with the HST functions computing, unmodified, without an undo step, every other external link kept. Saving as .xlsx
through the GUI (the profile remembers "Chuyển thành giá trị khi lưu") writes the results and no add-in link; .ods
keeps the formulas; both reopen with the same texts. A file whose only external links were the add-in files shows no
"automatic update of external links" bar; one with another link keeps it. Exit 1 when any check fails.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import excel_addin_fixtures as fx  # noqa: E402
import hst_gui  # noqa: E402

NODE = "/org.hasontech.hstoffice.SaveFormatCheck"
XLSX, ODS = "Calc MS Excel 2007 XML", "calc8"
HST = "ORG.HST.OFFICE.VI.CALCFUNCTIONS."
FIXTURES = os.path.join(hst_gui.ROOT, "tests", "fixtures", "excel-addins")
OTHER = fx.Link("file:///C:\\Tools\\Other.xlam", ["Other"])
RESULTS = []

# cell -> expected text, for the files below (A1 = 1500,25; A2 = 309848560)
VNTOOLS_CELLS = {
    "B1": (("[1]!VND(A1)", "Một ngàn năm trăm phẩy hai mươi lăm"), "Một ngàn năm trăm phẩy hai mươi lăm"),
    "B2": (("[1]!VND(A1,TRUE)", "x"), "Một ngàn năm trăm đồng hai mươi lăm xu"),
    "B3": (('[1]!VND(A1,TRUE,1,"đồng","xu")', "x"), "Một ngàn năm trăm đồng hai mươi lăm xu"),
    "B4": (("[1]!USD(A1,TRUE)", "x"), "One thousand five hundred dollars and twenty-five cents"),
    "B5": (("LEN([1]!VND(A2))", "x"), str(len("Ba trăm lẻ chín triệu tám trăm bốn mươi tám ngàn năm trăm sáu mươi"))),
}
XLL_CELLS = {
    "B1": (("_xll.VND(A1)", "x"), "Một ngàn năm trăm đồng hai mươi lăm xu"),
    "B2": (("_xll.USD(A2)", "x"), "Three hundred and nine million eight hundred and forty-eight thousand five hundred "
                                  "and sixty dollars"),
    "B3": (("_xll.VND(A2,,,,,TRUE)", "x"),
           "Ba trăm lẻ chín triệu, tám trăm bốn mươi tám ngàn, năm trăm sáu mươi đồng"),
    "B4": (('_xll.VND(A1,3,"đồng","hào",10)', "x"), "Một ngàn năm trăm đồng ba hào"),
    "B5": (("VND(A1,TRUE)", "x"), "Một ngàn năm trăm đồng hai mươi lăm xu"),
}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail!r}" if not ok and detail != "" else ""), flush=True)


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    return PropertyValue(Name=name, Value=value)


def values(cells):
    return dict({"A1": 1500.25, "A2": 309848560}, **{ref: content for ref, (content, _) in cells.items()})


def wait(condition, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.5)
    return condition()


def check_document(label, doc, expected, other=None):
    sheet = doc.Sheets.getByIndex(0)
    for ref, text in expected.items():
        cell = sheet.getCellRangeByName(ref)
        check(f"{label} {ref}: calls the HST function", HST in cell.getFormula().upper(), cell.getFormula())
        check(f"{label} {ref}: computes", cell.getString() == text, cell.getString())
    if other:
        cell = sheet.getCellRangeByName(other)
        check(f"{label} {other}: another add-in's external name is kept", "Other.xlam" in cell.getFormula(),
              cell.getFormula())
    check(f"{label}: unmodified after loading", not doc.isModified())
    check(f"{label}: no undo step", not doc.getUndoManager().isUndoPossible(),
          doc.getUndoManager().getAllUndoActionTitles())


def open_file(office, path):
    import uno
    return office.load(uno.systemPathToFileUrl(path))


def infobar(doc):
    """Whether the links bar is up once the window settled (the office adds it asynchronously after loading)."""
    controller = doc.getCurrentController()
    time.sleep(3)
    return controller.hasInfobar("enablecontent")


def typed(office):
    doc = office.load("private:factory/scalc")
    sheet = doc.Sheets.getByIndex(0)
    cases = {"A1": ("=VND(15,79; TRUE)", "Mười lăm đồng bảy mươi chín xu"),
             "A2": ("=VND(1234)", "Một ngàn hai trăm ba mươi bốn"),
             "A3": ('=VND(12,5; ; "đồng"; "hào"; 10)', "Mười hai đồng năm hào"),
             "A4": ("=USD(123,45; TRUE)", "One hundred and twenty-three dollars and forty-five cents"),
             "A5": ("=VND(-9)", "Âm chín")}
    for ref, (formula, text) in cases.items():
        cell = sheet.getCellRangeByName(ref)
        cell.setPropertyValue("FormulaLocal", formula)
        check(f"typed {formula}", cell.getString() == text, (cell.getFormula(), cell.getString()))
    doc.setModified(False)
    doc.close(True)


def opened_files(office, files):
    cases = [
        ("VnTools .xlsx, absolute path", fx.write_xlsx(os.path.join(files, "vntools.xlsx"), dict(
            values(VNTOOLS_CELLS), B6=("[2]!Other(A1)", "x")), [fx.Link(fx.VNTOOLS_PATH, ["USD", "VND"]), OTHER]),
         VNTOOLS_CELLS, "B6"),
        ("VnTools .xlsx, Library folder", fx.write_xlsx(os.path.join(files, "vntools-library.xlsx"), values(
            VNTOOLS_CELLS), [fx.Link("Ufunctions.xlam", ["USD", "VND"], fx.XLLIBRARY)]), VNTOOLS_CELLS, None),
        ("VnTools .xlsx, XLSTART folder", fx.write_xlsx(os.path.join(files, "vntools-startup.xlsx"), values(
            VNTOOLS_CELLS), [fx.Link("Ufunctions.xlam", ["USD", "VND"], fx.XLSTARTUP)]), VNTOOLS_CELLS, None),
        ("AccHelper .xlsx", fx.write_xlsx(os.path.join(files, "acchelper.xlsx"), values(XLL_CELLS)), XLL_CELLS, None),
    ]
    xls_expected = {"B1": "Một ngàn năm trăm phẩy hai mươi lăm", "B2": "Một ngàn năm trăm đồng hai mươi lăm xu",
                    "B3": "One thousand five hundred dollars and twenty-five cents",
                    "B4": "Một ngàn năm trăm đồng hai mươi lăm xu", "B5": "One thousand five hundred point two five",
                    "B6": "Ba trăm lẻ chín triệu, tám trăm bốn mươi tám ngàn, năm trăm sáu mươi đồng"}
    for label, path, cells, other in cases:
        doc = open_file(office, path)
        check_document(label, doc, {ref: text for ref, (_, text) in cells.items()}, other)
        shown = infobar(doc)
        if other:
            check(f"{label}: the links bar stays for the other add-in's link", shown)
        else:
            check(f"{label}: no links bar for an add-in file", not shown)
        doc.close(True)
    for name in ("vntools-addin.xls", "xll-addin.xls"):
        doc = open_file(office, os.path.join(FIXTURES, name))
        check_document(name, doc, xls_expected)
        doc.close(True)


def saved_files(office, files):
    import uno
    office.set_config(NODE, "Remembered", "convert")
    source = fx.write_xlsx(os.path.join(files, "to-save.xlsx"), dict(values(VNTOOLS_CELLS), B6=("[2]!Other(A1)", "x")),
                           [fx.Link(fx.VNTOOLS_PATH, ["USD", "VND"]), OTHER])
    expected = {ref: text for ref, (_, text) in VNTOOLS_CELLS.items()}
    doc = open_file(office, source)
    frame = doc.getCurrentController().getFrame()
    xlsx, ods = os.path.join(files, "saved.xlsx"), os.path.join(files, "saved.ods")
    office.dispatch(frame, ".uno:SaveAs", (pv("URL", uno.systemPathToFileUrl(xlsx)), pv("FilterName", XLSX)))
    office.dispatch(frame, ".uno:SaveAs", (pv("URL", uno.systemPathToFileUrl(ods)), pv("FilterName", ODS)))
    doc.close(True)

    with zipfile.ZipFile(xlsx) as package:
        sheet = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
        links = [package.read(n).decode("utf-8") for n in package.namelist() if n.startswith("xl/externalLinks/_rels/")]
    formulas = re.findall(r"<f[^>]*>([^<]*)</f>", sheet)
    check(".xlsx: no VND/USD formula is written", not any(re.search(r"VND|USD", f, re.I) for f in formulas), formulas)
    check(".xlsx: no link to the add-in is written", not any("Ufunctions" in link for link in links), links)
    check(".xlsx: the other add-in's link is kept", any("Other.xlam" in link for link in links), links)
    saved = open_file(office, xlsx)
    cells = saved.Sheets.getByIndex(0)
    for ref, text in expected.items():
        cell = cells.getCellRangeByName(ref)
        check(f".xlsx reopened {ref}: the text", cell.getString() == text and not cell.getFormula().startswith("="),
              (cell.getFormula(), cell.getString()))
    saved.close(True)

    with zipfile.ZipFile(ods) as package:
        content = package.read("content.xml").decode("utf-8")
    check(".ods: the formulas are kept", content.count("of:=" + HST + "VND(") >= 3, re.findall(r'formula="([^"]*)"', content))
    saved = open_file(office, ods)
    check_document(".ods reopened", saved, expected)
    saved.close(True)

    # an API store (no save question) keeps the formulas: .xlsx gets the bare names, read back as the HST functions
    doc = open_file(office, source)
    kept = os.path.join(files, "kept.xlsx")
    doc.storeToURL(uno.systemPathToFileUrl(kept), (pv("FilterName", XLSX),))
    doc.close(True)
    with zipfile.ZipFile(kept) as package:
        sheet = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
    check(".xlsx with formulas: bare VND(", "VND(A1)" in sheet, re.findall(r"<f[^>]*>([^<]*)</f>", sheet))
    saved = open_file(office, kept)
    check_document(".xlsx with formulas reopened", saved, expected)
    saved.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/sheets-vnd-usd"))
    parser.add_argument("--display", default=":153")
    parser.add_argument("--port", type=int, default=22954)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    files = os.path.join(work, f"files-{os.getpid()}")
    os.makedirs(files, exist_ok=True)
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            config=[(NODE, "Remembered", "convert"),
                                    ("/org.openoffice.Office.Common/Save/Document", "WarnAlienFormat", "false")])
    try:
        office.start()
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, work], check=False)
        for step in (typed, opened_files, saved_files):
            try:
                step(office) if step is typed else step(office, files)
            except Exception as error:  # noqa: BLE001 - reported as a failed check, the next step still runs
                check(f"{step.__name__} completed", False, repr(error))
    finally:
        office.stop()
    failed = [result for result in RESULTS if not result[1]]
    print(f"SUMMARY {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
