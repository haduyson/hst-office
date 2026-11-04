# SPDX-License-Identifier: AGPL-3.0-only
"""What the save warning reports about a VBA UserForm, and the structural form validator."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions/hst-vietnamese-tools/python"))
sys.path.insert(0, str(ROOT / "tests/runtime"))

from hst_office.vba_template import is_word_filter, unwritable_form_content  # noqa: E402
import vba_cfb  # noqa: E402
import vba_form_structure  # noqa: E402


def dialog(body):
    return ('<dlg:window xmlns:dlg="http://openoffice.org/2000/dialog" xmlns:script="http://openoffice.org/2000/script" '
            f'dlg:id="UserForm1"><dlg:bulletinboard>{body}</dlg:bulletinboard></dlg:window>').encode("utf-8")


class FormContent(unittest.TestCase):
    def test_common_controls_are_writable(self):
        body = ('<dlg:button dlg:id="a"/><dlg:text dlg:id="b"/><dlg:textfield dlg:id="c"/><dlg:checkbox dlg:id="d"/>'
                '<dlg:radiogroup><dlg:radio dlg:id="e"/></dlg:radiogroup><dlg:combobox dlg:id="f"/><dlg:menulist dlg:id="g"/>'
                '<dlg:titledbox dlg:id="h"><dlg:title dlg:value="x"/></dlg:titledbox>'
                '<dlg:spinbutton dlg:id="i"/><dlg:scrollbar dlg:id="j"/>')
        self.assertEqual(unwritable_form_content(dialog(body)), ([], []))

    def test_other_controls_are_named(self):
        lost, _items = unwritable_form_content(dialog('<dlg:img dlg:id="Image1"/><dlg:datefield dlg:id="Date1"/>'))
        self.assertEqual(lost, ["Image1", "Date1"])

    def test_event_bindings_are_not_controls(self):
        body = '<dlg:button dlg:id="a"><script:event script:event-name="x"/></dlg:button>'
        self.assertEqual(unwritable_form_content(dialog(body)), ([], []))

    def test_fixed_list_items_are_reported(self):
        body = ('<dlg:menulist dlg:id="List1"><dlg:menupopup><dlg:menuitem dlg:value="x"/></dlg:menupopup></dlg:menulist>'
                '<dlg:combobox dlg:id="Combo1"/>')
        self.assertEqual(unwritable_form_content(dialog(body)), ([], ["List1"]))

    def test_word_filters(self):
        self.assertTrue(is_word_filter("MS Word 97"))
        self.assertTrue(is_word_filter("MS Word 2007 XML VBA"))
        self.assertFalse(is_word_filter("writer8"))


class Patches(unittest.TestCase):
    def patch_text(self, name):
        series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        self.assertIn(name, series)
        return (ROOT / "patches/libreoffice" / name).read_text(encoding="utf-8")

    def test_form_export_writes_every_designer_part(self):
        text = self.patch_text("hst-vba-userform-export.patch")
        for part in ("\\003VBFrame", "\\001CompObj", "BaseClass=", "Package={AC9F2F90-E877-11CE-9F68-00AA00574A4F}",
                     "{0D452EE1-E08F-101A-852E-02608C4D0BB4}", "oox/source/ole/vbaformexport.cxx"):
            self.assertIn(part, text)

    def test_save_guard_defaults_to_the_safe_answer_in_vietnamese(self):
        text = self.patch_text("hst-macro-save-guard.patch")
        self.assertIn("set_default_response( RET_NO )", text)
        for phrase in ("Lưu không có macro", "Chọn định dạng khác", "không giữ được macro"):
            self.assertIn(phrase, text)


class Validator(unittest.TestCase):
    def test_decompress_literal_and_copy_tokens(self):
        chunk = bytes([0, *b"abcdefgh"])
        header = struct.pack("<H", 0xB000 | (len(chunk) - 1))
        self.assertEqual(vba_cfb.decompress(b"\x01" + header + chunk), b"abcdefgh")

    def test_rejects_non_compound_file(self):
        with self.assertRaises(ValueError):
            vba_cfb.Cfb(b"not a compound file")

    def test_record_past_the_stream_is_a_problem(self):
        problems = []
        vba_form_structure.record_size(struct.pack("<HH", 0x0400, 100), 0, 0x0400, "f", problems)
        self.assertEqual(problems, ["f: record runs past the stream"])

    def test_wrong_record_version_is_a_problem(self):
        problems = []
        vba_form_structure.record_size(struct.pack("<HH", 0x0200, 0), 0, 0x0400, "f", problems)
        self.assertEqual(problems, ["f: version 0x0200, expected 0x0400"])


if __name__ == "__main__":
    unittest.main()
