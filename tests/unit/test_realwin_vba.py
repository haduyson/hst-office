# SPDX-License-Identifier: AGPL-3.0-only
"""Real-Windows harness (tests/realwin): VBA corpus generation, result comparison and the remote path guard."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from _paths import ROOT

REALWIN = Path(ROOT) / "tests" / "realwin"
sys.path.insert(0, str(REALWIN))
sys.path.insert(0, str(Path(ROOT) / "tests" / "runtime" / "vba-corpus"))
import remote  # noqa: E402
import vba_compare  # noqa: E402
import vba_corpus_kit as kit  # noqa: E402
import vba_project_writer  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_vba_corpus", REALWIN / "make-vba-corpus.py")
make_vba_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_vba_corpus)


class CompareTests(unittest.TestCase):
    def test_lines_keep_equal_signs_in_values(self):
        self.assertEqual(vba_compare.parse_lines("a=1\nformula==SUM(A1)\n\nnoise"), {"a": "1", "formula": "=SUM(A1)"})

    def test_kinds(self):
        self.assertEqual(vba_compare.classify("Long:3", "Long:3"), "match")
        self.assertEqual(vba_compare.classify("Long:3", "Integer:3"), "mismatch")
        self.assertEqual(vba_compare.classify("ok", "ERR1"), "hst-error")
        self.assertEqual(vba_compare.classify("ERR1004", "ok"), "reference-error")
        self.assertEqual(vba_compare.classify("ERR1004", "ERR9"), "error-differs")
        self.assertEqual(vba_compare.classify("x", None), "missing")
        self.assertEqual(vba_compare.classify("ERRATIC", "x"), "mismatch")  # only ERR<digits> is an error

    def test_compare_reports_failed_calls_and_each_check(self):
        ref = {"a.xlsm": {"functions": {"F": {"status": "ok", "value": "k=1\nj=2\n"}, "G": {"status": "ok", "value": "x=1\n"}}}}
        hst = {"a.xlsm": {"functions": {"F": {"status": "ok", "value": "k=1\nj=3\n"}, "G": {"status": "error", "value": ""}}},
               "b.docm": {"status": "load-timeout", "error": "boom", "functions": {}}}
        rows = {(r["file"], r["function"], r["key"]): r["kind"] for r in vba_compare.compare(ref, hst)}
        self.assertEqual(rows[("a.xlsm", "F", "k")], "match")
        self.assertEqual(rows[("a.xlsm", "F", "j")], "mismatch")
        self.assertEqual(rows[("a.xlsm", "G", "*")], "call-failed")
        self.assertEqual(rows[("b.docm", "*", "*")], "call-failed")

    def test_markdown_lists_only_differences_and_escapes_pipes(self):
        rows = [dict(file="f", function="F", key="k", reference="a|b", hst="c", kind="mismatch"),
                dict(file="f", function="F", key="same", reference="1", hst="1", kind="match")]
        text = vba_compare.markdown(rows)
        self.assertIn("a\\|b", text)
        self.assertNotIn("| same |", text)
        self.assertIn("| match | 1 |", text)


class CorpusTests(unittest.TestCase):
    def test_vn_escapes_non_ascii_quotes_and_braces(self):
        self.assertEqual(kit.vn("abc"), '"abc"')
        self.assertEqual(kit.vn('a"b'), '"a""b"')
        self.assertEqual(kit.vn("Hà"), 'U("H{e0}")')
        self.assertEqual(kit.vn('Ố"{'), 'U("{1ed0}{22}{7b}")')

    def test_check_lines_record_value_statement_and_setup(self):
        source = kit.checks("Case1", [("#", "Dim s As String"), ("len", "Len(s)"), ("!assign", "s = 1")])
        self.assertIn("    Dim s As String\n", source)
        self.assertIn('Err.Clear: v = Empty: v = Len(s): P "len", v, Err.Number', source)
        self.assertIn('Err.Clear: s = 1: P "assign", "ok", Err.Number', source)
        self.assertTrue(source.rstrip().endswith("Case1 = Take()\nEnd Function"))
        self.assertEqual(kit.function_names(source), ["Case1"])

    def test_document_modules_are_added_once_and_typed(self):
        modules = kit.with_documents([("Cases", "x"), ("Sheet1", kit.document_module("Sheet1", "y"))], ("ThisWorkbook", "Sheet1"))
        self.assertEqual([name for name, _ in modules], ["Cases", "Sheet1", "ThisWorkbook"])
        self.assertTrue(vba_project_writer.is_document(modules[2][1]))
        self.assertFalse(vba_project_writer.is_document('Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"\n'))
        self.assertEqual(vba_project_writer.project_line("ThisWorkbook", modules[2][1]), "Document=ThisWorkbook/&H00000000")
        self.assertEqual(vba_project_writer.project_line("CDiem", 'Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"'), "Class=CDiem")

    def test_packages_bind_document_modules(self):
        with zipfile.ZipFile(io.BytesIO(kit.xlsm([("Cases", "Public Function F()\nEnd Function\n")]))) as package:
            self.assertIn('codeName="ThisWorkbook"', package.read("xl/workbook.xml").decode())
            self.assertIn('codeName="Sheet1"', package.read("xl/worksheets/sheet1.xml").decode())
            self.assertIn(b"Document=ThisWorkbook", package.read("xl/vbaProject.bin"))
        with zipfile.ZipFile(io.BytesIO(kit.docm([("Cases", "x")]))) as package:
            self.assertIn(b"Document=ThisDocument", package.read("word/vbaProject.bin"))

    def test_manifest_lists_every_case_function_and_derived_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = make_vba_corpus.write(tmp)
            on_disk = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest, on_disk)
        by_file = {entry["file"]: entry for entry in manifest}
        self.assertEqual(by_file["xl-language.xlsm"]["functions"],
                         ["LangLoops", "LangStrings", "LangDates", "LangFormat", "LangVietnamese", "LangClass"])
        self.assertTrue(by_file["xl-events.xlsm"]["events"])
        self.assertFalse(by_file["xl-ranges.xlsm"]["events"])
        self.assertEqual(by_file["wd-find.doc"]["derive_from"], "wd-find.docm")
        for entry in manifest:
            self.assertTrue(entry["functions"], entry["file"])
            if "derive_from" not in entry:
                self.assertTrue(entry["file"].endswith((".xlsm", ".docm")))


class RemoteGuardTests(unittest.TestCase):
    def test_only_the_test_roots_are_writable(self):
        for path in ("C:\\hst-test", "C:\\hst-test\\vba", "d:\\HST-TEST\\msi"):
            self.assertTrue(remote.inside_root(path), path)
        for path in ("C:\\", "C:\\hst-testing", "C:\\hst-test\\..\\Users", "C:\\Users\\admin\\Documents", "E:\\hst-test"):
            self.assertFalse(remote.inside_root(path), path)

    def test_push_refuses_before_connecting(self):
        with self.assertRaises(ValueError):
            remote.push("hst4", [], "C:\\Users")

    def test_unknown_host_is_refused(self):
        with self.assertRaises(SystemExit):
            remote.address("hst9")


if __name__ == "__main__":
    unittest.main()
