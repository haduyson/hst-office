# SPDX-License-Identifier: AGPL-3.0-only
"""Numbers follow the Windows (and macOS) regional settings, like the leading spreadsheet application.

Read from the patch itself (the new side of each hunk), so no LibreOffice tree is needed:
- i18npool's locale data of the OS user locale carries the OS decimal, thousands and list
  separator, only while the locale setting is the system default and never on Linux;
- en-US keeps its decimal and thousands separator (the invariant locale of the .xlsx filters);
- the built-in number format codes of that locale follow the separators, date/time codes do not;
- the Sheets formula separators use the leading application's rule under the same condition.
"""
from pathlib import Path
import re
import unittest

from test_vi_ui_default import new_side, series

PATCH = "hst-windows-regional-separators.patch"
LOCALEDATA = "i18npool/source/localedata/localedata.cxx"
FORMULAOPT = "sc/source/core/tool/formulaopt.cxx"
MAKEFILE = "i18npool/Library_i18npool.mk"
PATCHES = Path(__file__).resolve().parents[2] / "patches/libreoffice"


def function(text, signature):
    """Body of the first function whose definition starts with `signature` (brace matched)."""
    start = text.index(signature)
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[start:j + 1]
    raise AssertionError(f"unbalanced {signature}")


class Series(unittest.TestCase):
    def test_patch_is_last_in_the_series(self):
        self.assertEqual(series()[-1], PATCH)

    def test_header(self):
        head = (PATCHES / PATCH).read_text(encoding="utf-8").split("\n---\n", 1)[0]
        self.assertIn("License: these upstream files remain under their original license (MPL-2.0).", head)
        self.assertIn("Test: tests/unit/test_windows_regional_separators.py", head)
        self.assertNotRegex(new_side(PATCH, LOCALEDATA) + new_side(PATCH, FORMULAOPT), r"\b[Pp]hase\b|\bS\d\b")


class LocaleData(unittest.TestCase):
    def setUp(self):
        self.text = new_side(PATCH, LOCALEDATA)
        self.lookup = function(self.text, "std::optional<SystemSeparators> getSystemSeparators(")

    def test_windows_reads_the_user_locale_including_custom_values(self):
        for item in ("LOCALE_SDECIMAL", "LOCALE_STHOUSAND", "LOCALE_SLIST"):
            self.assertIn(item, self.text)
        self.assertIn("GetLocaleInfoEx(LOCALE_NAME_USER_DEFAULT", self.text)

    def test_macos_reads_cflocale_with_list_rule(self):
        self.assertIn("kCFLocaleDecimalSeparator", self.text)
        self.assertIn("kCFLocaleGroupingSeparator", self.text)
        self.assertIn('aSeps.aDecimal == "," ? u";"_ustr : u","_ustr', self.text)
        self.assertIn("ifeq ($(OS),MACOSX)", new_side(PATCH, MAKEFILE))
        self.assertIn("CoreFoundation", new_side(PATCH, MAKEFILE))

    def test_only_default_locale_setting_and_os_user_locale(self):
        self.assertRegex(self.lookup, r"ooSetupSystemLocale::get\(\)\.isEmpty\(\)\)\s*return \{\};")
        self.assertIn("nLang != MsLangId::getSystemLanguage()", self.lookup)
        self.assertRegex(self.lookup, r"catch \(const uno::Exception&\)\s*\{\s*return \{\};")

    def test_linux_keeps_locale_data(self):
        pattern = r"#if defined _WIN32 \|\| defined MACOSX.*#else\s*\(void\)rLocale;\s*return \{\};\s*#endif"
        self.assertRegex(self.lookup, re.compile(pattern, re.S))

    def test_en_us_keeps_decimal_and_thousands(self):
        self.assertRegex(self.lookup, r"if \(nLang == LANGUAGE_ENGLISH_US\)\s*aSeps\.aDecimal\.clear\(\);")
        apply = function(self.text, "template <typename Item> bool applySystemSeparators(")
        # no usable decimal: decimal and thousands both stay with the locale data
        self.assertIn("rSeps.aDecimal.getLength() == 1 && rSeps.aThousand.getLength() == 1", apply)
        self.assertIn("if (aDecimal.isEmpty() || aDecimal == aThousand)\n        return false;", apply)

    def test_both_item_getters_apply_the_override(self):
        apply = r"\s*\};\s*if \(std::optional<SystemSeparators> oSeps = getSystemSeparators\(rLocale\)\)\s*"
        self.assertRegex(self.text, r"dataItem\[17\]" + apply + r"applySystemSeparators\(item, \*oSeps\);")
        self.assertRegex(self.text, r"dataItem\[18\] : OUString\(\)" + apply
                         + r"\{\s*if \(applySystemSeparators\(item, \*oSeps\)")
        self.assertIn("item.decimalSeparatorAlternative.clear();", self.text)

    def test_number_format_codes_follow_dates_do_not(self):
        formats = self.text[self.text.index('"getAllFormats1"'):]
        formats = formats[:formats.index("formatArray[nOff + 1],")]
        self.assertIn("convertNumberFormatCode(aCode, cOldDec, cNewDec, cOldTh, cNewTh)", formats)
        for usage in ("FIXED_NUMBER", "PERCENT_NUMBER", "SCIENTIFIC_NUMBER", "CURRENCY"):
            self.assertIn(f'"{usage}"', formats)
        for usage in ("DATE", "TIME", "DATE_TIME", "FRACTION_NUMBER"):
            self.assertNotIn(f'"{usage}"', formats)
        # thousands/decimal of the raw data: dataItem[0] is unoID, [1] the date separator
        self.assertIn("cOldTh = dataItem[2][0];", formats)
        self.assertIn("cOldDec = dataItem[3][0];", formats)

    def test_code_conversion_skips_quotes_escapes_and_modifiers(self):
        conv = function(self.text, "OUString convertNumberFormatCode(")
        self.assertIn("cEnd = '\"';", conv)
        self.assertIn("cEnd = ']';", conv)
        self.assertIn("(c == '\\\\' || c == '_' || c == '*')", conv)
        self.assertIn("c == cOldTh && bPrevDigit && bNextDigit", conv)


class FormulaSeparators(unittest.TestCase):
    def setUp(self):
        self.text = new_side(PATCH, FORMULAOPT)

    def test_same_condition_as_locale_data(self):
        cond = function(self.text, "bool lcl_UsesSystemSeparators(")
        self.assertIn("ooSetupSystemLocale::get().isEmpty()", cond)
        self.assertIn("LanguageTag(rLocale).getLanguageType() == MsLangId::getSystemLanguage()", cond)
        self.assertRegex(cond, r"#else\s*\(void\)rLocale;\s*return false;\s*#endif")

    def test_leading_application_rule(self):
        block = self.text[self.text.index("    if (bSystemSeparators)"):]
        self.assertIn("rSepArg = OUString(cListSep == cDecSep ? u';' : cListSep);", block)
        # measured with Office 2021 International(xlColumnSeparator): '\\' for de, es, fr, vi; ',' for en-US
        self.assertIn('rSepArrayCol = cDecSep == \',\' ? u"\\\\"_ustr : u","_ustr;', block)
        self.assertIn('rSepArrayRow = ";";\n        return;', block)
        # the rule returns before the LibreOffice heuristics (English ',', de-CH ';')
        self.assertLess(block.index("return;"), block.index("Excel by default uses system's list separator"))
        self.assertIn('if (rLang == "ru" && !bSystemSeparators)', self.text)
        self.assertIn("const bool bSystemSeparators = lcl_UsesSystemSeparators(rLocale);", self.text)

if __name__ == "__main__":
    unittest.main()
