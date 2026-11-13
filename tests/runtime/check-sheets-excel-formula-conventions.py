# SPDX-License-Identifier: AGPL-3.0-only
"""Check that HST Sheets formulas follow the leading spreadsheet application's conventions (real build).

Usage: python3 tests/runtime/check-sheets-excel-formula-conventions.py [--instdir DIR] [--out DIR]
       [--phases vi:vi-VN,en-US:vi-VN,en-US:en-US]

Each phase starts soffice headless with a fresh profile that stores the given UI language and locale
(ooSetupSystemLocale), types values and formulas through the input line path (.uno:EnterString, so
number formats are inferred as for a user) with the separators of that locale, and checks:
- function names in the UI are English and identical in every UI language; CEILING/FLOOR are the
  .xlsx functions (CEILING.XCL is gone), CEILING.ODF/FLOOR.ODF the OpenDocument ones;
- TRUE/FALSE are accepted in cells and formulas and shown as TRUE/FALSE whatever the locale;
- error cells show #VALUE!, #DIV/0!, ... and never "Err:"/"Lỗi:" codes;
- Excel A1 references (Sheet1!A1, 'Trang tính1'!A1) are the default syntax;
- the HST functions (DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN) still work;
- .ods keeps OpenFormula ([.A1], COM.MICROSOFT.CEILING) and .xlsx gets CEILING, not CEILING.MATH.
Writes evidence.json; exit 1 when any expectation fails (hst-sheets-excel-formula-conventions.patch).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets_formula_profile import connect, prop, start  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = {"A1": "10", "A2": "20", "A3": "30", "B1": "Hà Nội", "B2": "Đà Nẵng", "B3": "Hà Nội", "F1": "1", "F2": "2", "F3": "3",
        "G1": "x", "G2": "y", "G3": "z"}
# (typed with {s} = argument separator and {d} = decimal separator, expected display or a predicate)
FORMULAS = [
    ("TRUE", "TRUE"), ("FALSE", "FALSE"), ("=TRUE", "TRUE"), ("=FALSE", "FALSE"), ("=1=1", "TRUE"),
    ("=AND(TRUE{s}FALSE)", "FALSE"), ("=VLOOKUP(2{s}F1:G3{s}2{s}FALSE)", "y"), ("=N(TRUE)", "1"),
    ("=IF(A1>5{s}\"Đạt\"{s}\"Không\")", "Đạt"), ("=SUMIF(B1:B3{s}\"Hà Nội\"{s}A1:A3)", "40"),
    ("=XLOOKUP(3{s}F1:F3{s}G1:G3)", "z"), ("=ROUND(2{d}345{s}2)", "2{d}35"),
    ("=CEILING(-2{d}5{s}2)", "-2"), ("=FLOOR(-2{d}5{s}2)", "-4"), ("=FLOOR(-2{d}5{s}-2)", "-2"), ("=CEILING(2{d}1{s}1)", "3"),
    ("=1/0", "#DIV/0!"), ("=NA()", "#N/A"), ("=SQRT(-1)", "#VALUE!"), ("=VALUE(\"abc\")", "#VALUE!"),
    ("=NOSUCHFUNCTION(1)", "#NAME?"), ("=1+*2", "error"), ("=A1:A2 B3:B4", "#NULL!"),
    ("='{sheet}'!A1", "10"), ("=SUM('{sheet}'!A1:A3)", "60"), ("=INDIRECT(\"'{sheet}'!A2\")", "20"),
    ("=DOCSO(1234)", "Một nghìn hai trăm ba mươi bốn"), ("=BODAU(\"Hà Nội\")", "Ha Noi"), ("=TACHTEN(\"Nguyễn Văn An\")", "An"),
]
NATIVE, OOXML, FUNCTIONS = 3, 5, 16


def run_phase(uno, program, out, ui, loc, env):
    phase_dir = os.path.join(out, f"{ui}_{loc}")
    proc, pipe = start(program, os.path.join(phase_dir, "profile"), ui, loc, env)
    checks, result = [], {"ui": ui, "locale": loc}

    def check(name, ok, actual):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "actual": actual})
        print(f"{'PASS' if ok else 'FAIL'}  [{ui}/{loc}] {name}: {actual!r}")

    try:
        ctx = connect(uno, pipe)
        smgr = ctx.ServiceManager
        provider = smgr.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        syntax = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                      (prop("nodepath", "org.openoffice.Office.Calc/Formula/Syntax"),))
        check("default formula syntax is Excel A1 (1)", syntax.getByName("Grammar") == 1, syntax.getByName("Grammar"))
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (prop("Hidden", True),))
        mapper = doc.createInstance("com.sun.star.sheet.FormulaOpCodeMapper")
        native = {e.Name: e.Token.OpCode for e in mapper.getAvailableMappings(NATIVE, FUNCTIONS)}
        ooxml = {e.Token.OpCode: e.Name for e in mapper.getAvailableMappings(OOXML, FUNCTIONS)}
        result["native_names"] = sorted(native)
        check("CEILING/FLOOR in the UI are the .xlsx functions",
              ooxml.get(native.get("CEILING")) == "CEILING" and ooxml.get(native.get("FLOOR")) == "FLOOR",
              {n: ooxml.get(native.get(n)) for n in ("CEILING", "FLOOR", "CEILING.ODF", "FLOOR.ODF")})
        renamed = {n: ooxml.get(native.get(n), "").replace("_xlfn.", "") for n in
                   ("FORMULATEXT", "SKEW.P", "FORECAST.ETS", "FORECAST.ETS.CONFINT", "FORECAST.ETS.STAT")}
        check("FORMULATEXT, SKEW.P, FORECAST.ETS* keep their .xlsx names", all(k == v for k, v in renamed.items()), renamed)
        check("no CEILING.XCL/FLOOR.XCL names", not {"CEILING.XCL", "FLOOR.XCL"} & set(native), sorted({"CEILING.XCL", "FLOOR.XCL"} & set(native)))
        non_ascii = sorted(n for n in native if not n.isascii())
        check("function names are English (ASCII)", not non_ascii, non_ascii)
        descriptions = smgr.createInstanceWithContext("com.sun.star.sheet.FunctionDescriptions", ctx)
        wizard = {}
        for i in range(descriptions.getCount()):
            entry = {p.Name: p.Value for p in descriptions.getByIndex(i)}
            wizard[entry["Name"]] = entry.get("Description") or ""
        result["wizard_names"] = sorted(wizard)
        named = sorted(n for n, d in wizard.items() if "Microsoft" in d and n in ("CEILING", "FLOOR"))
        check("CEILING/FLOOR help does not name a product", not named, named)

        sheet = doc.Sheets.getByIndex(0)
        sep_arg = mapper.getAvailableMappings(NATIVE, 1)[2].Name  # (, ), separator
        dec = "," if loc.startswith("vi") else "."
        result.update(sheet=sheet.Name, separator=sep_arg)
        controller = doc.getCurrentController()
        dispatcher = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        frame = controller.getFrame()

        def enter(address, text):
            controller.select(sheet.getCellRangeByName(address))
            dispatcher.executeDispatch(frame, ".uno:EnterString", "", 0, (prop("StringName", text),))
            return sheet.getCellRangeByName(address)

        for address, value in DATA.items():
            enter(address, value)
        rows = []
        for row, (typed, _expected) in enumerate(FORMULAS, start=1):
            enter(f"Z{row}", typed.replace("{s}", sep_arg).replace("{d}", dec).replace("{sheet}", sheet.Name))
        doc.calculateAll()  # applies the number format inferred from each result (boolean, ...)
        for row, (typed, expected) in enumerate(FORMULAS, start=1):
            text = typed.replace("{s}", sep_arg).replace("{d}", dec).replace("{sheet}", sheet.Name)
            want = expected.replace("{d}", dec)
            cell = sheet.getCellRangeByName(f"Z{row}")
            shown = cell.getString()
            if want == "error":
                ok = shown.startswith("#") and "Err" not in shown and "Lỗi" not in shown
            else:  # a typed TRUE/FALSE must become a boolean value, not text that looks the same
                ok = shown == want and (typed not in ("TRUE", "FALSE") or cell.getType().value == "VALUE")
            rows.append({"typed": text, "shown": shown, "formula": cell.getPropertyValue("FormulaLocal")})
            check(f"{text} shows {want}", ok, shown)
        result["cells"] = rows

        ods = os.path.join(phase_dir, "formulas.ods")
        xlsx = os.path.join(phase_dir, "formulas.xlsx")
        doc.storeToURL(uno.systemPathToFileUrl(ods), (prop("FilterName", "calc8"),))
        doc.storeToURL(uno.systemPathToFileUrl(xlsx), (prop("FilterName", "Calc MS Excel 2007 XML"),))
        doc.close(True)
        with zipfile.ZipFile(ods) as archive:
            content = archive.read("content.xml").decode("utf-8")
        stored = re.findall(r'table:formula="([^"]*)"', content)
        excel_refs = [f for f in stored if not f.startswith("of:") or re.search(r"[\w']!\$?[A-Z]+\$?[0-9]", f)]
        check(".ods stores OpenFormula ([.A1]) whatever the UI syntax", stored and not excel_refs, excel_refs or len(stored))
        check(".ods stores COM.MICROSOFT.CEILING", "COM.MICROSOFT.CEILING(" in content, "COM.MICROSOFT.CEILING(" in content)
        with zipfile.ZipFile(xlsx) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        check(".xlsx writes CEILING, not CEILING.MATH", "CEILING(" in sheet_xml and "CEILING.MATH" not in sheet_xml,
              [part.split("</f>")[0] for part in sheet_xml.split("<f")[1:] if "CEIL" in part])
        check(".xlsx writes boolean results as booleans", 't="b"' in sheet_xml, sheet_xml.count('t="b"'))
        # Reload both files: the visible results survive the round trip.
        for path in (ods, xlsx):
            again = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (prop("Hidden", True),))
            first = again.Sheets.getByIndex(0)
            shown = [first.getCellRangeByName(f"Z{i}").getString() for i in range(1, len(FORMULAS) + 1)]
            mismatched = [(r["typed"], r["shown"], s) for r, s in zip(rows, shown) if r["shown"] != s]
            check(f"{os.path.basename(path)} reloads with the same results", not mismatched, mismatched)
            again.close(True)
    except Exception as error:  # report and keep the evidence of other phases
        check("phase ran", False, repr(error))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["checks"] = checks
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/sheets-excel-formula-conventions"))
    parser.add_argument("--phases", default="vi:vi-VN,en-US:vi-VN,en-US:en-US")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    import uno
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    phases = [run_phase(uno, program, out, *phase.split(":"), env) for phase in args.phases.split(",")]
    names = [tuple(p.get("native_names", [])) for p in phases]
    same = len(set(names)) == 1 and names[0]
    print(f"{'PASS' if same else 'FAIL'}  function names identical in every UI language")
    failed = sum(c["status"] == "FAIL" for p in phases for c in p["checks"]) + (0 if same else 1)
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "names_identical": bool(same), "phases": phases},
                  handle, indent=2, ensure_ascii=False)
    print(f"failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
