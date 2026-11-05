# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of VBA authoring in HST Sheets and HST Writer (headless, fresh profile, soffice as hstbuild).

Usage: python3 tests/runtime/check-vba.py [--instdir upstream/libreoffice/instdir] [--out tests/output/vba]
                                          [--only calc|writer|roundtrip|config] [--port 22975]

1. Config: the VBA load/run/save defaults and macro security (ask before running document macros).
2. Compatibility matrix (tests/runtime/vba_cases.py): every Excel/Word idiom runs in its own new
   document from a module that begins with "Option VBASupport 1" in a VBA-mode library, the way
   the HST command "Macro VBA" prepares documents (hst_office/vba.py, same template).
3. Upstream Word VBA suites: the testAll() macros of LibreOffice's own .docm test files.
4. Round trip: new and existing .xlsm/.docm and .ods/.odt saved, reloaded, code kept and runnable;
   Workbook_Open / Worksheet_Change / Document_Open events.

Writes evidence.json and matrix.md (the table used by the help page and the report). Exit 1 when a
case marked "ok" fails or any config/round-trip expectation fails; "limited" cases only report.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "extensions/hst-vietnamese-tools/python"))
import vba_cases  # noqa: E402
from hst_office import vba  # noqa: E402  (the code behind "Macro VBA")
from vba_check_roundtrip import check_roundtrip  # noqa: E402
from vba_check_support import (BUILD_USER, FIXTURES, ROWS, Office, case_module, compiles, config_value,  # noqa: E402,F401
                               module_code, prepare, pv, reexec_as_build_user, record, run)

WRITER_SUITES = [  # (fixture, module, function, status) from sw/qa/core/macros-test.cxx
    ("sw/qa/core/data/docm/testFind.docm", "Module1", "testAll", "ok"),
    ("sw/qa/core/data/docm/testDocumentRange.docm", "Module1", "testAll", "ok"),
    ("sw/qa/core/data/docm/testTables.docm", "ThisDocument", "TestAll", "ok"),
    ("sw/qa/core/data/docm/testVBA.docm", "ThisDocument", "testAll", "ok"),
    # upstream marks these "TODO - make these pass in Writer"
    ("sw/qa/core/data/docm/testFontColor.docm", "ThisDocument", "testAll", "limited"),
    ("sw/qa/core/data/docm/testSentences.docm", "ThisDocument", "TestAll", "limited"),
    ("sw/qa/core/data/docm/testWords.docm", "ThisDocument", "TestAll", "limited"),
    ("sw/qa/core/data/docm/testParagraphFormat.docm", "ThisDocument", "TestAll", "limited"),
]
def run_matrix(office, group, cases, kind, setup=None):
    for case in cases:
        if not compiles(office, kind, case_module(case)):
            record(group, f"{case['id']}: {case['title']}", False, "compile error", case["status"])
            continue
        doc = office.new(kind)
        try:
            if setup:
                setup(doc)
            name, library = prepare(doc, kind)
            vba.add_module(library, "HstCase", case_module(case))
            try:
                got = run(doc, name, "HstCase", "T")
            except Exception as error:  # noqa: BLE001 - compile errors and uncaught runtime errors
                got = f"EXC {type(error).__name__}: {getattr(error, 'Message', error)}"
            ok = got == case["want"]
            detail = f"got {got!r}, want {case['want']!r}"
            if ok and case.get("doc"):
                try:
                    ok = bool(case["doc"](doc))
                except Exception as error:  # noqa: BLE001
                    ok = False
                    detail = f"document check raised {error!r}"
                else:
                    detail = "document check failed" if not ok else ""
            record(group, f"{case['id']}: {case['title']}", ok, detail, case["status"])
        finally:
            doc.close(True)


def writer_setup(doc):
    text = doc.Text
    cursor = text.createTextCursor()
    for number, paragraph in enumerate(vba_cases.WRITER_TEXT.split("\n")):
        if number:
            text.insertControlCharacter(cursor, 0, False)  # PARAGRAPH_BREAK
        text.insertString(cursor, paragraph, False)
    doc.getCurrentController().getViewCursor().gotoStart(False)


def check_config(office):
    expected = {
        # Load VBA code, make it executable and save the original VBA back (Excel and Word files).
        "org.openoffice.Office.Calc/Filter/Import/VBA/Load": True,
        "org.openoffice.Office.Calc/Filter/Import/VBA/Executable": True,
        "org.openoffice.Office.Calc/Filter/Import/VBA/Save": True,
        "org.openoffice.Office.Calc/Filter/Import/VBA/UseExport": True,
        "org.openoffice.Office.Writer/Filter/Import/VBA/Load": True,
        "org.openoffice.Office.Writer/Filter/Import/VBA/Executable": True,
        "org.openoffice.Office.Writer/Filter/Import/VBA/Save": True,
        # Medium: macros in a document from an unknown source run only after the user agrees.
        "org.openoffice.Office.Common/Security/Scripting/MacroSecurityLevel": 1,
        "org.openoffice.Office.Common/Security/Scripting/DisableMacrosExecution": False,
    }
    for path, want in expected.items():
        try:
            got = config_value(office.ctx, path)
        except Exception as error:  # noqa: BLE001
            got = f"ERROR {error}"
        record("config", f"{path} = {want!r}", got == want, f"got {got!r}")
    # Keyboard shortcuts of the bundled HST extension (Accelerators.xcu): Alt+F11 editor, Alt+F8 macros.
    from com.sun.star.awt import KeyEvent
    from com.sun.star.awt.Key import F11, F8
    from com.sun.star.awt.KeyModifier import MOD2
    supplier = office.ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
    for module, key, name, want in (
            ("com.sun.star.sheet.SpreadsheetDocument", F11, "Alt+F11", "org.hst.office.vi:EditVba"),
            ("com.sun.star.text.TextDocument", F11, "Alt+F11", "org.hst.office.vi:EditVba"),
            ("com.sun.star.sheet.SpreadsheetDocument", F8, "Alt+F8", ".uno:MacroDialog"),
            ("com.sun.star.text.TextDocument", F8, "Alt+F8", ".uno:MacroDialog")):
        event = KeyEvent()
        event.KeyCode, event.Modifiers = key, MOD2
        try:
            got = supplier.getUIConfigurationManager(module).getShortCutManager().getCommandByKeyEvent(event)
        except Exception as error:  # noqa: BLE001 - NoSuchElementException when unbound
            got = f"unbound ({type(error).__name__})"
        record("config", f"{module.rsplit('.', 1)[-1]} {name} -> {want}", got == want, f"got {got!r}")


def check_writer_suites(office):
    """One office per suite: an unhandled Basic error in an upstream macro can end a headless office."""
    for fixture, module, function, status in WRITER_SUITES:
        name = os.path.basename(fixture)
        own = Office(office.program, office.out, office.port + 1).start()
        try:
            doc = own.load(os.path.join(FIXTURES, fixture))
            got = run(doc, doc.BasicLibraries.ProjectName, module, function)
            doc.close(True)
        except Exception as error:  # noqa: BLE001 - includes the office ending during the macro
            got = f"EXC {type(error).__name__}: {getattr(error, 'Message', error)}"
        finally:
            own.stop()
        record("writer-upstream", f"{name} {function}()", got == "OK", f"got {str(got)[:160]!r}", status)


def write_matrix(out):
    lines = ["| Nhóm | Trường hợp | Kết quả |", "|---|---|---|"]
    for row in ROWS:
        verdict = "đạt" if row["passed"] else ("hạn chế" if row["status"] == "limited" else "LỖI")
        lines.append(f"| {row['group']} | {row['name']} | {verdict} |")
    with open(os.path.join(out, "matrix.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/vba"))
    parser.add_argument("--only", choices=("calc", "writer", "roundtrip", "config"))
    parser.add_argument("--port", type=int, default=22975)
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    if os.geteuid() == 0:
        reexec_as_build_user(args.out)  # soffice never runs as root
    program = os.path.join(os.path.abspath(args.instdir), "program")
    sys.path.insert(0, program)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    office = Office(program, args.out, args.port).start()
    try:
        if args.only in (None, "config"):
            check_config(office)
        if args.only in (None, "calc"):
            run_matrix(office, "calc", vba_cases.CALC, "scalc")
        if args.only in (None, "writer"):
            run_matrix(office, "writer", vba_cases.WRITER, "swriter", writer_setup)
            check_writer_suites(office)
        if args.only in (None, "roundtrip"):
            check_roundtrip(office, args.out)
    finally:
        office.stop()
    write_matrix(args.out)
    failed = [r for r in ROWS if not r["passed"] and r["status"] == "ok"]
    summary = {}
    for row in ROWS:
        entry = summary.setdefault(row["group"], {"passed": 0, "total": 0})
        entry["total"] += 1
        entry["passed"] += row["passed"]
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "summary": summary, "failed": len(failed), "rows": ROWS}, handle, indent=2, ensure_ascii=False)
    print("SUMMARY " + ", ".join(f"{g} {v['passed']}/{v['total']}" for g, v in summary.items()) + f"; failing ok-cases: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
