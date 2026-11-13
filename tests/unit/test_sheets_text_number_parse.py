# SPDX-License-Identifier: AGPL-3.0-only
"""Rules of "Chuyển thành số": which texts are numbers stored as text (sc/inc/hsttextnumberparse.hxx).

The header has no LibreOffice dependencies; it is taken from hst-sheets-text-to-number.patch and compiled with a
small driver (skipped without a C++ compiler). Each row: text, locale, then the number the cell gets (the ASCII
form read with '.' as decimal separator; None = stays text), kind, VND?, grouped?, decimals.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_ribbon_group_button import added

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-sheets-text-to-number.patch")
HEADER = "sc/inc/hsttextnumberparse.hxx"
VI, EN = (",", ".", "₫"), (".", ",", "$")

CASES = [
    # Vietnamese: "." groups thousands, "," is the decimal separator
    ("1234", VI, "1234", "plain", 0, 0, 0),
    ("1.234", VI, "1234", "plain", 0, 1, 0),
    ("1.234.567", VI, "1234567", "plain", 0, 1, 0),
    ("1.234.567,89", VI, "1234567.89", "plain", 0, 1, 2),
    ("0,5", VI, "0.5", "plain", 0, 0, 1),
    (",5", VI, "0.5", "plain", 0, 0, 1),
    ("12,34", VI, "12.34", "plain", 0, 0, 2),
    ("1,234", VI, "1.234", "plain", 0, 0, 3),
    ("15%", VI, "15E-2", "percent", 0, 0, 0),
    ("12,5 %", VI, "12.5E-2", "percent", 0, 0, 1),
    ("-15%", VI, "-15E-2", "percent", 0, 0, 0),
    ("1.000.000 đ", VI, "1000000", "currency", 1, 1, 0),
    ("1.000.000đ", VI, "1000000", "currency", 1, 1, 0),
    ("1.000.000 ₫", VI, "1000000", "currency", 1, 1, 0),
    ("1.000.000 VND", VI, "1000000", "currency", 1, 1, 0),
    ("1.000.000 vnđ", VI, "1000000", "currency", 1, 1, 0),
    ("VND 1.000.000", VI, "1000000", "currency", 1, 1, 0),
    ("500.000 đồng", VI, "500000", "currency", 1, 1, 0),
    ("-1.000 đ", VI, "-1000", "currency", 1, 1, 0),
    ("(1.000)", VI, "-1000", "plain", 0, 1, 0),
    ("(1.000 đ)", VI, "-1000", "currency", 1, 1, 0),
    ("1.234-", VI, "-1234", "plain", 0, 1, 0),
    ("−42", VI, "-42", "plain", 0, 0, 0),
    ("+5", VI, "5", "plain", 0, 0, 0),
    ("  1.234  ", VI, "1234", "plain", 0, 1, 0),
    ("1 234 567", VI, "1234567", "plain", 0, 1, 0),
    ("1 234 567,5", VI, "1234567.5", "plain", 0, 1, 1),
    ("1 234", VI, "1234", "plain", 0, 1, 0),
    ("１２３４", VI, "1234", "plain", 0, 0, 0),
    ("１．２３４", VI, "1234", "plain", 0, 1, 0),
    ("0", VI, "0", "plain", 0, 0, 0),
    ("-0", VI, "0", "plain", 0, 0, 0),
    ("2026", VI, "2026", "plain", 0, 0, 0),
    ("123456789012345", VI, "123456789012345", "plain", 0, 0, 0),
    # English: "," groups thousands, "." is the decimal separator
    ("1.234", EN, "1.234", "plain", 0, 0, 3),
    ("1,234,567.89", EN, "1234567.89", "plain", 0, 1, 2),
    ("$1,234.50", EN, "1234.50", "currency", 0, 1, 2),
    ("(1,000)", EN, "-1000", "plain", 0, 1, 0),
    ("3.5%", EN, "3.5E-2", "percent", 0, 0, 1),
    ("1.000.000 VND", EN, None, None, 0, 0, 0),
    # not numbers: wrong separators for the locale, codes, dates and words
    ("1,234,567.89", VI, None, None, 0, 0, 0),
    ("3.14", VI, None, None, 0, 0, 0),
    ("12.34", VI, None, None, 0, 0, 0),
    ("1.2345", VI, None, None, 0, 0, 0),
    ("1.234 567", VI, None, None, 0, 0, 0),
    ("12 34", VI, None, None, 0, 0, 0),
    ("0905123456", VI, None, None, 0, 0, 0),
    ("0905 123 456", VI, None, None, 0, 0, 0),
    ("007", VI, None, None, 0, 0, 0),
    ("001203004567", VI, None, None, 0, 0, 0),
    ("+84905123456", VI, None, None, 0, 0, 0),
    ("+84 905 123 456", VI, None, None, 0, 0, 0),
    ("1234567890123456", VI, None, None, 0, 0, 0),
    ("13/11/2026", VI, None, None, 0, 0, 0),
    ("13.11.2026", VI, None, None, 0, 0, 0),
    ("12:30", VI, None, None, 0, 0, 0),
    ("1E5", VI, None, None, 0, 0, 0),
    ("15% đ", VI, None, None, 0, 0, 0),
    ("-(1.000)", VI, None, None, 0, 0, 0),
    ("--5", VI, None, None, 0, 0, 0),
    ("-5-", VI, None, None, 0, 0, 0),
    ("5+", VI, None, None, 0, 0, 0),
    ("$1.000", VI, None, None, 0, 0, 0),
    ("đ", VI, None, None, 0, 0, 0),
    (",", VI, None, None, 0, 0, 0),
    ("", VI, None, None, 0, 0, 0),
    ("abc", VI, None, None, 0, 0, 0),
    ("A1", VI, None, None, 0, 0, 0),
    ("1" * 70, VI, None, None, 0, 0, 0),
]

DRIVER = r"""
#include "hsttextnumberparse.hxx"
#include <cstdio>
#include <iostream>
#include <string>
static std::u16string utf16(const std::string& s)
{
    std::u16string r;
    for (size_t i = 0; i < s.size();)
    {
        unsigned char c = s[i];
        int n = c < 0x80 ? 1 : c < 0xE0 ? 2 : 3;
        char32_t v = n == 1 ? c : n == 2 ? (c & 0x1F) : (c & 0x0F);
        for (int k = 1; k < n; ++k)
            v = (v << 6) | (s[i + k] & 0x3F);
        r += static_cast<char16_t>(v);
        i += n;
    }
    return r;
}
int main()
{
    std::string sDec, sGroup, sCurrency, sText;
    while (std::getline(std::cin, sDec) && std::getline(std::cin, sGroup) && std::getline(std::cin, sCurrency)
           && std::getline(std::cin, sText))
    {
        const std::u16string aCurrency = utf16(sCurrency);
        hst::textnumber::Separators aSep{ utf16(sDec)[0], utf16(sGroup)[0], aCurrency };
        const auto a = hst::textnumber::parse(utf16(sText), aSep);
        if (!a)
            std::printf("None\n");
        else
            std::printf("%s %d %d %d %d\n", a->aNumber.c_str(), static_cast<int>(a->eKind), a->bVnd ? 1 : 0,
                        a->bGrouped ? 1 : 0, a->nDecimals);
    }
}
"""
KINDS = {"plain": 0, "percent": 1, "currency": 2}


class TextNumberParseTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_vietnamese_and_english_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hsttextnumberparse.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added(PATCH, HEADER))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe,
                                    os.path.join(tmp, "driver.cxx")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            feed = "".join(f"{dec}\n{group}\n{currency}\n{text}\n" for text, (dec, group, currency), *_ in CASES)
            run = subprocess.run([exe], input=feed, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            lines = run.stdout.splitlines()
        self.assertEqual(len(lines), len(CASES))
        for (text, locale, number, kind, vnd, grouped, decimals), line in zip(CASES, lines):
            want = "None" if number is None else f"{number} {KINDS[kind]} {vnd} {grouped} {decimals}"
            self.assertEqual(line, want, (text, locale))

    def test_rules_are_documented_in_the_header(self):
        header = added(PATCH, HEADER)
        for rule in ('"1.234" is 1234 in vi-VN and 1.234 in en-US', "leading zeros", "15 significant digits"):
            self.assertIn(rule, header)


if __name__ == "__main__":
    unittest.main()
