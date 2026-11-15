# SPDX-License-Identifier: AGPL-3.0-only
"""ConvertEncoding in Sheets: one selected cell means the sheet's used area; the HST menu offers it in Sheets."""
import _paths  # noqa: F401
import os
import unittest
import xml.etree.ElementTree as ET

from hst_office.encoding import Converter
from hst_office.encoding_calc_ranges import convert_grid, is_single_cell, normalize

OOR = "{http://openoffice.org/2001/registry}"


class SingleCell(unittest.TestCase):
    def test_single_cell(self):
        self.assertTrue(is_single_cell([(0, 3, 7, 3, 7)]))
        self.assertFalse(is_single_cell([(0, 3, 7, 4, 7)]))
        self.assertFalse(is_single_cell([(0, 3, 7, 3, 8)]))
        self.assertFalse(is_single_cell([(0, 1, 1, 1, 1), (0, 3, 3, 3, 3)]))
        self.assertFalse(is_single_cell([]))

    def test_whole_sheet_of_one_cell_is_the_used_area(self):
        # what target_rects(doc, rects, sheet) normalizes: the sheet clipped to its used area
        self.assertEqual(normalize([(0, 0, 0, 1 << 30, 1 << 30)], {0: (4, 9)}), [(0, 0, 0, 4, 9)])

    def test_text_cells_of_a_range_convert_numbers_stay(self):
        grid = [("Hµ Néi", 12.0), ("", "TP Hå ChÝ Minh")]
        out, changed = convert_grid(grid, lambda text, upper: Converter("tcvn3").convert(text, upper=upper)[0])
        self.assertEqual(out[0][0], "Hà Nội")
        self.assertEqual(out[0][1], 12.0)
        self.assertEqual(out[1][0], "")
        self.assertEqual(out[1][1], "TP Hồ Chí Minh")
        self.assertEqual(changed, {(0, 0), (1, 1)})


class Menu(unittest.TestCase):
    def test_hst_menu_offers_it_in_sheets(self):
        root = ET.parse(os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "Addons.xcu")).getroot()
        for node in root.iter("node"):
            props = {p.get(OOR + "name"): p.findtext("value") for p in node.findall("prop")}
            if props.get("URL") == "org.hst.office.vi:ConvertEncoding":
                contexts = props["Context"].split(",")
                self.assertIn("com.sun.star.sheet.SpreadsheetDocument", contexts)
                self.assertIn("com.sun.star.text.TextDocument", contexts)
                return
        self.fail("ConvertEncoding not in Addons.xcu")


if __name__ == "__main__":
    unittest.main()
