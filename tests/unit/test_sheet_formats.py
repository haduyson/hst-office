# SPDX-License-Identifier: AGPL-3.0-only
import datetime
import unittest

import _paths  # noqa: F401
from hst_office import sheets


class FormatSpecs(unittest.TestCase):
    def test_codes_come_from_shared_data(self):
        self.assertEqual(sheets.format_spec("date")["code"], "DD/MM/YYYY")
        self.assertEqual(sheets.format_spec("vnd")["code"], "#,##0 [$₫-42A]")
        self.assertEqual(sheets.format_spec("percent")["code"], "0.00%")
        for kind in sheets.KINDS:
            spec = sheets.format_spec(kind)
            self.assertEqual((spec["locale"], spec["language"], spec["country"]), ("vi-VN", "vi", "VN"))

    def test_unknown_kind_rejected(self):
        for kind in ("", "auto", "formula", None):
            with self.assertRaises(ValueError):
                sheets.format_spec(kind)

    def test_unsafe_code_rejected(self):
        data = {"locale": "vi-VN", "formats": {"date": {"code": "=HYPERLINK(\"x\")", "example": ""}}}
        with self.assertRaises(ValueError):
            sheets.format_spec("date", data)

    def test_blockers(self):
        self.assertEqual(sheets.sheet_blockers(False, True), [])
        self.assertEqual(sheets.sheet_blockers(True, True), ["sheet-protected"])
        self.assertEqual(sheets.sheet_blockers(True, False), ["no-selection", "sheet-protected"])

    def test_calc_null_date_serial(self):
        # Calc's default null date is 1899-12-30; 2026-02-05 is therefore serial 46058.
        self.assertEqual((datetime.date(2026, 2, 5) - datetime.date(1899, 12, 30)).days, 46058)


if __name__ == "__main__":
    unittest.main()
