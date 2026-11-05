# SPDX-License-Identifier: AGPL-3.0-only
"""Part of check-vba.py: macros saved to each format and read back, and the events of saved files."""
import os
import unicodedata

from hst_office import vba_template
from vba_check_support import FIXTURES, module_code, prepare, pv, record, run


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
            ("swriter", "doc", "MS Word 97", marker_writer, "ok")):
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
            if ext == "docm":
                # A Word file keeps the project it was read with: Word does not open one HST writes.
                record("roundtrip", f"{name}: the project of the Word file stays, without the edit",
                       "HstEdited" not in code and vba_template.same_text(code, original), f"edit kept={'HstEdited' in code}")
            else:
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
        h1 = unicodedata.normalize("NFC", sheet.getCellRangeByName("H1").String)  # Windows-1258 decomposes some letters
        record("events", "Workbook_Open runs when the .xlsm opens (macros allowed)", h1 != "", f"H1={h1!r}")
        # This Excel project uses code page 1252: Vietnamese letters in its code cannot be stored.
        # The fixture's project uses code page 1252: HST saves it in Windows-1258 so the letters survive.
        record("events", "Vietnamese text in the code of an Excel project with a Western code page", h1 == "mở",
               f"H1={h1!r}")
        # Worksheet_Change follows edits made by the user, not UNO calls: see check-vba-editor.py.
    finally:
        doc.close(True)
    # Document_Open in ThisDocument of a Word file, kept in .odt (edits are not written to .docm).
    for ext, filt in (("odt", "writer8"),):
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
            text = unicodedata.normalize("NFC", doc.Text.String)
            record("events", f"Document_Open runs when the .{ext} opens (macros allowed)", text.startswith("MỞ "), f"text={text[:20]!r}")
        finally:
            doc.close(True)
