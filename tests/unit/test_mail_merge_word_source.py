# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư, Word documents: the recipient list a Word mail-merge .docx names (w:mailMerge), where it is looked for
when the document moved, and the computed columns the staging copy gets for the document's Word fields."""
import datetime
import os
import sys
import tempfile
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_format as fmt
from hst_office import mail_merge_table as mt
from hst_office import mail_merge_word_link as link
from hst_office import mail_merge_word_source as ws

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import mail_merge_word_samples as samples  # noqa: E402


class Settings(unittest.TestCase):
    def test_excel_list_from_the_relationship(self):
        found = ws.parse(samples.settings_xml("C:\\Thu\\ds.xlsx").encode(),
                         ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                          '<Relationship Id="rId1" Target="file:///C:\\Tron%20thu\\ds.xlsx" TargetMode="External"/>'
                          '</Relationships>').encode())
        self.assertEqual((found.path, found.sheet, found.name), ("C:\\Tron thu\\ds.xlsx", samples.SHEET, "ds.xlsx"))

    def test_connect_string_without_relationship(self):
        found = ws.parse(samples.settings_xml("D:\\Danh sach\\nv.xlsx").encode())
        self.assertEqual((found.path, found.sheet), ("D:\\Danh sach\\nv.xlsx", samples.SHEET))

    def test_csv_from_the_query(self):
        found = ws.parse(samples.settings_xml("C:\\Thu\\ds.csv").encode())
        self.assertEqual((found.path, found.sheet), ("C:\\Thu\\ds.csv", None))

    def test_blank_lines_suppressed_by_default(self):
        self.assertFalse(ws.parse(samples.settings_xml("C:\\Thu\\ds.xlsx").encode()).keep_blank_lines)

    def test_do_not_suppress_blank_lines(self):
        for source in ("C:\\Thu\\ds.xlsx", "C:\\Thu\\ds.csv"):
            xml = samples.settings_xml(source, keep_blank_lines=True)
            self.assertTrue(ws.parse(xml.encode()).keep_blank_lines, source)
        off = xml.replace("<w:doNotSuppressBlankLines/>", '<w:doNotSuppressBlankLines w:val="false"/>')
        self.assertFalse(ws.parse(off.encode()).keep_blank_lines)

    def test_word_output_leaves_out_empty_field_paragraphs(self):
        # recipient 2 has no Chức vụ: the paragraph is only that MERGEFIELD, so Word leaves it out by default
        suppressed, kept = samples.word_output(), samples.word_output(keep_blank_lines=True)
        self.assertEqual(len(suppressed[1]), len(samples.EXPECTED[1]) - 1)
        self.assertNotIn("", suppressed[1])
        self.assertEqual(kept, samples.EXPECTED)
        self.assertEqual(suppressed[0], samples.EXPECTED[0])

    def test_no_mail_merge(self):
        xml = '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
        self.assertIsNone(ws.parse(xml.encode()))

    def test_whole_package(self):
        with tempfile.TemporaryDirectory() as folder:
            path = samples.write_all(folder)
            found = ws.read(path)
            self.assertEqual(found.name, samples.XLSX)
            # the Windows folder does not exist here: the list next to the letter is found
            self.assertEqual(ws.locate(found.path, folder), os.path.join(folder, samples.XLSX))
            self.assertIsNone(ws.read(os.path.join(folder, samples.XLSX)))  # not a Word package


class Paths(unittest.TestCase):
    def test_targets(self):
        self.assertEqual(ws.target_path("file:///C:\\a\\b.xlsx"), "C:\\a\\b.xlsx")
        self.assertEqual(ws.target_path("file:///home/u/a%20b.xlsx"), "/home/u/a b.xlsx")
        self.assertEqual(ws.target_path("file://srv/share/a.xlsx"), "\\\\srv\\share\\a.xlsx")
        self.assertEqual(ws.target_path("ds.xlsx"), "ds.xlsx")

    def test_remote_is_never_probed(self):
        self.assertTrue(ws.is_remote("\\\\srv\\share\\a.xlsx"))
        self.assertTrue(ws.is_remote("https://example.org/a.xlsx"))
        self.assertFalse(ws.is_remote("C:\\a.xlsx"))
        self.assertIsNone(ws.locate("\\\\srv\\share\\a.xlsx", "/tmp"))

    @unittest.skipIf(os.sep == "\\", "POSIX paths")
    def test_relative_and_next_to_the_document(self):
        self.assertEqual(ws.candidates("..\\ds\\a.csv", "/d/x"), ["/d/ds/a.csv", "/d/x/a.csv"])
        self.assertEqual(ws.candidates("/home/u/a.xlsx", "/d"), ["/home/u/a.xlsx", "/d/a.xlsx"])
        self.assertEqual(ws.candidates("C:\\u\\a.xlsx", "/d"), ["/d/a.xlsx"])


class Columns(unittest.TestCase):
    TABLE = mt.Table(["Họ và tên", "Ngày sinh", "Lương"], [fmt.COL_TEXT, fmt.COL_DATE, fmt.COL_NUMBER],
                     [("Nguyễn Văn An", float((datetime.date(1985, 3, 7) - fmt.NULL_DATE).days), 15000000.0)])

    def test_word_columns_and_aliases(self):
        columns = ["Họ_và_tên", "Lương", 'MERGEFIELD Lương \\# "#,##0"', "Khác", "Ngày sinh"]
        self.assertEqual(link.word_column_names(columns, self.TABLE.headers),
                         ["Họ_và_tên", 'MERGEFIELD Lương \\# "#,##0"'])
        values = {name: function(self.TABLE.rows[0], 1)
                  for name, function in link.extra_columns(self.TABLE, columns)}
        self.assertEqual(values, {"Họ_và_tên": "Nguyễn Văn An", 'MERGEFIELD Lương \\# "#,##0"': "15,000,000"})

    def test_staging_holds_the_word_results(self):
        extra = link.extra_columns(self.TABLE, ['IF { MERGEFIELD Lương } > 10000000 "cao" "thường"'])
        headers, _kinds, rows = mt.staging(self.TABLE, [0], extra=extra)
        self.assertEqual(rows[0][headers.index('IF { MERGEFIELD Lương } > 10000000 "cao" "thường"')], "cao")
        self.assertNotIn('IF { MERGEFIELD Lương } > 10000000 "cao" "thường"', mt.insertable(headers))

    def test_kinds_of_adopted_word_fields(self):
        self.assertEqual(link.word_kind(self.TABLE, "Ngày sinh", {}), fmt.DATE)
        self.assertEqual(link.word_kind(self.TABLE, "Lương", {}), fmt.TEXT)
        self.assertEqual(link.word_kind(self.TABLE, "Lương", {"Lương": fmt.NUMBER}), fmt.NUMBER)
        self.assertEqual(link.word_kind(self.TABLE, "Họ_và_tên", {}), fmt.TEXT)


if __name__ == "__main__":
    unittest.main()
