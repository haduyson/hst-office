# SPDX-License-Identifier: AGPL-3.0-only
"""New-style tone placement on oa/oe/uy for the Vietnamese UI translations."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/l10n"))
from vi_tone import fix, normalize_po  # noqa: E402


class TonePlacementTest(unittest.TestCase):
    def test_rhymes_at_syllable_end_move_the_tone(self):
        for old, new in (("Xoá", "Xóa"), ("hoà", "hòa"), ("khoẻ", "khỏe"), ("Huỷ", "Hủy"), ("Tuỳ chọn", "Tùy chọn"),
                         ("luỹ thừa", "lũy thừa"), ("Uỷ quyền", "Ủy quyền"), ("_Xoá", "_Xóa"), ("Thuỵ Điển", "Thụy Điển")):
            self.assertEqual(fix(old), new)

    def test_other_syllables_are_unchanged(self):
        for text in ("toán", "Hoàn tác", "khoảng", "quý", "Ngoà_i", "thoại", "Xóa", "Hủy", "Ngoài"):
            self.assertEqual(fix(text), text)

    def test_decomposed_input_is_fixed(self):
        self.assertEqual(fix("Hu" + "ỷ"), "Hủy")

    def test_po_only_msgstr_changes_and_header_is_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "messages.po"
            path.write_text('msgid ""\nmsgstr ""\n"Last-Translator: Hoà\\n"\n\nmsgctxt "Xoá"\nmsgid "Delete"\n'
                            'msgstr ""\n"Xoá "\n"tuỳ ý"\n', encoding="utf-8")
            self.assertEqual(normalize_po(path), 2)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Hoà", text)
            self.assertIn('msgctxt "Xoá"', text)
            self.assertIn('"Xóa "\n"tùy ý"', text)


if __name__ == "__main__":
    unittest.main()
