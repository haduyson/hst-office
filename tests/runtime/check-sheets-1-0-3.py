# SPDX-License-Identifier: AGPL-3.0-only
"""Check the HST Sheets 1.0.3 features on a real build (installed package or instdir).

Usage: python3 tests/runtime/check-sheets-1-0-3.py --instdir DIR [--out DIR] [--phase en-US:en-US]

Starts soffice headless with a fresh profile and, through the input line path (.uno:EnterString), checks:
- Flash Fill: .uno:FlashFill fills a column from a typed example (Vietnamese names), Ctrl+E in Sheets is
  bound to .uno:FlashFill;
- dynamic arrays: =D1:D5*2 typed in one cell spills, =SUM(F1#) sees the spill range, an array blocked by a
  value shows #SPILL!; saved as .ods (with the HST mark on the anchor) and reopened, the array still resizes
  with its result;
- results of the leading spreadsheet application: "a"&TRUE, MROUND(5,-2), SUM("1",2), an empty FILTER
  (#CALC!), ERROR.TYPE of it, FILTERXML numbers.
Writes evidence.json; exit 1 when any expectation fails.
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets_formula_profile import connect, prop, start  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NATIVE = 3


def run(uno, program, out, ui, loc, env):
    proc, pipe = start(program, os.path.join(out, "profile"), ui, loc, env)
    checks = []

    def check(name, ok, actual):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "actual": actual})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {actual!r}")

    try:
        ctx = connect(uno, pipe)
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        dispatcher = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)

        # Ctrl+E in Sheets.
        from com.sun.star.awt import KeyEvent
        from com.sun.star.awt.Key import E as KEY_E
        from com.sun.star.awt.KeyModifier import MOD1
        supplier = smgr.createInstanceWithContext("com.sun.star.ui.ModuleUIConfigurationManagerSupplier", ctx)
        shortcuts = supplier.getUIConfigurationManager("com.sun.star.sheet.SpreadsheetDocument").getShortCutManager()
        event = KeyEvent()
        event.KeyCode, event.Modifiers = KEY_E, MOD1
        try:
            command = shortcuts.getCommandByKeyEvent(event)
        except Exception as error:  # NoSuchElementException: no binding
            command = repr(error)
        check("Ctrl+E in Sheets is Flash Fill", command == ".uno:FlashFill", command)

        doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (prop("Hidden", True),))
        sheet = doc.Sheets.getByIndex(0)
        sep = doc.createInstance("com.sun.star.sheet.FormulaOpCodeMapper").getAvailableMappings(NATIVE, 1)[2].Name
        controller = doc.getCurrentController()
        frame = controller.getFrame()

        def enter(address, text):
            controller.select(sheet.getCellRangeByName(address))
            dispatcher.executeDispatch(frame, ".uno:EnterString", "", 0, (prop("StringName", text.replace(",", sep)),))

        def cell(address):
            return sheet.getCellRangeByName(address)

        # Flash Fill.
        for row, name in enumerate(["Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Cường"], start=1):
            enter(f"A{row}", name)
        enter("B1", "An")
        controller.select(cell("B2"))
        dispatcher.executeDispatch(frame, ".uno:FlashFill", "", 0, ())
        filled = [cell("B2").getString(), cell("B3").getString()]
        check("Flash Fill fills the given names", filled == ["Bình", "Cường"], filled)

        # Dynamic arrays.
        for row in range(1, 6):
            enter(f"D{row}", str(row))
        enter("F1", "=D1:D5*2")
        enter("G1", "=SUM(F1#)")
        doc.calculateAll()
        check("=D1:D5*2 spills", [cell(f"F{r}").getValue() for r in range(1, 6)] == [2, 4, 6, 8, 10],
              [cell(f"F{r}").getValue() for r in range(1, 6)])
        check("=SUM(F1#)", cell("G1").getValue() == 30, cell("G1").getValue())
        enter("I3", "x")
        enter("I1", "=D1:D5")
        check("blocked spill is #SPILL!", cell("I1").getString() == "#SPILL!", cell("I1").getString())
        enter("K1", "3")
        enter("L1", "=SEQUENCE(K1)")

        # Results of the leading spreadsheet application.
        cases = [
            ("N1", '="a"&TRUE', "aTRUE"),
            ("N2", "=LEN(TRUE)", "4"),
            ("N3", "=MROUND(5,-2)", "#NUM!"),
            ("N4", '=SUM("1",2)', "3"),
            ("N5", "=FILTER(D1:D5,D1:D5>10)", "#CALC!"),
            ("N6", "=ERROR.TYPE(FILTER(D1:D5,D1:D5>10))", "14"),
            ("N7", '=ISNUMBER(FILTERXML("<a><b>1</b></a>","//b"))', "TRUE"),
        ]
        for address, formula, _ in cases:
            enter(address, formula)
        doc.calculateAll()
        for address, formula, want in cases:
            check(formula, cell(address).getString() == want, cell(address).getString())

        # 1900 date system: serial 1 is 01/01/1900, serial 60 is 29/02/1900.
        date_cases = [
            ("P1", "=TEXT(1,\"yyyy-mm-dd\")", "1900-01-01"),
            ("P2", "=TEXT(60,\"yyyy-mm-dd\")", "1900-02-29"),
            ("P3", "=TEXT(61,\"yyyy-mm-dd\")", "1900-03-01"),
            ("P4", "=DATE(1900,3,1)", "61"),
            ("P5", "=DAY(60)", "29"),
            ("P6", "=WEEKNUM(60)", "9"),
            ("P7", "=EOMONTH(1,1)", "59"),
            ("P8", "=DAYS360(1,61)", "60"),
            ("P10", "=TEXT(0,\"dd/mm/yyyy\")", "00/01/1900"),
            ("P11", "=DAY(0)", "0"),
        ]
        for address, formula, _ in date_cases:
            enter(address, formula)
        enter("P9", "1900-02-29")
        doc.calculateAll()
        for address, formula, want in date_cases:
            # Numbers by value: a date result shows in a date format.
            text = "-" in want or "/" in want
            got = cell(address).getString() if text else cell(address).getValue()
            check(formula, got == (want if text else float(want)), got)
        check("typing 1900-02-29 gives serial 60", cell("P9").getValue() == 60, cell("P9").getValue())

        # .ods round trip of the dynamic array.
        path = os.path.join(out, "dynamic.ods")
        url = uno.systemPathToFileUrl(path)
        doc.storeToURL(url, (prop("FilterName", "calc8"),))
        doc.close(True)
        with zipfile.ZipFile(path) as package:
            content = package.read("content.xml").decode("utf-8")
        check(".ods marks the dynamic anchors", content.count('dynamic-array="true"') >= 2,
              content.count('dynamic-array="true"'))
        doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
        sheet = doc.Sheets.getByIndex(0)
        sheet.getCellRangeByName("K1").setValue(5)
        doc.calculateAll()
        time.sleep(1)
        values = [sheet.getCellRangeByName(f"L{r}").getValue() for r in range(1, 6)]
        check(".ods reopened: SEQUENCE(K1) resizes to 5", values == [1, 2, 3, 4, 5], values)
        doc.close(True)
    except Exception as error:  # report, do not hide
        check("run", False, repr(error))
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=60)
        except Exception:
            proc.kill()
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/sheets-1-0-3"))
    parser.add_argument("--phase", default="en-US:en-US")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamental.ini" if os.name == "nt" else "fundamentalrc")
    import uno
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    checks = run(uno, program, out, *args.phase.split(":"), env)
    failed = sum(c["status"] == "FAIL" for c in checks)
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "checks": checks}, handle, indent=2, ensure_ascii=False)
    print(f"failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
