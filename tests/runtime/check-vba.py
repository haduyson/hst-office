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
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "extensions/hst-vietnamese-tools/python"))
import vba_cases  # noqa: E402
from hst_office import vba, vba_template  # noqa: E402  (the code behind "Macro VBA")

BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
FIXTURES = os.path.join(ROOT, "upstream/libreoffice")
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
ROWS = []


def record(group, name, ok, detail="", status="ok"):
    """status ok: a failure fails the run; limited: known gap, a pass is flagged."""
    ROWS.append(dict(group=group, name=name, passed=bool(ok), status=status, detail=str(detail)[:300]))
    tag = "PASS" if ok else ("FAIL" if status == "ok" else "LIMIT")
    if ok and status == "limited":
        tag = "PASS(limited case now passes: update vba_cases.py/help)"
    print(f"{tag:5} [{group}] {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def reexec_as_build_user(out):
    os.makedirs(out, exist_ok=True)
    subprocess.run(["chown", "-R", BUILD_USER, out], check=True)
    os.execvp("runuser", ["runuser", "-u", BUILD_USER, "--", sys.executable] + sys.argv)


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


class Office:
    def __init__(self, program, out, port):
        self.program, self.out, self.port = program, out, port
        self.profile = os.path.join(out, f"profile-{port}")

    def start(self):
        shutil.rmtree(self.profile, ignore_errors=True)
        env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
        env.update(HOME=os.path.join(self.out, "home"), LANG="C.UTF-8", LC_ALL="C.UTF-8")
        os.makedirs(env["HOME"], exist_ok=True)
        args = [f"-env:UserInstallation=file://{self.profile}", "--norestore", "--headless", "--nologo"]
        for _ in range(3):  # exit 81 = restart requested while the fresh profile is created
            if subprocess.run([os.path.join(self.program, "soffice.bin"), "--terminate_after_init"] + args,
                              env=env, timeout=180, check=False).returncode == 0:
                break
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice")] + args
                                     + [f"--accept=socket,host=127.0.0.1,port={self.port};urp;"], env=env)
        import uno
        local = uno.getComponentContext()
        deadline = time.time() + 120
        while True:
            try:
                resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={self.port};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - NoConnectException until soffice listens
                if time.time() > deadline:
                    raise
                time.sleep(1)
        time.sleep(2)
        self.desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        return self

    def stop(self):
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge drops while soffice exits
            pass
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=20)

    def new(self, kind, hidden=False):
        if hidden:
            return self.desktop.loadComponentFromURL(f"private:factory/{kind}", "_blank", 0,
                                                     (pv("Hidden", True), pv("MacroExecutionMode", 3)))
        # Not Hidden: VBA objects such as Selection or End(xlDown) need the document view.
        # MacroExecutionMode USE_CONFIG (3) as for File > New; the API default never runs cell UDFs.
        return self.desktop.loadComponentFromURL(f"private:factory/{kind}", "_blank", 0, (pv("MacroExecutionMode", 3),))

    def load(self, path, run_macros=True):
        import uno
        if path.startswith(FIXTURES + os.sep):
            # Work on a copy: a lock file left next to a fixture by an ended office blocks loading it.
            self.copies = getattr(self, "copies", 0) + 1  # unique name: an ended office may leave a lock
            copy = os.path.join(self.out, "fixtures", f"{self.port}-{self.copies}-{os.path.basename(path)}")
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            shutil.copyfile(path, copy)
            path = copy
        # ALWAYS_EXECUTE_NO_WARN = 4: the test opens its own files; users get the security prompt (config check).
        return self.desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0,
                                                 (pv("MacroExecutionMode", 4 if run_macros else 0),))


def config_value(ctx, path):
    node, key = path.rsplit("/", 1)
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (pv("nodepath", node),)).getByName(key)


def prepare(doc, kind):
    """Prepare the document exactly as "Macro VBA" does; return its VBA library."""
    library, _module, _code, _created = vba.prepare_document(doc, "calc" if kind == "scalc" else "writer")
    return library, doc.BasicLibraries.getByName(library)


def run(doc, library, module, function):
    script = doc.getScriptProvider().getScript(
        f"vnd.sun.star.script:{library}.{module}.{function}?language=Basic&location=document")
    return script.invoke((), (), ())[0]


def case_module(case):
    body = "\n".join("  " + line for line in case["body"].splitlines())
    return (f"{vba_template.OPTION_LINE}\nFunction T()\n  Dim r As Variant\n  On Error GoTo Fail\n{body}\n  T = CStr(r)\n"
            f"  Exit Function\nFail:\n  T = \"ERR \" & Err.Number & \": \" & Err.Description\nEnd Function\n"
            + case.get("extra", "") + "\n")


def compiles(office, kind, code):
    """A compile error opens an error box, which aborts a headless office when the document has a
    view: compile first in a hidden document, where the failed call just returns nothing."""
    doc = office.new(kind, hidden=True)
    try:
        name, library = prepare(doc, kind)
        vba.add_module(library, "HstCompile", code.replace("Function T()", "Function T()\n  T = \"c\"\n  Exit Function", 1))
        return run(doc, name, "HstCompile", "T") is not None
    finally:
        doc.close(True)


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
            ("com.sun.star.sheet.SpreadsheetDocument", F8, "Alt+F8", ".uno:MacroDialog")):
        event = KeyEvent()
        event.KeyCode, event.Modifiers = key, MOD2
        try:
            got = supplier.getUIConfigurationManager(module).getShortCutManager().getCommandByKeyEvent(event)
        except Exception as error:  # noqa: BLE001 - NoSuchElementException when unbound
            got = f"unbound ({type(error).__name__})"
        record("config", f"{module.rsplit('.', 1)[-1]} {name} -> {want}", got == want, f"got {got!r}")


def module_code(doc, library, module):
    libs = doc.BasicLibraries
    if not libs.hasByName(library):
        return None
    libs.loadLibrary(library)
    lib = libs.getByName(library)
    return lib.getByName(module) if lib.hasByName(module) else None


def check_roundtrip(office, out):
    work = os.path.join(out, "files")
    os.makedirs(work, exist_ok=True)
    marker_calc = 'Function HstRoundTrip()\n  ActiveSheet.Range("A1").Value = 7\n  HstRoundTrip = "OK"\nEnd Function\n'
    marker_writer = 'Function HstRoundTrip()\n  ActiveDocument.Range(0, 0).Text = "!"\n  HstRoundTrip = "OK"\nEnd Function\n'
    for kind, ext, filt, marker, status in (
            ("scalc", "xlsm", "Calc Office Open XML VBA", marker_calc, "ok"),
            ("scalc", "ods", "calc8", marker_calc, "ok"),
            ("scalc", "xls", "MS Excel 97", marker_calc, "ok"),
            ("swriter", "docm", "MS Word 2007 XML VBA", marker_writer, "ok"),
            ("swriter", "odt", "writer8", marker_writer, "ok"),
            ("swriter", "doc", "MS Word 97", marker_writer, "limited")):
        path = os.path.join(work, f"new-{kind}.{ext}")
        doc = office.new(kind)
        try:
            project, library = prepare(doc, kind)
            library.replaceByName("Module1", library.getByName("Module1") + "\n" + marker)
            import uno
            doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", filt),))
        finally:
            doc.close(True)
        doc = office.load(path)
        try:
            code = module_code(doc, project, "Module1") or ""
            template = vba_template.module_text("calc" if kind == "scalc" else "writer")
            kept = "HstRoundTrip" in code and vba_template.same_text(code.split("Function HstRoundTrip")[0], template)
            result = run(doc, project, "Module1", "HstRoundTrip") if kept else None
            record("roundtrip", f"new document -> .{ext}: module kept and runs", kept and result == "OK",
                   f"kept={kept} result={result!r} libs={list(doc.BasicLibraries.ElementNames)}", status)
        except Exception as error:  # noqa: BLE001
            record("roundtrip", f"new document -> .{ext}: module kept and runs", False, repr(error), status)
        finally:
            doc.close(True)
    # Existing Office files: edit a module, save back to the same format, reopen.
    for fixture, ext, filt, module, edit in (
            ("sc/qa/unit/data/xlsm/vba-user-function.xlsm", "xlsm", "Calc Office Open XML VBA", "Module1",
             'Function HstEdited()\n  HstEdited = "OK"\nEnd Function\n'),
            ("sw/qa/core/data/docm/testWords.docm", "docm", "MS Word 2007 XML VBA", "ThisDocument",
             'Function HstEdited()\n  HstEdited = "OK"\nEnd Function\n')):
        source = os.path.join(FIXTURES, fixture)
        name = os.path.basename(fixture)
        doc = office.load(source)
        try:
            libs = doc.BasicLibraries
            library = libs.ProjectName
            original = module_code(doc, library, module)
            libs.getByName(library).replaceByName(module, original + "\n" + edit)
            plain = os.path.join(work, "unchanged-" + name)
            import uno
            path = os.path.join(work, "edited-" + name)
            doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", filt),))
        finally:
            doc.close(True)
        # Unchanged save keeps the original project.
        doc = office.load(source)
        try:
            doc.storeToURL(uno.systemPathToFileUrl(plain), (pv("FilterName", filt),))
        finally:
            doc.close(True)
        doc = office.load(plain)
        try:
            again = module_code(doc, doc.BasicLibraries.ProjectName, module) or ""
            record("roundtrip", f"{name}: unchanged save keeps the original VBA", vba_template.same_text(again, original),
                   f"before {original[:120]!r} after {again[:120]!r}")
        finally:
            doc.close(True)
        doc = office.load(path)
        try:
            code = module_code(doc, doc.BasicLibraries.ProjectName, module) or ""
            ok = "HstEdited" in code and run(doc, doc.BasicLibraries.ProjectName, module, "HstEdited") == "OK"
            record("roundtrip", f"{name}: edited module saved back to .{ext}", ok, f"edit kept={'HstEdited' in code}")
        except Exception as error:  # noqa: BLE001
            record("roundtrip", f"{name}: edited module saved back to .{ext}", False, repr(error))
        finally:
            doc.close(True)
    check_events(office, work)


def check_events(office, work):
    import uno
    # Workbook_Open / Worksheet_Change live in the document modules of an Excel file.
    source = os.path.join(FIXTURES, "sc/qa/extras/testdocuments/SimpleCopyPaste.xlsm")
    path = os.path.join(work, "events.xlsm")
    doc = office.load(source)
    try:
        lib = doc.BasicLibraries.getByName(doc.BasicLibraries.ProjectName)
        lib.replaceByName("ThisWorkbook", lib.getByName("ThisWorkbook")
                          + '\nPrivate Sub Workbook_Open()\n  Worksheets(1).Range("H1").Value = "mở"\nEnd Sub\n')
        lib.replaceByName("Sheet1", lib.getByName("Sheet1")
                          + '\nPrivate Sub Worksheet_Change(ByVal Target As Range)\n'
                            '  If Target.Address = "$A$5" Then Range("H2").Value = Target.Value * 2\nEnd Sub\n')
        doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", "Calc Office Open XML VBA"),))
    finally:
        doc.close(True)
    doc = office.load(path)
    try:
        sheet = doc.Sheets.getByIndex(0)
        h1 = sheet.getCellRangeByName("H1").String
        record("events", "Workbook_Open runs when the .xlsm opens (macros allowed)", h1 != "", f"H1={h1!r}")
        # This Excel project uses code page 1252: Vietnamese letters in its code cannot be stored.
        record("events", "Vietnamese text in the code of an Excel project with a Western code page", h1 == "mở",
               f"H1={h1!r}", "limited")
        # Worksheet_Change follows edits made by the user, not UNO calls: see check-vba-editor.py.
    finally:
        doc.close(True)
    # Document_Open in ThisDocument of a Word file, kept in .odt (edits are not written to .docm).
    for ext, filt in (("odt", "writer8"), ("docm", "MS Word 2007 XML VBA")):
        path = os.path.join(work, f"events.{ext}")
        doc = office.load(os.path.join(FIXTURES, "sw/qa/core/data/docm/testWords.docm"))
        try:
            lib = doc.BasicLibraries.getByName(doc.BasicLibraries.ProjectName)
            lib.replaceByName("ThisDocument", lib.getByName("ThisDocument")
                              + '\nPrivate Sub Document_Open()\n  ActiveDocument.Range(0, 0).Text = "MỞ "\nEnd Sub\n')
            doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", filt),))
        finally:
            doc.close(True)
        doc = office.load(path)
        try:
            text = doc.Text.String
            record("events", f"Document_Open runs when the .{ext} opens (macros allowed)", text.startswith("MỞ "), f"text={text[:20]!r}",
                   "limited")
        finally:
            doc.close(True)


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
