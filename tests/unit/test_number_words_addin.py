# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""VND() and USD(): every argument form of the two Vietnamese Excel add-ins, and the outputs their public tutorials
and authors show (sources in the comments; where the two add-ins differ, HST reads as the add-in workbook does)."""
import unittest

import _paths  # noqa: F401

from hst_office import number_words as nw
from hst_office.number_words_addin import usd, vnd

TRUE, FALSE = 1.0, 0.0  # Calc passes booleans to add-in functions as numbers


class VndWorkbookLayout(unittest.TestCase):
    """VND(number; [add_unit]; [charset]; [unit]; [sub_unit])."""

    def test_tutorial_outputs(self):
        cases = [
            ((9.0, FALSE, 1.0), "Chín"),                                    # ketoanleanh screenshot, =VND(C3; FALSE;1)
            ((-9.0, FALSE, 1.0), "Âm chín"),                                # same screenshot
            ((9.5, FALSE, 1.0), "Chín phẩy năm mươi"),                      # same screenshot
            ((123000.0, TRUE), "Một trăm hai mươi ba ngàn đồng"),           # ketoanleanh, unit ticked
            ((245000.0, TRUE), "Hai trăm bốn mươi lăm ngàn đồng"),          # download.com.vn guide
            ((1234.0,), "Một ngàn hai trăm ba mươi bốn"),                   # VOH, =vnd(B3) (no final period: see below)
            ((15.79, TRUE), "Mười lăm đồng bảy mươi chín xu"),              # help text copy, 15,79
        ]
        for args, expected in cases:
            self.assertEqual(vnd(*args), expected, args)

    def test_argument_forms(self):
        self.assertEqual(vnd(1500.0), "Một ngàn năm trăm")
        self.assertEqual(vnd(1500.0, TRUE), "Một ngàn năm trăm đồng")
        self.assertEqual(vnd(1500.0, "TRUE"), "Một ngàn năm trăm đồng")
        self.assertEqual(vnd(1500.0, FALSE), "Một ngàn năm trăm")
        self.assertEqual(vnd(1500.5, TRUE, 1.0, "đồng", "xu"), "Một ngàn năm trăm đồng năm mươi xu")  # GPE long form
        self.assertEqual(vnd(1500.5, TRUE, None, "dollar", "cent"), "Một ngàn năm trăm dollar năm mươi cent")
        self.assertEqual(vnd(1500.5, TRUE, None, "đồng", ""), "Một ngàn năm trăm lẻ một đồng")  # "" rounds to đồng
        self.assertEqual(vnd(1500.5, FALSE, 1.0, "đồng", "xu"), "Một ngàn năm trăm phẩy năm mươi")

    def test_reading_rules(self):
        cases = {0: "Không", 15: "Mười lăm", 21: "Hai mươi mốt", 24: "Hai mươi bốn", 105: "Một trăm lẻ năm",
                 1005: "Một ngàn không trăm lẻ năm", 1000000: "Một triệu", 1000001: "Một triệu không trăm lẻ một",
                 10 ** 9: "Một tỷ", 1001000000: "Một tỷ không trăm lẻ một triệu", 2 * 10 ** 12: "Hai ngàn tỷ"}
        for number, expected in cases.items():
            self.assertEqual(vnd(float(number)), expected, number)
        self.assertEqual(vnd(123.04), "Một trăm hai mươi ba phẩy không bốn")
        self.assertEqual(vnd(-0.004), "Không")
        self.assertEqual(vnd(0.5, TRUE), "Năm mươi xu")
        self.assertEqual(vnd(9.999, TRUE), "Mười đồng")

    def test_limits_and_bad_arguments(self):
        self.assertTrue(vnd(999999999999999.0).startswith("Chín trăm chín mươi chín ngàn"))
        for args in ((1e15,), (float("inf"),), (((1.0,),),), (1.0, "maybe")):
            with self.assertRaises(nw.NumberWordsError):
                vnd(*args)


class VndXllLayout(unittest.TestCase):
    """VND(amount; [charset]; [unit]; [sub_unit]; [sub_unit_factor]; [grouping]): the unit is always read."""

    def test_author_examples(self):
        cases = [  # giaiphapexcel thread of the XLL add-in's author; HST omits its "và", "chẵn" and final period
            ((125000.0, TRUE), "Một trăm hai mươi lăm ngàn đồng"),
            ((9.25, 3.0, "đồng", "xu"), "Chín đồng hai mươi lăm xu"),
            ((12.5, None, "đồng", "hào", 10.0), "Mười hai đồng năm hào"),
            ((120.53, None, "giờ", "phút", 60.0), "Một trăm hai mươi giờ ba mươi hai phút"),
            ((2500.32, None, "tấn", "kg", 1000.0), "Hai ngàn năm trăm tấn ba trăm hai mươi kg"),
            ((309848560.0, None, None, None, None, TRUE),
             "Ba trăm lẻ chín triệu, tám trăm bốn mươi tám ngàn, năm trăm sáu mươi đồng"),
            ((120050.0, 3.0, "USD"), "Một trăm hai mươi ngàn không trăm năm mươi USD"),
        ]
        for args, expected in cases:
            self.assertEqual(vnd(*args), expected, args)

    def test_charset_number_reads_the_unit(self):
        for charset in (1.0, 2.0, 3.0):
            self.assertEqual(vnd(1000.0, charset), "Một ngàn đồng")

    def test_grouping_never_splits_scales(self):
        self.assertEqual(vnd(2 * 10 ** 12 + 5, None, None, None, None, TRUE), "Hai ngàn tỷ, không trăm lẻ năm đồng")
        self.assertEqual(vnd(1000.0, None, None, None, None, FALSE), "Một ngàn đồng")

    def test_bad_factor(self):
        with self.assertRaises(nw.NumberWordsError):
            vnd(1.5, None, "giờ", "phút", -60.0)


class Usd(unittest.TestCase):
    def test_workbook_layout(self):
        self.assertEqual(usd(125000.0), "One hundred and twenty-five thousand")
        self.assertEqual(usd(125000.0, TRUE), "One hundred and twenty-five thousand dollars")
        self.assertEqual(usd(123.45, TRUE), "One hundred and twenty-three dollars and forty-five cents")
        self.assertEqual(usd(1.0, TRUE), "One dollar")
        self.assertEqual(usd(-2.5), "Minus two point five")

    def test_xll_layout(self):
        self.assertEqual(usd(11000.0, "VND"), "Eleven thousand VND")                 # author: =USD(11000,"VND")
        self.assertEqual(usd(235000.0, "dollars", "cents"), "Two hundred and thirty-five thousand dollars")
        self.assertEqual(usd(12.5, "dollar", "dime", 10.0), "Twelve dollars and five dime")  # units it does not know stay as typed
        self.assertEqual(usd(2500300.25, "dollar", "cent", None, TRUE),
                         "Two million, five hundred thousand, three hundred dollars and twenty-five cents")


if __name__ == "__main__":
    unittest.main()
