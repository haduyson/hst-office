#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the Vietnamese utilities against a real HST Office (soffice runs as the build user, never root).

Usage (the Xvfb display must already run; it is never started or stopped here):
    python3 tests/runtime/check-vietnamese-utilities.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/vietnamese-utilities] [--display :94] [--port 2194] [--rows 50000] [--shots DIR]

Checks, with screenshots of each dialog and of the HST menu in --shots:
  1. Sheets functions DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN: set through the API and typed into a cell; the
     "Tiếng Việt" category (12); more than 15 digits is an error.
  2. Every dispatch URL of the utilities resolves (org.hst.office.vi:NumberToWords, RemoveDiacritics, ...).
  3. Bỏ dấu (undo), Tách họ tên, Sắp xếp theo tên, Xóa dòng trống on --rows rows (time, one undo), the 4 date formats.
  4. "Đọc số thành chữ" dialog (text and formula), Writer "Đổi số thành chữ".
  5. Save as .xlsx with HST functions: the warning; Hủy saves nothing, Vẫn lưu keeps the formulas, "Đổi thành chữ rồi
     lưu" writes values and the open document keeps its formulas, the check box converts the document too; Ctrl+S.
  6. The classic HST menu: "Tiện ích tiếng Việt" with the Sheets / Writer commands. Exit status 1 on any FAIL;
     started as root, the script re-executes itself as the build user under dbus-run-session.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import vietnamese_utilities_gui as gui  # noqa: E402
from vietnamese_utilities_dialogs import blank_rows, dialogs, menu, save_warning, writer  # noqa: E402
from vietnamese_utilities_gui import ROWS, record  # noqa: E402

ROOT = hst_gui.ROOT
URLS = ("NumberToWords", "RemoveDiacritics", "SplitName", "SortByGivenName", "DeleteBlankRows", "FormatDate",
        "FormatDateLong", "FormatMonthYear", "FormatDateDash")


def functions(office, doc, args):
    sheet = doc.Sheets.getByIndex(0)
    cell = sheet.getCellRangeByName
    cases = {"A1": ("=DOCSO(105)", "Một trăm lẻ năm"), "A2": ("=DOCTIEN(10000000)", "Mười triệu đồng chẵn"),
             "A3": ('=DOCSO(1005;"ngàn linh")', "Một ngàn không trăm linh năm"),
             "A4": ('=DOCTIEN(12.5;"dollar";"cent";"en")', "Twelve dollars and fifty cents"),
             "A5": ('=BODAU("Nguyễn Văn Đức")', "Nguyen Van Duc"), "A6": ('=TACHHO("Nguyễn Thị Minh Khai")', "Nguyễn Thị Minh"),
             "A7": ('=TACHTEN("Nguyễn Thị Minh Khai")', "Khai"), "A8": ("=DOCSO(-2.5)", "Âm hai phẩy năm")}
    for address, (formula, _) in cases.items():
        cell(address).setFormula(formula)
    doc.calculateAll()
    for address, (formula, expected) in cases.items():
        record("function %s" % formula, cell(address).getString() == expected, cell(address).getString())
    cell("A9").setFormula("=DOCSO(1E15)")
    doc.calculateAll()
    record("more than 15 digits is an error, not a reading", cell("A9").getError() != 0, cell("A9").getString())
    descriptions = office.service("com.sun.star.sheet.FunctionDescriptions")
    found = {}
    for index in range(descriptions.getCount()):
        props = {p.Name: p.Value for p in descriptions.getByIndex(index)}
        if props.get("Name") in ("DOCSO", "DOCTIEN", "BODAU", "TACHHO", "TACHTEN"):
            found[props["Name"]] = props.get("Category")
    record("Function Wizard lists the five functions in category 12 (Tiếng Việt)",
           sorted(found) == ["BODAU", "DOCSO", "DOCTIEN", "TACHHO", "TACHTEN"] and set(found.values()) == {12}, found)
    # typed like a user, in the cell input
    frame = doc.getCurrentController().getFrame()
    wid = gui.wait_window(office, r"HST Sheets")
    gui.focus(office.display, wid, 700, 500)  # a click into the grid gives the keyboard focus
    doc.getCurrentController().select(cell("C1"))
    gui.type_text(office.display, wid, "=DOCTIEN(1000001)")
    gui.xdo(office.display, "key", "Return")
    time.sleep(1.5)
    record("typed =DOCTIEN(1000001) reads the money", cell("C1").getString() == "Một triệu không trăm lẻ một đồng chẵn",
           (cell("C1").getFormula(), cell("C1").getString()))
    import uno
    for name in URLS:
        url = uno.createUnoStruct("com.sun.star.util.URL")
        url.Complete = "org.hst.office.vi:" + name
        url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)[1]
        record("dispatch URL org.hst.office.vi:%s resolves" % name, frame.queryDispatch(url, "", 0) is not None)


def commands(office, doc, args):
    from hst_office import actions
    said = []
    host = gui.host_for(office, doc, said)
    controller = doc.getCurrentController()
    sheet = doc.Sheets.getByIndex(0)
    controller.setActiveSheet(sheet)
    cell = sheet.getCellRangeByName
    run = lambda name, address: (controller.select(cell(address)), actions.COMMANDS[name](host))  # noqa: E731
    # Bỏ dấu
    cell("E1").setString("Nguyễn Văn Đức")
    cell("E2").setFormula('="Hà "&"Nội"')
    cell("E3").setValue(42)
    doc.getUndoManager().clear()
    run("RemoveDiacritics", "E1:E3")
    record("Bỏ dấu: text converted, formula and number kept", cell("E1").getString() == "Nguyen Van Duc"
           and cell("E2").getFormula() == '="Hà "&"Nội"' and cell("E3").getValue() == 42, said[-1:])
    doc.getUndoManager().undo()
    record("Bỏ dấu: one undo restores", cell("E1").getString() == "Nguyễn Văn Đức")
    # Tách họ tên
    for row, text in enumerate(("Họ và tên", "Nguyễn Thị Minh Khai", "Trần An", "Lan")):
        cell("G%d" % (row + 1)).setString(text)
    run("SplitName", "G1:G4")
    got = [(cell("H%d" % r).getString(), cell("I%d" % r).getString()) for r in range(1, 5)]
    record("Tách họ tên: Họ đệm / Tên columns", got == [("Họ đệm", "Tên"), ("Nguyễn Thị Minh", "Khai"), ("Trần", "An"),
                                                      ("", "Lan")], got)
    # Sắp xếp theo tên
    table = (("STT", "Họ và tên", "Lớp"), (1, "Trần Văn Bình", "6A"), (2, "Lê Văn An", "6B"), (3, "Đỗ Ân", "6C"), (4, "Nguyễn An", "6D"))
    for r, row in enumerate(table):
        for c, value in enumerate(row):
            target = sheet.getCellByPosition(11 + c, r)
            target.setValue(value) if isinstance(value, int) else target.setString(value)
    run("SortByGivenName", "M2")
    names = [sheet.getCellByPosition(12, r).getString() for r in range(1, 5)]
    classes = [sheet.getCellByPosition(13, r).getString() for r in range(1, 5)]
    record("Sắp xếp theo tên: given name, then family", names == ["Lê Văn An", "Nguyễn An", "Đỗ Ân", "Trần Văn Bình"]
           and classes == ["6B", "6D", "6C", "6A"] and sheet.getCellByPosition(14, 0).getString() == "", (names, classes))
    # Định dạng ngày tháng
    cell("E10").setFormula("=DATE(2026;2;5)")
    shown = {}
    for name in ("FormatDate", "FormatDateLong", "FormatMonthYear", "FormatDateDash"):
        run(name, "E10")
        shown[name] = cell("E10").getString()
    record("4 date formats", shown == {"FormatDate": "05/02/2026", "FormatDateLong": "ngày 05 tháng 02 năm 2026",
                                       "FormatMonthYear": "tháng 02 năm 2026", "FormatDateDash": "05-02-2026"}, shown)
    blank_rows(doc, host, args, said)
    controller.setActiveSheet(sheet)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "vietnamese-utilities"))
    ap.add_argument("--shots", default=None, help="screenshot directory (default: --out/shots)")
    ap.add_argument("--display", default=":94")
    ap.add_argument("--port", type=int, default=2194)
    ap.add_argument("--rows", type=int, default=50000)
    args = ap.parse_args()
    args.out = os.path.abspath(args.out)
    args.shots = os.path.abspath(args.shots or os.path.join(args.out, "shots"))
    if os.geteuid() == 0:
        for path in (args.out, args.shots):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work"), args.port, display=args.display).start()
    try:
        doc = office.load("private:factory/scalc")
        for step in (functions, commands, dialogs, save_warning):
            try:
                step(office, doc, args)
            except Exception as error:  # noqa: BLE001 - report and go on with the next step
                import traceback
                traceback.print_exc()
                record("%s ran without error" % step.__name__, False, repr(error))
        menu(office, doc, args, "sheets", ["Đọc số thành chữ", "Bỏ dấu", "Tách họ tên", "Sắp xếp theo tên",
                                           "Xóa dòng trống", "Định dạng ngày tháng"])
        doc.close(True)
        writer(office, args)
    finally:
        office.stop()
    failed = [n for n, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
