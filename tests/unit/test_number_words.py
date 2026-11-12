# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese and English number words (DOCSO, DOCTIEN, the dialog and the Writer command)."""
import unittest
from decimal import Decimal

import _paths  # noqa: F401

from hst_office import number_words as nw
from hst_office import utilities_texts as T
from hst_office.number_words_choice import error_text, formula, words


def opts(text=""):
    return nw.parse_options(text)


class ReadNumber(unittest.TestCase):
    CASES = {
        0: "Không", 1: "Một", 5: "Năm", 10: "Mười", 11: "Mười một", 14: "Mười bốn", 15: "Mười lăm", 20: "Hai mươi",
        21: "Hai mươi mốt", 24: "Hai mươi bốn", 25: "Hai mươi lăm", 55: "Năm mươi lăm", 100: "Một trăm",
        101: "Một trăm lẻ một", 105: "Một trăm lẻ năm", 110: "Một trăm mười", 115: "Một trăm mười lăm",
        121: "Một trăm hai mươi mốt", 1000: "Một nghìn", 1005: "Một nghìn không trăm lẻ năm",
        1015: "Một nghìn không trăm mười lăm", 1100: "Một nghìn một trăm", 10000: "Mười nghìn",
        1000000: "Một triệu", 1000001: "Một triệu không trăm lẻ một", 1005000: "Một triệu không trăm lẻ năm nghìn",
        10000000: "Mười triệu", 1000000000: "Một tỷ", 1000000001: "Một tỷ không trăm lẻ một",
        1000000005: "Một tỷ không trăm lẻ năm", 2000000000000: "Hai nghìn tỷ",
        1001000000: "Một tỷ không trăm lẻ một triệu",
    }

    def test_integers(self):
        for number, expected in self.CASES.items():
            self.assertEqual(nw.read_number(number), expected, number)

    def test_round_numbers_have_no_stray_words(self):
        for number in (10 ** 6, 10 ** 9, 10 ** 12, 10 ** 14):
            self.assertNotIn(",", nw.read_number(number))
            self.assertNotIn("không", nw.read_number(number))

    def test_fifteen_digits_is_the_limit(self):
        self.assertTrue(nw.read_number(999999999999999).startswith("Chín trăm chín mươi chín nghìn chín trăm"))
        for too_big in (10 ** 15, 1e15, 1234567890123456, "1.000.000.000.000.000", -10 ** 15):
            with self.assertRaises(nw.NumberWordsError) as caught:
                nw.read_number(too_big)
            self.assertEqual(caught.exception.code, "too-many-digits")

    def test_negative_and_decimals(self):
        self.assertEqual(nw.read_number(-5), "Âm năm")
        self.assertEqual(nw.read_number(-2.5), "Âm hai phẩy năm")
        self.assertEqual(nw.read_number(3.14), "Ba phẩy một bốn")
        self.assertEqual(nw.read_number(0.05), "Không phẩy không năm")
        self.assertEqual(nw.read_number(0.1 + 0.2), "Không phẩy ba")  # 15 significant digits, not 0.30000000000000004
        self.assertEqual(nw.read_number(-0.0), "Không")

    def test_options(self):
        self.assertEqual(nw.read_number(1005, opts("ngàn linh")), "Một ngàn không trăm linh năm")
        self.assertEqual(nw.read_number(105, opts("LINH")), "Một trăm linh năm")
        self.assertEqual(nw.read_number(24, opts("tư")), "Hai mươi tư")
        self.assertEqual(nw.read_number(14, opts("tư")), "Mười bốn")
        self.assertEqual(nw.read_number(1000, opts("ngan")), "Một ngàn")
        self.assertEqual(opts("ngàn, linh; tư en").text(), "ngàn linh tư en")
        self.assertEqual(opts("").text(), "")
        with self.assertRaises(nw.NumberWordsError) as caught:
            opts("ngàn xyz")
        self.assertEqual((caught.exception.code, caught.exception.detail), ("bad-option", "xyz"))

    def test_english(self):
        en = opts("tiếng Anh")
        self.assertEqual(nw.read_number(105, en), "One hundred and five")
        self.assertEqual(nw.read_number(1005, en), "One thousand and five")
        self.assertEqual(nw.read_number(21, en), "Twenty-one")
        self.assertEqual(nw.read_number(-2.5, en), "Minus two point five")
        self.assertEqual(nw.read_number(10 ** 6, en), "One million")


class ReadMoney(unittest.TestCase):
    def test_vnd(self):
        self.assertEqual(nw.read_money(10000000), "Mười triệu đồng chẵn")
        self.assertEqual(nw.read_money(1000001), "Một triệu không trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(0), "Không đồng chẵn")
        self.assertEqual(nw.read_money(-10), "Âm mười đồng chẵn")

    def test_vnd_default_reads_whole_dong(self):
        # no "xu" part by default: the amount is rounded half up (away from zero) to the nearest đồng
        self.assertEqual(nw.read_money(1000.4), "Một nghìn đồng chẵn")
        self.assertEqual(nw.read_money(1000.5), "Một nghìn không trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(1500.75), "Một nghìn năm trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(0.5), "Một đồng chẵn")
        self.assertEqual(nw.read_money(0.4), "Không đồng chẵn")
        self.assertEqual(nw.read_money(-0.4), "Không đồng chẵn")
        self.assertEqual(nw.read_money(-0.5), "Âm một đồng chẵn")
        self.assertEqual(nw.read_money(-1000.5), "Âm một nghìn không trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(2.5), "Ba đồng chẵn")  # half up, not to the even đồng
        self.assertEqual(nw.read_money("1.250.000,5"), "Một triệu hai trăm năm mươi nghìn không trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(1000.5, "đồng"), nw.read_money(1000.5))  # sub-unit left out: still whole đồng

    def test_explicit_xu(self):
        self.assertEqual(nw.read_money(1500.75, "đồng", "xu"), "Một nghìn năm trăm đồng bảy mươi lăm xu")
        self.assertEqual(nw.read_money(1000.5, "đồng", "xu"), "Một nghìn đồng năm mươi xu")
        self.assertEqual(nw.read_money(0.5, "đồng", "xu"), "Năm mươi xu")
        self.assertEqual(nw.read_money(-0.5, "đồng", "xu"), "Âm năm mươi xu")
        self.assertEqual(nw.read_money(1.005, "đồng", "xu"), "Một đồng một xu")  # half up on the decimal text

    def test_units(self):
        self.assertEqual(nw.read_money(12.5, "đô la", "xu"), "Mười hai đô la năm mươi xu")
        self.assertEqual(nw.read_money(1500.5, "đồng", ""), "Một nghìn năm trăm lẻ một đồng chẵn")
        self.assertEqual(nw.read_money(7, "", ""), "Bảy chẵn")

    def test_english_money(self):
        en = opts("en")
        self.assertEqual(nw.read_money(10000000, options=en), "Ten million dollars")
        self.assertEqual(nw.read_money(1, options=en), "One dollar")
        self.assertEqual(nw.read_money(1.01, options=en), "One dollar and one cent")
        self.assertEqual(nw.read_money(1500.75, options=en), "One thousand five hundred dollars and seventy-five cents")
        self.assertEqual(nw.read_money(1000.5, options=en), "One thousand dollars and fifty cents")  # cents by default
        self.assertEqual(nw.read_money(2, "euro", "cent", en), "Two euros")
        self.assertEqual(nw.read_money(3, "dong", "", en), "Three dong")

    def test_money_limit(self):
        with self.assertRaises(nw.NumberWordsError):
            nw.read_money(10 ** 15)


class ParseNumberText(unittest.TestCase):
    def test_accepted(self):
        for text, expected in (("1.000.001", 1000001), ("1,000,001", 1000001), ("1 000 001", 1000001),
                               ("3,5", Decimal("3.5")), ("3.5", Decimal("3.5")), ("1.234,5", Decimal("1234.5")),
                               ("1,234.5", Decimal("1234.5")), ("1.000", 1000), ("-1.500.000 VND", -1500000),
                               ("1.250.000 đ", 1250000), ("$12.50", Decimal("12.50")), (" 5 ", 5)):
            self.assertEqual(nw.parse_number_text(text), expected, text)

    def test_refused(self):
        for text in ("", "abc", "12.34.5", "1,2,3", "1.2345.678", "12 a", "1 2", "--5"):
            with self.assertRaises(nw.NumberWordsError, msg=text):
                nw.parse_number_text(text)


class DialogChoice(unittest.TestCase):
    def choice(self, money=False, unit="đồng", sub="", options=""):
        return {"money": money, "unit": unit, "sub_unit": sub, "options": opts(options)}

    def test_formula(self):
        self.assertEqual(formula(self.choice(), "A1"), "=DOCSO(A1)")
        self.assertEqual(formula(self.choice(options="ngàn linh"), "A1"), '=DOCSO(A1;"ngàn linh")')
        self.assertEqual(formula(self.choice(True), "B2"), "=DOCTIEN(B2)")
        self.assertEqual(formula(self.choice(True, "đồng", "xu"), "B2"), '=DOCTIEN(B2;"đồng";"xu")')
        self.assertEqual(formula(self.choice(True, options="ngàn"), "B2"), '=DOCTIEN(B2;"đồng";"";"ngàn")')
        self.assertEqual(formula(self.choice(True, "dollar", "cent", "en"), "B2"), '=DOCTIEN(B2;"dollar";"cent";"en")')
        self.assertEqual(formula(self.choice(True, "dollar", "cent"), "B2"), '=DOCTIEN(B2;"dollar";"cent")')
        self.assertEqual(formula(self.choice(True, "dollar", "cent", "en"), "B2"), '=DOCTIEN(B2;"dollar";"cent";"en")')
        self.assertEqual(formula(self.choice(True, 'a"b', "", ""), "B2"), '=DOCTIEN(B2;"a""b";"")')

    def test_presets(self):
        self.assertEqual(T.DIALOG["presets"][0], "đồng")
        self.assertEqual(T.PRESETS, (("đồng", ""), ("dollar", "cent")))
        unit, sub = T.PRESETS[0]
        self.assertEqual(formula(self.choice(True, unit, sub), "A1"), "=DOCTIEN(A1)")
        self.assertEqual(words(1000.5, self.choice(True, unit, sub)), "Một nghìn không trăm lẻ một đồng chẵn")
        self.assertEqual(words(1000.5, self.choice(True, *T.PRESETS[1], "en")), "One thousand dollars and fifty cents")

    def test_words_and_errors(self):
        self.assertEqual(words(105.0, self.choice()), "Một trăm lẻ năm")
        self.assertEqual(words("1.000.000", self.choice(True)), "Một triệu đồng chẵn")
        with self.assertRaises(nw.NumberWordsError) as caught:
            words(None, self.choice())
        self.assertIn("Không đọc được số", error_text(caught.exception))
        self.assertIn("15 chữ số", error_text(nw.NumberWordsError("too-many-digits", "x")))


if __name__ == "__main__":
    unittest.main()
