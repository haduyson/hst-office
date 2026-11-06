# SPDX-License-Identifier: AGPL-3.0-only
"""Glossary-wide Vietnamese term replacements: File is "tệp tin" in every UI string."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/l10n"))
import vi_terms  # noqa: E402

PAIRS = vi_terms.load_pairs()


class TermReplacementTest(unittest.TestCase):
    def test_glossary_has_the_file_decision(self):
        self.assertEqual(PAIRS.get("tập tin"), "tệp tin")

    def test_case_and_access_keys_are_kept(self):
        for old, new in (("Tập tin", "Tệp tin"), ("tập tin", "tệp tin"), ("TẬP TIN", "TỆP TIN"),
                         ("Tập Tin", "Tệp Tin"), ("~Tập tin", "~Tệp tin"), ("_Tập tin", "_Tệp tin"),
                         ("Tậ_p tin", "Tệ_p tin"), ("tậ~p tin", "tệ~p tin"), ("Tập ti_n", "Tệp ti_n"),
                         ("tập _tin", "tệp _tin"), ("Mở tập tin...", "Mở tệp tin..."),
                         ("Tên tập tin:", "Tên tệp tin:"), ("dòng 1\\ntập tin", "dòng 1\\ntệp tin"),
                         ("Trang Tập tin", "Trang Tệp tin")):
            self.assertEqual(vi_terms.fix(old, PAIRS), new)

    def test_other_text_is_unchanged(self):
        for text in ("Tập hợp", "tập tính", "tệp", "Tệp tin", "xtập tin", "tập tinh", "Lưu tập", "tập\ntin"):
            self.assertEqual(vi_terms.fix(text, PAIRS), text)

    def test_po_msgstr_only_and_patch_lines_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "messages.po"
            path.write_text('msgid ""\nmsgstr ""\n"Last-Translator: tập tin\\n"\n\n'
                            'msgctxt "tập tin"\nmsgid "File"\nmsgstr "~Tập tin"\n\n'
                            'msgid "File View"\nmsgstr "Trang Tập tin"\n\n'
                            'msgid "Open"\nmsgstr ""\n"Mở "\n"tập tin"\n', encoding="utf-8")
            self.assertEqual(vi_terms.normalize_po(path, PAIRS, frozenset({'msgstr "Trang Tập tin"'})), (2, 1))
            text = path.read_text(encoding="utf-8")
            self.assertIn('"Last-Translator: tập tin\\n"', text)
            self.assertIn('msgctxt "tập tin"', text)
            self.assertIn('msgstr "~Tệp tin"', text)
            self.assertIn('msgstr "Trang Tập tin"', text)
            self.assertIn('"Mở "\n"tệp tin"', text)


if __name__ == "__main__":
    unittest.main()
