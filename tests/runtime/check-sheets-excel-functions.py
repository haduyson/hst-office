#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the worksheet functions added for the leading spreadsheet application (HST Sheets).

  check-sheets-excel-functions.py <program dir> <outdir> [ui:locale ...]   (default vi:vi-VN en-US:en-US)

Per phase, on a fresh profile: every case of sheets_excel_functions_cases.py entered through FormulaLocal shows
the expected text, keeps it after an .xlsx and an .ods round trip, and the .xlsx carries the expected formula
text; CODE/CHAR follow the locale's ANSI code page; CELL("filename") of the saved .xlsx is the native
<dir>/[file.xlsx]Sheet form; the Function Wizard lists every new function under its English name with a
description in the UI language; an .xlsx using online-service functions keeps formulas and cached results on
open and writes them back unchanged. Writes <outdir>/evidence.json; exit 1 on any failure.
(hst-sheets-excel-functions.patch, hst-sheets-lambda-functions.patch, hst-sheets-groupby-pivotby.patch)
"""
import json
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets_excel_functions_cases import CASES, CODEPAGE, DATA, NEW, ONLINE, build_online_xlsx  # noqa: E402
from sheets_formula_profile import connect, prop, start  # noqa: E402

try:  # the LAMBDA family and GROUPBY/PIVOTBY (hst-sheets-lambda-functions.patch and later)
    from sheets_lambda_cases import LAMBDA_CASES, LAMBDA_NEW  # noqa: E402
except ImportError:
    LAMBDA_CASES, LAMBDA_NEW = [], []
VI_MARK = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)


def localize(formula, sep, dec):
    parts = formula.split('"')
    for i in range(0, len(parts), 2):  # outside string literals
        parts[i] = parts[i].replace(".", "\0").replace(";", sep).replace("\0", dec) if dec != "." else \
            parts[i].replace(";", sep)
    out = '"'.join(parts)
    # keep dotted function names (BINOM.DIST.RANGE) intact
    return out.replace("BINOM" + dec + "DIST" + dec + "RANGE", "BINOM.DIST.RANGE")


def sheet_xml(path):
    return zipfile.ZipFile(path).read("xl/worksheets/sheet1.xml").decode("utf-8")


def run_phase(program, out, ui, loc, results):
    uno_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    proc, pipe = start(program, os.path.join(out, "profile"), ui, loc, uno_env)
    import uno
    desk = None

    def check(name, ok, detail=""):
        results.append({"phase": f"{ui}:{loc}", "check": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + f"[{ui}:{loc}] {name} {detail}")
    try:
        ctx = connect(uno, pipe)
        smgr = ctx.ServiceManager
        desk = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desk.loadComponentFromURL("private:factory/scalc", "_blank", 0, (prop("Hidden", True),))
        sep = "," if loc == "en-US" else ";"
        dec = "." if loc == "en-US" else ","
        sh = doc.Sheets.getByIndex(0)
        for r, row in enumerate(DATA):
            for c, v in enumerate(row):
                cell = sh.getCellByPosition(7 + c, r)
                cell.setString(v) if isinstance(v, str) else cell.setValue(v)
        cases = [(f, e.format(sep=sep, dec=dec), x) for f, e, x in CASES + LAMBDA_CASES] + [(f, e, None) for f, e in CODEPAGE[loc]]
        for i, (f, _, _) in enumerate(cases):
            sh.getCellByPosition(0, i).setPropertyValue("FormulaLocal", localize(f, sep, dec))
        sh.getCellByPosition(1, 0).setPropertyValue("FormulaLocal", '=CELL("filename"' + sep + 'B2)')
        doc.calculateAll()
        for i, (f, want, _) in enumerate(cases):
            got = sh.getCellByPosition(0, i).getString()
            check(f"value {f}", got == want, f"got {got!r} want {want!r}")
        xlsx, ods = os.path.join(out, "functions.xlsx"), os.path.join(out, "functions.ods")
        doc.storeToURL("file://" + ods, (prop("FilterName", "calc8"),))
        doc.storeAsURL("file://" + xlsx, (prop("FilterName", "Calc Office Open XML"),))
        doc.calculateAll()
        tab = sh.getName()
        want_cell = os.path.dirname(xlsx) + os.sep + "[functions.xlsx]" + tab
        got_cell = sh.getCellByPosition(1, 0).getString()
        check("CELL filename native form", got_cell == want_cell, f"got {got_cell!r}")
        doc.close(True)
        xml = sheet_xml(xlsx)
        for f, _, needle in cases:
            if needle:
                check(f"xlsx text {needle}", needle in xml.replace("&quot;", '"'))
        for path in (xlsx, ods):
            again = desk.loadComponentFromURL("file://" + path, "_blank", 0, (prop("Hidden", True),))
            again.calculateAll()
            s2 = again.Sheets.getByIndex(0)
            for i, (f, want, _) in enumerate(cases):
                got = s2.getCellByPosition(0, i).getString()
                check(f"reload {os.path.basename(path)} {f}", got == want, f"got {got!r}")
            again.close(True)
        fd = smgr.createInstanceWithContext("com.sun.star.sheet.FunctionDescriptions", ctx)
        descs = {}
        for i in range(fd.getCount()):
            d = {p.Name: p.Value for p in fd.getByIndex(i)}
            descs[d["Name"]] = d.get("Description") or ""
        for name in NEW + LAMBDA_NEW:
            desc = descs.get(name)
            vi_ok = bool(desc) and (bool(VI_MARK.search(desc)) if ui == "vi" else not VI_MARK.search(desc))
            check(f"wizard {name}", vi_ok, (desc or "missing")[:60])
        src = os.path.join(out, "online.xlsx")
        build_online_xlsx(src)
        odoc = desk.loadComponentFromURL("file://" + src, "_blank", 0, (prop("Hidden", True),))
        osh = odoc.Sheets.getByIndex(0)
        for i, (f, v, _) in enumerate(ONLINE):
            got = osh.getCellByPosition(0, i).getString()
            check(f"online cached {f.split('(')[0]}", got == v.replace(".", dec), f"got {got!r}")
        resaved = os.path.join(out, "online-resaved.xlsx")
        odoc.storeToURL("file://" + resaved, (prop("FilterName", "Calc Office Open XML"),))
        odoc.close(True)
        xml = sheet_xml(resaved).replace("&quot;", '"')
        for f, v, _ in ONLINE:
            check(f"online written back {f.split('(')[0]}", f">{f}</f>" in xml and f"<v>{v}</v>" in xml)
    finally:
        try:
            desk.terminate()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(30)
        except Exception:
            proc.kill()


def main():
    program, out = sys.argv[1], sys.argv[2]
    phases = sys.argv[3:] or ["vi:vi-VN", "en-US:en-US"]
    sys.path.insert(0, program)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    results = []
    for phase in phases:
        ui, loc = phase.split(":")
        sub = os.path.join(out, phase.replace(":", "_"))
        os.makedirs(sub)
        run_phase(program, sub, ui, loc, results)
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    failed = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(failed)} PASS, {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
