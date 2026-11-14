# SPDX-License-Identifier: AGPL-3.0-only
"""HST Sheets has the worksheet functions of the leading spreadsheet application that the engine lacked.

Read from the patch (new side of each hunk), so no LibreOffice tree is needed
(hst-sheets-excel-functions.patch; C++: CppunitTest_sc_excelcompat_functions_test; runtime:
tests/runtime/check-sheets-excel-functions.py). Every new function has an opcode, a UI name, an .xlsx name with
the _xlfn. prefix of newer functions, an ODF COM.MICROSOFT.* name, a Function Wizard entry whose strings are
translated into Vietnamese, an interpreter dispatch and binary/OOXML filter rows. No user-facing string names
the reference product.
"""
import re
import unittest

from test_vi_ui_default import new_side, series

PATCH = "hst-sheets-excel-functions.patch"
# UI name -> (opcode, .xlsx name)
FUNCTIONS = {
    "ARRAYTOTEXT": ("ocArrayToText", "_xlfn.ARRAYTOTEXT"),
    "VALUETOTEXT": ("ocValueToText", "_xlfn.VALUETOTEXT"),
    "DBCS": ("ocDbcs", "_xlfn.DBCS"),
    "PHONETIC": ("ocPhonetic", "PHONETIC"),
    "PERCENTOF": ("ocPercentOf", "_xlfn.PERCENTOF"),
    "REGEXTEST": ("ocRegexTest", "_xlfn.REGEXTEST"),
    "REGEXEXTRACT": ("ocRegexExtract", "_xlfn.REGEXEXTRACT"),
    "REGEXREPLACE": ("ocRegexReplace", "_xlfn.REGEXREPLACE"),
    "TRIMRANGE": ("ocTrimRange", "_xlfn.TRIMRANGE"),
}
VIETNAMESE = re.compile(r"[ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ]", re.I)


def names():
    """New side of core_resource.hrc: the hunks of the ODFF, OOXML, PODF, API, ENGLISH and native lists."""
    return new_side(PATCH, "formula/inc/core_resource.hrc")


def hrc_blocks():
    text = new_side(PATCH, "sc/inc/scfuncs.hrc")
    return {m.group(1): re.findall(r'NC_\("oc\w+", "((?:[^"\\]|\\.)*)"\)', m.group(2))
            for m in re.finditer(r"const TranslateId oc(\w+)_ARY\[\] =\s*\{(.*?)\};", text, re.S)}


def po_entries():
    text = new_side(PATCH, "translations/source/vi/sc/messages.po")
    return {(c, i): s for c, i, s in re.findall(r'msgctxt "(\w+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"', text)}


class SheetsExcelFunctions(unittest.TestCase):
    def test_patch_is_in_series_after_formula_conventions(self):
        names = series()
        self.assertIn(PATCH, names)
        self.assertGreater(names.index(PATCH), names.index("hst-sheets-excel-formula-conventions.patch"))

    def test_every_function_has_an_opcode_and_dispatch(self):
        opcode = new_side(PATCH, "include/formula/opcode.hxx")
        dispatch = new_side(PATCH, "sc/source/core/tool/interpr4.cxx")
        for name, (op, _) in FUNCTIONS.items():
            with self.subTest(name):
                self.assertRegex(opcode, rf"\b{op}\s*= \d+,")
                self.assertRegex(dispatch, rf"case {op}\s*: Sc\w+\(\);")
        self.assertRegex(opcode, r"ocTrimRange\s*= 529,\s*ocStopTwoParameters = 530,")

    def test_every_function_has_its_names_in_all_six_lists(self):
        text = names()
        for name, (op, xlsx) in FUNCTIONS.items():
            with self.subTest(name):
                self.assertEqual(text.count(f'{{ "COM.MICROSOFT.{name}" , {op} }}'), 1)
                # PODF, API and ENGLISH use the plain name; for PHONETIC that is also the .xlsx name.
                self.assertEqual(text.count(f'{{ "{name}" , {op} }}'), 4 if xlsx == name else 3)
                if xlsx != name:
                    self.assertEqual(text.count(f'{{ "{xlsx}" , {op} }}'), 1)
                self.assertEqual(text.count(f'NC_("RID_STRLIST_FUNCTION_NAMES", "{name}") , {op} }}'), 1)

    def test_binom_dist_range_is_the_ui_and_xlsx_name_of_b(self):
        text = names()
        self.assertIn('{ "_xlfn.BINOM.DIST.RANGE" , ocB }', text)
        self.assertIn('{ "BINOM.DIST.RANGE" , ocB }', text)
        self.assertIn('NC_("RID_STRLIST_FUNCTION_NAMES", "BINOM.DIST.RANGE") , ocB }', text)
        # B stays readable: typed in the UI and in .xlsx files written by earlier versions.
        compiler = new_side(PATCH, "sc/source/core/tool/compiler.cxx")
        self.assertIn('{ "B",              ocB },              // B -> _xlfn.BINOM.DIST.RANGE', compiler)
        self.assertIn('else if (!mxSymbols->isPODF() && rName.equalsIgnoreAsciiCaseAscii("B"))', compiler)

    def test_function_wizard_entries(self):
        funcdesc = new_side(PATCH, "sc/source/core/data/funcdesc.cxx")
        blocks = hrc_blocks()
        for name, (op, _) in FUNCTIONS.items():
            with self.subTest(name):
                self.assertRegex(funcdesc, rf"\{{ {op}, ENTRY\(oc{name}_ARY\), 0, ID_FUNCTION_GRP_\w+, HID_FUNC_{name}_MS, \d,")
                self.assertIn(name, blocks)
                # description + a (name, description) pair per argument
                self.assertEqual(len(blocks[name]) % 2, 1)

    def test_wizard_strings_are_translated_into_vietnamese(self):
        po = po_entries()
        for name, strings in hrc_blocks().items():
            if name not in FUNCTIONS:
                continue
            for msgid in strings:
                with self.subTest(f"{name}: {msgid}"):
                    msgstr = po.get((f"oc{name}", msgid))
                    self.assertTrue(msgstr, "missing Vietnamese translation")
                    self.assertNotEqual(msgstr, msgid)
            self.assertRegex(po[(f"oc{name}", strings[0])], VIETNAMESE)

    def test_no_user_facing_string_names_the_reference_product(self):
        for name, strings in hrc_blocks().items():
            for text in strings + [po_entries().get((f"oc{name}", s), "") for s in strings]:
                self.assertNotRegex(text, r"(?i)excel|microsoft", name)

    def test_filter_tables(self):
        xls = new_side(PATCH, "sc/source/filter/excel/xlformula.cxx")
        oox = new_side(PATCH, "sc/source/filter/oox/formulabase.cxx")
        for name, (op, _) in FUNCTIONS.items():
            with self.subTest(name):
                if name == "PHONETIC":
                    self.assertIn("{ ocPhonetic,           360,", xls)
                    self.assertIn('{ "COM.MICROSOFT.PHONETIC",       "PHONETIC",             360,', oox)
                    continue
                self.assertRegex(xls, rf'EXC_FUNCENTRY_\w+\(\s*{op},.*"{name}" \)')
                self.assertRegex(oox, rf'\{{ "COM.MICROSOFT.{name}",\s+"{name}",.*MACROCALL_NEW')

    def test_errors_reach_the_text_conversions(self):
        interpr4 = new_side(PATCH, "sc/source/core/tool/interpr4.cxx")
        self.assertRegex(interpr4, r"case ocValueToText:.*\n\s*case ocArrayToText:\n\s*return true;")

    def test_trimrange_returns_a_reference(self):
        parclass = new_side(PATCH, "sc/source/core/tool/parclass.cxx")
        self.assertIn("{ ocTrimRange,       {{ ReferenceOrRefArray, Value, Value                    }, 0, Reference }}", parclass)
        compiler = new_side(PATCH, "formula/source/core/api/FormulaCompiler.cxx")
        self.assertEqual(compiler.count("case ocTrimRange:"), 2)

    def test_char_code_use_the_ansi_code_page(self):
        cxx = new_side(PATCH, "sc/source/core/tool/interpr1.cxx")
        self.assertEqual(cxx.count("sc::GetAnsiCodePageEncoding(), convertFlags"), 2)
        self.assertNotIn("osl_getThreadTextEncoding(), convertFlags", cxx)
        page = new_side(PATCH, "sc/source/core/tool/ansicodepage.cxx")
        # Windows: the system default locale's ANSI code page (the process itself runs UTF-8).
        self.assertIn("GetLocaleInfoEx(LOCALE_NAME_SYSTEM_DEFAULT, LOCALE_IDEFAULTANSICODEPAGE", page)
        self.assertIn("utl_getWinTextEncodingFromLangStr(ScGlobal::getLocaleData().getLanguageTag().getBcp47())", page)

    def test_cell_filename_and_info(self):
        cxx = new_side(PATCH, "sc/source/core/tool/interpr1.cxx")
        self.assertIn("osl::FileBase::getSystemPathFromFileURL(aDirURL, aSysPath)", cxx)
        self.assertIn('aFilter.startsWith("calc8")', cxx)
        info = new_side(PATCH, "sc/source/core/tool/interpr5.cxx")
        self.assertIn('PushString( u"pcdos"_ustr );', info)
        self.assertIn('PushString( u"Windows (64-bit) NT 10.00"_ustr );', info)
        self.assertNotIn("Windows (32-bit) NT 5.01", info)

    def test_new_sources_are_built_and_tested(self):
        mk = new_side(PATCH, "sc/Library_sc.mk")
        self.assertIn("sc/source/core/tool/interpr_excelcompat \\", mk)
        self.assertIn("sc/source/core/tool/interpr_excelregex \\", mk)
        self.assertIn("CppunitTest_sc_excelcompat_functions_test", new_side(PATCH, "sc/Module_sc.mk"))
        self.assertIn("sc_functions_test,excelcompat", new_side(PATCH, "sc/CppunitTest_sc_excelcompat_functions_test.mk"))


if __name__ == "__main__":
    unittest.main()
