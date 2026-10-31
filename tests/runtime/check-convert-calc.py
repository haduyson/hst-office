#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of "Chuyển mã" in Calc against a real HST Office (soffice runs as the build user, never root).

Usage (the Xvfb display must already run; it is never started or stopped here):
    python3 tests/runtime/check-convert-calc.py [--instdir upstream/libreoffice/instdir] [--out tests/output/convert-calc]
        [--display :86] [--cells 100000]

The command module (convert_calc_action.run) runs in this process from the repository sources against the live
office document; only the modal wizard is replaced by a stub that returns the chosen encoding. Checks: TCVN3 and VNI
cells, formula/number/text-number/Unicode cells untouched, fonts switched, rich text kept, whole column selection,
whole-sheet mode with sheet names and notes, one undo step, and the time for --cells VNI cells.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
ROWS = []


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


class Stub:
    """Stands in for ConvertWizard: returns `key`, reports the options."""
    key, whole, names_notes = None, False, False

    def __init__(self, ctx, strings, items, calc=None):
        Stub.items, Stub.calc = items, calc

    def run(self, peer=None):
        self.whole, self.names_notes = Stub.whole, Stub.names_notes
        return Stub.key


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "convert-calc"))
    ap.add_argument("--display", default=":86")
    ap.add_argument("--cells", type=int, default=100000)
    args = ap.parse_args()
    hst_gui.setup_uno(args.instdir)
    sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
    office = hst_gui.Office(args.instdir, args.out, 22086, display=args.display, nodefault=True).start()
    try:
        run(office, args)
    finally:
        office.stop()
    failed = [n for n, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    sys.exit(1 if failed else 0)


def run(office, args):
    from hst_office import actions, convert_calc_action
    from hst_office.data_files import load_locale
    convert_calc_action.ConvertWizard = Stub
    doc = office.load("private:factory/scalc")
    frame = doc.getCurrentController().getFrame()
    said = []

    class Host(actions.Host):
        def say(self, text, error=False):
            said.append(text)

    def convert(selection, key, whole=False, names=False):
        controller = doc.getCurrentController()
        controller.select(selection)
        Stub.key, Stub.whole, Stub.names_notes = key, whole, names
        del said[:]
        convert_calc_action.run(Host(office.ctx, frame, load_locale("vi")))
        return said[-1] if said else ""

    sheet = doc.Sheets.getByIndex(0)
    cell = lambda a: sheet.getCellRangeByName(a)  # noqa: E731
    tc, vn = "ViÖt Nam", "Vieät Nam"
    for addr, text, font in (("A1", tc, ".VnTime"), ("A2", tc, ".VnTime"), ("A3", "Hà Nội", "Arial"),
                             ("B1", vn, "VNI-Times"), ("B2", vn, "VNI-Times"), ("B3", "00123", "VNI-Times")):
        cell(addr).setString(text)
        cell(addr).CharFontName = font
    cell("A4").setFormula('="Vi"&"Öt"')
    cell("A5").setFormula("=1+2")
    cell("A6").setValue(42)
    cell("A7").setFormula("=B1")
    cell("B4").setFormula("=A5")
    cell("B5").setValue(7.5)
    # rich text: first run bold, second plain, both VNI
    rich = cell("B6")
    text = rich.getText()
    cursor = text.createTextCursor()
    text.insertString(cursor, "Vieät", False)
    cursor.gotoStart(True)
    cursor.CharWeight = 150
    cursor.CharFontName = "VNI-Times"
    cursor.gotoEnd(False)
    cursor.CharWeight = 100
    text.insertString(cursor, " Nam", False)
    sheet.Name = "B¶ng"
    note_cell = cell("A1")
    sheet.getAnnotations().insertNew(note_cell.getCellAddress(), tc)
    manager = doc.getUndoManager()
    manager.clear()

    msg = convert(cell("A1:A7"), "tcvn3")
    record("tcvn3 range: A1,A2 converted", cell("A1").getString() == "Việt Nam" and cell("A2").getString() == "Việt Nam", cell("A1").getString())
    record("tcvn3: font switched", cell("A1").CharFontName == "Times New Roman" and cell("A2").CharFontName == "Times New Roman",
           cell("A1").CharFontName)
    record("unicode cell untouched", cell("A3").getString() == "Hà Nội" and cell("A3").CharFontName == "Arial")
    record("formulas untouched", cell("A4").getFormula() == '="Vi"&"Öt"' and cell("A5").getFormula() == "=1+2"
           and cell("A7").getFormula() == "=B1", cell("A4").getFormula())
    record("number untouched", cell("A6").getValue() == 42 and cell("A6").getString() == "42")
    record("summary counts", "2 ô văn bản" in msg and "3 ô công thức" in msg, msg)
    titles = manager.getAllUndoActionTitles()
    record("single undo step", len(titles) == 1 and titles[0] == "Chuyển mã", titles)
    manager.undo()
    record("undo restores text and font", cell("A1").getString() == tc and cell("A1").CharFontName == ".VnTime"
           and cell("A2").getString() == tc, (cell("A1").getString(), cell("A1").CharFontName))
    manager.redo()
    record("redo reapplies", cell("A1").getString() == "Việt Nam")

    columns = sheet.getColumns()
    convert(columns.getByIndex(1), "vni")
    record("vni whole column clipped to used area", cell("B1").getString() == "Việt Nam" and cell("B2").getString() == "Việt Nam"
           and cell("B1").CharFontName == "Times New Roman", cell("B1").getString())
    record("text-number kept as text", cell("B3").getString() == "00123" and cell("B3").Type.value == "TEXT", cell("B3").getString())
    record("formula/number in column untouched", cell("B4").getFormula() == "=A5" and cell("B5").getValue() == 7.5)
    record("rich text converted, bold kept", cell("B6").getString() == "Việt Nam", cell("B6").getString())
    runs = []
    paragraphs = rich.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        portions = paragraphs.nextElement().createEnumeration()
        while portions.hasMoreElements():
            run = portions.nextElement()
            runs.append((run.getString(), run.CharWeight))
    record("rich runs keep weights", runs[0][1] == 150 and runs[-1][1] == 100, runs)

    convert(cell("A1"), "tcvn3", whole=True, names=True)
    record("sheet name converted", sheet.Name == "Bảng", sheet.Name)
    record("note converted", sheet.getAnnotations().getByIndex(0).getString() == "Việt Nam",
           sheet.getAnnotations().getByIndex(0).getString())
    manager.undo()
    record("undo restores sheet name", sheet.Name == "B¶ng", sheet.Name)

    doc.Sheets.insertNewByName("Perf", 1)
    perf = doc.Sheets.getByName("Perf")
    rows = tuple((vn if i % 2 else "Haø Noäi %d" % i,) for i in range(args.cells))
    perf.getCellRangeByPosition(0, 0, 0, args.cells - 1).setDataArray(rows)
    perf.getCellRangeByPosition(0, 0, 0, args.cells - 1).CharFontName = "VNI-Times"
    doc.getCurrentController().setActiveSheet(perf)
    start = time.time()
    msg = convert(perf.getCellRangeByPosition(0, 0, 0, args.cells - 1), "vni")
    elapsed = time.time() - start
    ok = perf.getCellByPosition(0, 1).getString() == "Việt Nam" and perf.getCellByPosition(0, 2).getString() == "Hà Nội 2"
    record("%d cells converted" % args.cells, ok and ("%d ô văn bản" % args.cells) in msg, msg)
    record("%d cells within 60 s" % args.cells, elapsed < 60, "%.1f s" % elapsed)
    start = time.time()
    manager.undo()
    record("undo of bulk conversion", perf.getCellByPosition(0, 1).getString() == vn, "%.1f s" % (time.time() - start))
    from hst_office.wizard_convert import ConvertWizard
    sheet.Name = "Sheet1"
    cell("A1").setString("Vieät Nam")
    calc = {"single": True, "sample": lambda whole: [{"text": "Vieät Nam", "font": ""}]}
    wizard = ConvertWizard(office.ctx, load_locale("vi"), [{"text": "Vieät Nam", "font": ""}], calc)
    wizard.d.select("source", 2)
    ok = wizard.refresh() and wizard.chosen() == "vni" and "Việt Nam" in wizard.d.get("result")
    record("wizard with sheet options builds and previews", ok, wizard.d.get("result"))
    wizard.d.dialog.dispose()
    doc.close(True)


if __name__ == "__main__":
    main()
