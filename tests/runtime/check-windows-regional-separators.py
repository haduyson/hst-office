# SPDX-License-Identifier: AGPL-3.0-only
"""Check on Windows that HST Office numbers follow the user's regional settings (installed build).

Usage, in the user's own session with the office's Python:
  "<program>\\python.exe" check-windows-regional-separators.py --program "<program dir>" --out DIR

Reads HKCU\\Control Panel\\International (LocaleName, sDecimal, sThousand, sList) and runs two phases, each
with a fresh profile and soffice headless:
- default: ooSetupSystemLocale empty, so the regional settings apply (en-US keeps '.' and ',' as its
  decimal and thousands separator, the list separator still follows);
- explicit: ooSetupSystemLocale = LocaleName, so the LibreOffice locale data applies.
Per phase: LocaleData2.getLocaleItem2, the native formula separators (FormulaOpCodeMapper NATIVE
SEPARATORS / ARRAY_SEPARATORS), numbers typed through the input line (.uno:EnterString), the built-in
"#,##0.00" format; then .ods and .xlsx must hold locale-independent values, formulas and format codes.
Writes evidence.json; exit 1 when any expectation fails (hst-windows-regional-separators.patch).
"""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import winreg
import zipfile

# LibreOffice locale data (decimal, thousands, list) and its formula separators (argument, array column, row)
LO_DATA = {"en-US": (".", ",", ";"), "vi-VN": (",", ".", ";")}
LO_FORMULA = {"en-US": (",", ",", ";"), "vi-VN": (";", ".", ";")}
NATIVE, OOXML, SEPARATORS, ARRAY_SEPARATORS = 3, 5, 1, 2
XCU = ('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
       'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
       '<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooSetupSystemLocale" oor:op="fuse">'
       '<value>{loc}</value></prop></item>\n</oor:items>\n')


def regional():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as key:
        return {name: winreg.QueryValueEx(key, name)[0] for name in ("LocaleName", "sDecimal", "sThousand", "sList")}


def expected(reg, phase):
    loc = reg["LocaleName"]
    if phase == "explicit":
        return LO_DATA.get(loc), LO_FORMULA.get(loc)
    dec, th, lst = reg["sDecimal"], reg["sThousand"], reg["sList"]
    if loc == "en-US":
        dec, th = ".", ","
    return (dec, th, lst), (";" if lst == dec else lst, "\\" if dec == "," else ",", ";")


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def start(program, profile, loc):
    (profile / "user").mkdir(parents=True)
    (profile / "user" / "registrymodifications.xcu").write_text(XCU.format(loc=loc), encoding="utf-8")
    soffice = str(Path(program) / "soffice.exe")
    url = f"-env:UserInstallation={profile.as_uri()}"
    subprocess.run([soffice, "--headless", "--norestore", "--terminate_after_init", url], timeout=300, check=False)
    pipe = f"hstregional{os.getpid()}{int(time.time())}"
    proc = subprocess.Popen([soffice, "--headless", "--norestore", "--nologo", url, f"--accept=pipe,name={pipe};urp;"])
    return proc, pipe


def connect(uno, pipe, timeout=240):
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(1)


def native_separators(doc):
    mapper = doc.createInstance("com.sun.star.sheet.FormulaOpCodeMapper")

    def names(lang, group):
        return {e.Token.OpCode: e.Name for e in mapper.getAvailableMappings(lang, group)}
    xs, xa = names(OOXML, SEPARATORS), names(OOXML, ARRAY_SEPARATORS)
    ns, na = names(NATIVE, SEPARATORS), names(NATIVE, ARRAY_SEPARATORS)
    op = {name: code for code, name in xs.items()}
    arr = {name: code for code, name in xa.items()}
    return ns[op[","]], na[arr[","]], na[arr[";"]]  # OOXML: ',' argument, ',' column, ';' row


def files_are_invariant(doc, out, check):
    ods, xlsx = out / "regional.ods", out / "regional.xlsx"
    doc.storeToURL(ods.as_uri(), (prop("FilterName", "calc8"),))
    doc.storeToURL(xlsx.as_uri(), (prop("FilterName", "Calc Office Open XML"),))
    with zipfile.ZipFile(ods) as z:
        content = z.read("content.xml").decode("utf-8")
    with zipfile.ZipFile(xlsx) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        styles = z.read("xl/styles.xml").decode("utf-8")
    check(".ods values and formulas are locale-independent",
          all(s in content for s in ('office:value="1.5"', 'office:value="1234.5"', "of:=SUM(1.5;2)")), content[-1500:])
    check(".xlsx values and formulas are locale-independent",
          all(s in sheet for s in ("<v>1.5</v>", "<v>1234.5</v>", ">SUM(1.5,2)</f>")), sheet[-1500:])
    codes = re.findall(r'formatCode="([^"]*)"', styles)
    check(".xlsx number format keeps #,##0.00", any(re.fullmatch(r"(\[\$-[0-9A-F]+\])?#,##0\.00", c) for c in codes), codes)


def run_phase(uno, program, out, reg, phase):
    out = out / phase
    loc = reg["LocaleName"] if phase == "explicit" else ""
    data, formula = expected(reg, phase)
    checks, result = [], {"phase": phase, "ooSetupSystemLocale": loc, "expected_data": data, "expected_formula": formula}

    def check(name, ok, actual):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "actual": actual})
        print(f"{'PASS' if ok else 'FAIL'}  [{phase}] {name}: {actual!r}")

    proc, pipe = start(program, out / "profile", loc)
    try:
        ctx = connect(uno, pipe)
        smgr = ctx.ServiceManager
        lang, _, country = reg["LocaleName"].partition("-")
        locale = uno.createUnoStruct("com.sun.star.lang.Locale", lang, country, "")
        item = smgr.createInstanceWithContext("com.sun.star.i18n.LocaleData2", ctx).getLocaleItem2(locale)
        actual = (item.decimalSeparator, item.thousandSeparator, item.listSeparator)
        result["locale_data"] = actual
        check("locale data separators (decimal, thousands, list)", data is None or actual == data, actual)
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (prop("Hidden", True),))
        seps = native_separators(doc)
        result["formula_separators"] = seps
        check("formula separators (argument, array column, array row)", formula is None or seps == formula, seps)
        dec, th, arg = actual[0], actual[1], seps[0]
        sheet = doc.Sheets.getByIndex(0)
        controller = doc.getCurrentController()
        dispatcher = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)

        def enter(address, text):
            controller.select(sheet.getCellRangeByName(address))
            dispatcher.executeDispatch(controller.getFrame(), ".uno:EnterString", "", 0, (prop("StringName", text),))
            return sheet.getCellRangeByName(address)
        typed = [("A1", f"1{dec}5", 1.5), ("A2", f"1{th}234{dec}5", 1234.5), ("A3", f"=SUM(1{dec}5{arg}2)", 3.5),
                 ("A5", f"=SUM({{1{seps[1]}2{seps[2]}3{seps[1]}4}})", 10.0)]
        for address, text, value in typed:
            cell = enter(address, text)
            check(f"typed {text!r} is {value}", cell.getValue() == value and not cell.getError(),
                  (cell.getValue(), cell.getString(), cell.getError()))
        index = uno.getConstantByName("com.sun.star.i18n.NumberFormatIndex.NUMBER_1000DEC2")
        cell = sheet.getCellRangeByName("A4")
        cell.setValue(1234.5)
        cell.NumberFormat = doc.getNumberFormats().getFormatIndex(index, locale)
        check("built-in #,##0.00 shows the separators", cell.getString() == f"1{th}234{dec}50", cell.getString())
        files_are_invariant(doc, out, check)
        doc.close(True)
        desktop.terminate()
    except Exception as exc:  # a phase that cannot run is a failure, the other phases still run
        check("phase ran", False, repr(exc))
    finally:
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["checks"] = checks
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--program", default=r"C:\Program Files\HST Office\program")
    parser.add_argument("--out", default=r"C:\hst-test\regional\out")
    parser.add_argument("--phases", default="default,explicit")
    args = parser.parse_args()
    sys.path.insert(0, args.program)
    import uno
    out = Path(args.out).resolve()
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    reg = regional()
    print("regional settings:", reg)
    phases = [run_phase(uno, args.program, out, reg, phase) for phase in args.phases.split(",")]
    failed = sum(c["status"] == "FAIL" for p in phases for c in p["checks"])
    with open(out / "evidence.json", "w", encoding="utf-8") as handle:
        json.dump({"regional": reg, "failed": failed, "phases": phases}, handle, indent=2, ensure_ascii=False)
    print(f"failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
