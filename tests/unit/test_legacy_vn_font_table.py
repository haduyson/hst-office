# SPDX-License-Identifier: AGPL-3.0-only
"""The TCVN3/VNI table in the WMF import patch matches data/vietnamese/encoding-maps.json."""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = importlib.util.spec_from_file_location(
    "legacy_vn_table", os.path.join(ROOT, "scripts", "patches", "generate-legacy-vn-font-table.py"))
TABLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TABLE)


class LegacyVietnameseFontTableTest(unittest.TestCase):
    def test_patch_carries_current_table(self):
        self.assertEqual(TABLE.header_in_patch(), TABLE.generate())

    def test_known_letters(self):
        header = TABLE.generate()
        # TCVN3 0xBE = "ắ" (row 0xB8..0xBF, 7th entry), uppercase table "Ắ"; VNI "o" + 0xF8 = "ò"
        lower = header.split("aTcvn3[128] = {")[1].split("};")[0].split(",")
        upper = header.split("aTcvn3Upper[128] = {")[1].split("};")[0].split(",")
        self.assertEqual(int(lower[0xBE - 0x80], 16), ord("ắ"))
        self.assertEqual(int(upper[0xBE - 0x80], 16), ord("Ắ"))
        self.assertEqual(int(lower[0xAE - 0x80], 16), ord("đ"))
        self.assertIn("{ 0x6F, 0xF8, 0x00F2 }", header)
        self.assertIn('u"Times New Roman"_ustr', header)


if __name__ == "__main__":
    unittest.main()
