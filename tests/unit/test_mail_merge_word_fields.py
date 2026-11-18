# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư, Word fields: MERGEFIELD switches (\\# \\@ \\* \\b \\f) and IF fields evaluated with Word's rules, against
the Word-made sample letter (tests/runtime/mail_merge_word_samples.py) and its expected Word output."""
import datetime
import os
import sys
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_format as fmt
from hst_office import mail_merge_table as mt
from hst_office import mail_merge_word_fields as wf
from hst_office import mail_merge_word_pictures as pictures

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import mail_merge_word_samples as samples  # noqa: E402

KINDS = {"n": fmt.COL_NUMBER, "d": fmt.COL_DATE, "t": fmt.COL_TEXT, "s": fmt.COL_TEXT}


def sample_table():
    """The sample list as the recipient reader gives it (dates as day numbers, the Text column as text)."""
    rows = []
    for values in samples.ROWS:
        row = []
        for kind, value in zip(samples.KINDS, values):
            if value == "":
                row.append(None)
            elif kind == "d":
                row.append(float((value - datetime.date(1899, 12, 30)).days))
            elif kind == "n":
                row.append(float(value))
            else:
                row.append(str(value))
        rows.append(tuple(row))
    return mt.Table(samples.HEADERS, [KINDS[k] for k in samples.KINDS], rows)


def column(instruction):
    """The column the DOCX import gives a field (hstwordmergeimport.cxx: trimmed, nested fields as { })."""
    return instruction.strip().replace("\x13", "{").replace("\x15", "}")


def merged(table, index):
    record = wf.Record(wf.table_lookup(table, table.rows[index]), index + 1)
    return tuple("".join(text if result is None else wf.evaluate_code(column(text), record) for text, result in parts)
                 for parts in samples.PARAGRAPHS)


class SampleLetter(unittest.TestCase):
    def test_every_recipient_matches_word(self):
        table = sample_table()
        for index, expected in enumerate(samples.EXPECTED):
            with self.subTest(recipient=index + 1):
                self.assertEqual(merged(table, index), expected)


class NumberPictures(unittest.TestCase):
    def test_grouping_in_the_convention_written(self):
        self.assertEqual(pictures.format_number(1500000.0, "#,##0"), "1,500,000")
        self.assertEqual(pictures.format_number(1500000.0, "#.##0"), "1.500.000")
        self.assertEqual(pictures.format_number(1234.567, "#.##0,00"), "1.234,57")
        self.assertEqual(pictures.format_number(1234.5, "#,##0.00"), "1,234.50")

    def test_word_examples(self):
        self.assertEqual(pictures.format_number(15.0, "$###"), "$ 15")
        self.assertEqual(pictures.format_number(9.0, "00.00"), "09.00")
        self.assertEqual(pictures.format_number(0.75, ".x"), ".8")
        self.assertEqual(pictures.format_number(1.0, "000"), "001")

    def test_sections_and_signs(self):
        picture = "#,##0 'đ';(#,##0 'đ');'không'"
        self.assertEqual(pictures.format_number(-2500.0, picture), "(2,500 đ)")
        self.assertEqual(pictures.format_number(0.0, picture), "không")
        self.assertEqual(pictures.format_number(-5.0, "#,##0"), "   -5")
        self.assertEqual(pictures.format_number(-1234.5, "#,##0.00"), "-1,234.50")
        self.assertEqual(pictures.format_number(5.0, "+0"), "+5")

    def test_half_rounds_up(self):
        self.assertEqual(pictures.format_number(8250000.5, "#,##0"), "8,250,001")

    def test_text_numbers(self):
        self.assertEqual(pictures.to_number("1.500.000"), 1500000.0)
        self.assertEqual(pictures.to_number("8250000,5"), 8250000.5)
        self.assertEqual(pictures.to_number("1,234.5"), 1234.5)
        self.assertIsNone(pictures.to_number("Nguyễn"))


class DatePictures(unittest.TestCase):
    MOMENT = datetime.datetime(1985, 3, 7, 14, 5)

    def test_vietnamese_long_date(self):
        self.assertEqual(pictures.format_date(self.MOMENT, "'ngày' dd 'tháng' MM 'năm' yyyy"),
                         "ngày 07 tháng 03 năm 1985")

    def test_month_and_minute_differ_by_case(self):
        self.assertEqual(pictures.format_date(self.MOMENT, "d/M/yy HH:mm"), "7/3/85 14:05")
        self.assertEqual(pictures.format_date(self.MOMENT, "h:mm AM/PM"), "2:05 PM")

    def test_names(self):
        self.assertEqual(pictures.format_date(self.MOMENT, "dddd"), "Thứ Năm")
        self.assertEqual(pictures.format_date(self.MOMENT, "MMMM", "en"), "March")

    def test_text_dates(self):
        self.assertEqual(pictures.to_date("07/03/1985"), datetime.datetime(1985, 3, 7))
        self.assertIsNone(pictures.to_date("không rõ"))


class Fields(unittest.TestCase):
    def record(self, **values):
        def lookup(name):
            key = wf.name_key(name)
            for header, value in values.items():
                if wf.name_key(header) == key:
                    return value, fmt.COL_NUMBER if isinstance(value, float) else fmt.COL_TEXT
            return None
        return wf.Record(lookup, 4)

    def test_word_names_match_headers(self):
        self.assertEqual(wf.name_key("Họ_và_tên"), wf.name_key("Họ và tên"))
        self.assertEqual(wf.name_key("HỌ VÀ TÊN"), wf.name_key("họ_và_tên"))

    def test_before_after_only_with_a_value(self):
        code = 'MERGEFIELD Chuc_vu \\b "Chức vụ: " \\f "."'
        self.assertEqual(wf.evaluate_code(code, self.record(Chuc_vu="kế toán")), "Chức vụ: kế toán.")
        self.assertEqual(wf.evaluate_code(code, self.record(Chuc_vu="")), "")

    def test_if_operators(self):
        record = self.record(Diem=7.5, Ten="An")
        self.assertEqual(wf.evaluate_code('IF { MERGEFIELD Diem } >= 5 "Đạt" "Chưa đạt"', record), "Đạt")
        self.assertEqual(wf.evaluate_code('IF { MERGEFIELD Diem } < 5 "Đạt" "Chưa đạt"', record), "Chưa đạt")
        self.assertEqual(wf.evaluate_code('IF "{ MERGEFIELD Ten }" <> "A?" "x" "y"', record), "y")
        self.assertEqual(wf.evaluate_code('IF "{ MERGEFIELD Ten }" = "an" "x" "y"', record), "y")

    def test_if_without_operator_and_missing_false_text(self):
        self.assertEqual(wf.evaluate_code('IF { MERGEFIELD Diem } "có" "không"', self.record(Diem=0.0)), "không")
        self.assertEqual(wf.evaluate_code('IF 1 = 2 "có"', self.record()), "")

    def test_switches_on_if_and_record_number(self):
        self.assertEqual(wf.evaluate_code('IF 1 = 1 "ông" "bà" \\* Upper', self.record()), "ÔNG")
        self.assertEqual(wf.evaluate_code("MERGEREC \\# 000", self.record()), "004")

    def test_unknown_field_and_broken_code(self):
        self.assertEqual(wf.evaluate_code("MERGEFIELD Khong_co", self.record()), "")
        self.assertEqual(wf.evaluate_code("IF { MERGEFIELD x = 1", self.record()), "")

    def test_codes_and_names(self):
        self.assertTrue(wf.is_word_code('MERGEFIELD Lương \\# "#,##0"'))
        self.assertTrue(wf.is_word_code('IF { MERGEFIELD x } = "1" "a" "b"'))
        self.assertFalse(wf.is_word_code("Họ và tên"))
        self.assertEqual(wf.names_text('IF { MERGEFIELD Giới_tính } = "Nam" "Ông" "Bà"'),
                         '<IF «Giới_tính» = "Nam" "Ông" "Bà">')
        self.assertEqual(wf.names_text('MERGEFIELD Lương \\# "#,##0"'), "<Lương>")
        self.assertEqual(wf.merge_names('IF { MERGEFIELD a } = "1" "{ MERGEFIELD b }" ""'), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
