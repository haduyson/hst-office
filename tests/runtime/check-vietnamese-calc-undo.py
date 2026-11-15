#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Does one Undo restore everything after the Sheets utilities that write blocks with setDataArray?

Calc does not undo setDataArray into cells that were EMPTY (measured on HST Sheets 1.0.1, also noted in
csv_calc.py): the "engine" rows below show it. The utilities are safe as long as each block they write lands on
non-empty text (Bỏ dấu) or inside columns inserted in the same undo step (Tách họ tên, Sắp xếp theo tên, Xóa dòng
trống: Undo removes the columns again). The "command" rows check that with one Undo (UndoManager) and with
.uno:Undo (what Ctrl+Z dispatches).

Usage (the Xvfb display must already run; it is never started or stopped here):
    python3 tests/runtime/check-vietnamese-calc-undo.py --display :94 [--instdir DIR] [--out DIR] [--port 2195]
Exit status 1 when a command leaves something behind after Undo."""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import vietnamese_utilities_gui as gui  # noqa: E402
from vietnamese_utilities_gui import ROWS, record  # noqa: E402

NAMES = ("Họ và tên", "Nguyễn Thị Minh Khai", "Trần Văn Ân", "Lê Đức", "", "Đỗ Ánh")
COMMANDS = (("RemoveDiacritics", "A1:A6"), ("SplitName", "A1:A6"), ("SortByGivenName", "A1"),
            ("DeleteBlankRows", "A1:C6"))


def engine(doc):
    """setDataArray in one undo context over targets that were empty or not (informative, never fails the run)."""
    cell = doc.Sheets.getByIndex(0).getCellRangeByName
    for label, before in (("empty", ("", "")), ("text", ("x", "y")), ("empty+text", ("", "y"))):
        cell("A1:A2").clearContents(1023)
        for row, value in enumerate(before):
            if value:
                cell("A%d" % (row + 1)).setString(value)
        manager = doc.getUndoManager()
        manager.clear()
        manager.enterUndoContext("probe")
        cell("A1:A2").setDataArray((("new1",), ("new2",)))
        manager.leaveUndoContext()
        manager.undo()
        print("INFO  engine: setDataArray over %s cells, after one undo: %s" % (
            label, (cell("A1").getString(), cell("A2").getString())), flush=True)


def fill(sheet):
    sheet.getCellRangeByName("A1:L12").clearContents(1023)
    for row, name in enumerate(NAMES):
        if name:
            sheet.getCellByPosition(0, row).setString(name)
            sheet.getCellByPosition(1, row).setValue(row)
    sheet.getCellRangeByName("C3").setString("Hà Nội")  # a sparse column: a sort moves it to another row


def commands(office, doc):
    from hst_office import actions
    host = gui.host_for(office, doc, [])
    controller, sheet = doc.getCurrentController(), doc.Sheets.getByIndex(0)
    grid = lambda: sheet.getCellRangeByName("A1:L12").getFormulaArray()  # noqa: E731
    for via in ("UndoManager", ".uno:Undo"):
        for name, address in COMMANDS:
            fill(sheet)
            doc.getUndoManager().clear()
            before = grid()
            controller.select(sheet.getCellRangeByName(address))
            actions.COMMANDS[name](host)
            changed = grid() != before
            steps = len(doc.getUndoManager().getAllUndoActionTitles())
            if via == "UndoManager":
                doc.getUndoManager().undo()
            else:
                office.dispatch(controller.getFrame(), ".uno:Undo")
                time.sleep(1)
            after = grid()
            left = [(r + 1, c + 1, after[r][c]) for r in range(len(before)) for c in range(len(before[0]))
                    if before[r][c] != after[r][c]]
            record("%s via %s: one undo step restores every cell" % (name, via), changed and steps == 1 and not left,
                   (changed, steps, left[:5]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "vietnamese-calc-undo"))
    ap.add_argument("--display", default=":94")
    ap.add_argument("--port", type=int, default=2195)
    args = ap.parse_args()
    hst_gui.setup_uno(args.instdir)
    sys.path.insert(0, os.path.join(hst_gui.ROOT, "extensions", "hst-vietnamese-tools", "python"))
    office = hst_gui.Office(args.instdir, os.path.join(os.path.abspath(args.out), "work"), args.port,
                            display=args.display).start()
    try:
        doc = office.load("private:factory/scalc")
        engine(doc)
        commands(office, doc)
        doc.close(True)
    finally:
        office.stop()
    failed = [n for n, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
