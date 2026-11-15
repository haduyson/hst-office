# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư value formats: vi-VN numbers and dates, words, the kinds offered per column, and reading a field's
kind back from its column name and number-format code."""
import datetime
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_format as fmt

DAY = (datetime.date(1985, 3, 7) - fmt.NULL_DATE).days  # spreadsheet day number of 07/03/1985


class Numbers(unittest.TestCase):
    def test_thousands_grouped_with_dots(self):
        self.assertEqual(fmt.render(fmt.NUMBER, 1500000.0), "1.500.000")
        self.assertEqual(fmt.render(fmt.NUMBER, 999.0), "999")
        self.assertEqual(fmt.render(fmt.NUMBER, 0.0), "0")
        self.assertEqual(fmt.render(fmt.NUMBER, -12345678.0), "-12.345.678")

    def test_whole_numbers_round_half_up(self):
        self.assertEqual(fmt.render(fmt.NUMBER, 1234.5), "1.235")

    def test_two_decimals_with_comma(self):
        self.assertEqual(fmt.render(fmt.NUMBER2, 1234567.5), "1.234.567,50")
        self.assertEqual(fmt.render(fmt.NUMBER2, 2.0), "2,00")
        self.assertEqual(fmt.render(fmt.NUMBER2, -0.25), "-0,25")

    def test_text_and_empty_values_pass_through(self):
        self.assertEqual(fmt.render(fmt.NUMBER, "chưa có"), "chưa có")
        self.assertEqual(fmt.render(fmt.NUMBER, None), "")


class Dates(unittest.TestCase):
    def test_short_date_has_four_digit_year(self):
        self.assertEqual(fmt.render(fmt.DATE, float(DAY)), "07/03/1985")

    def test_long_date_reads_like_an_official_letter(self):
        self.assertEqual(fmt.render(fmt.DATE_LONG, float(DAY)), "ngày 07 tháng 03 năm 1985")


class Words(unittest.TestCase):
    def test_number_and_money_words(self):
        self.assertEqual(fmt.render(fmt.WORDS, 1500000.0), "Một triệu năm trăm nghìn")
        self.assertEqual(fmt.render(fmt.MONEY_WORDS, 1500000.0), "Một triệu năm trăm nghìn đồng chẵn")

    def test_words_follow_the_number_words_defaults(self):
        settings = {"number_options": "ngàn linh", "money_options": "", "unit": "đồng", "sub_unit": ""}
        self.assertEqual(fmt.render(fmt.WORDS, 1005.0, settings), "Một ngàn không trăm linh năm")

    def test_too_many_digits_falls_back_to_the_number(self):
        self.assertEqual(fmt.render(fmt.WORDS, 1e17), "100000000000000000")


class Kinds(unittest.TestCase):
    def test_default_kind_per_column(self):
        self.assertEqual(fmt.default_kind(fmt.COL_NUMBER, (1.0, 2.0)), fmt.NUMBER)
        self.assertEqual(fmt.default_kind(fmt.COL_NUMBER, (1.5, None)), fmt.NUMBER2)
        self.assertEqual(fmt.default_kind(fmt.COL_DATE), fmt.DATE)
        self.assertEqual(fmt.default_kind(fmt.COL_TEXT), fmt.TEXT)

    def test_word_columns_round_trip(self):
        name = fmt.word_column("Số tiền", fmt.MONEY_WORDS)
        self.assertEqual(name, "Số tiền (tiền bằng chữ)")
        self.assertEqual(fmt.split_word_column(name), ("Số tiền", fmt.MONEY_WORDS))
        self.assertEqual(fmt.split_word_column("Họ và tên"), ("Họ và tên", None))

    def test_kind_of_field(self):
        self.assertEqual(fmt.kind_of_field("Số tiền", "#.##0", False), ("Số tiền", fmt.NUMBER))
        self.assertEqual(fmt.kind_of_field("Ngày", fmt.CODES[fmt.DATE_LONG], False), ("Ngày", fmt.DATE_LONG))
        self.assertEqual(fmt.kind_of_field("Số tiền", "#.##0", True), ("Số tiền", fmt.TEXT))
        self.assertEqual(fmt.kind_of_field("Số tiền (bằng chữ)", "General", True), ("Số tiền", fmt.WORDS))

    def test_every_offered_kind_renders(self):
        for column_kind, kinds in fmt.KINDS_FOR_COLUMN.items():
            for kind in kinds:
                self.assertTrue(fmt.render(kind, 31113.0 if column_kind != fmt.COL_TEXT else "x"))

    def test_plain_number_without_trailing_zero(self):
        self.assertEqual(fmt.plain_number(1500000.0), "1500000")
        self.assertEqual(fmt.plain_number(2.5), "2,5")


if __name__ == "__main__":
    unittest.main()
