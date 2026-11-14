# SPDX-License-Identifier: AGPL-3.0-only
"""HST Sheets has GROUPBY and PIVOTBY on the LAMBDA callables (hst-sheets-groupby-pivotby.patch).

Read from the patch, so no LibreOffice tree is needed. C++: CppunitTest_sc_excelcompat_functions_test
(testGroupByPivotByAndLambda), runtime: tests/runtime/check-sheets-excel-functions.py.
"""
import re
import unittest

from test_sheets_excel_functions import VIETNAMESE
from test_vi_ui_default import new_side, series

PATCH = "hst-sheets-groupby-pivotby.patch"
FUNCTIONS = {"GROUPBY": ("ocGroupBy", 8), "PIVOTBY": ("ocPivotBy", 11)}


class SheetsGroupByPivotBy(unittest.TestCase):
    def test_patch_follows_the_lambda_family(self):
        names = series()
        self.assertGreater(names.index(PATCH), names.index("hst-sheets-lambda-functions.patch"))

    def test_names_dispatch_and_wizard(self):
        names = new_side(PATCH, "formula/inc/core_resource.hrc")
        dispatch = new_side(PATCH, "sc/source/core/tool/interpr4.cxx")
        funcdesc = new_side(PATCH, "sc/source/core/data/funcdesc.cxx")
        for name, (op, args) in FUNCTIONS.items():
            with self.subTest(name):
                self.assertIn(f'{{ "COM.MICROSOFT.{name}" , {op} }}', names)
                self.assertIn(f'{{ "_xlfn.{name}" , {op} }}', names)
                self.assertRegex(dispatch, rf"case {op}\s*: Sc\w+\(\);")
                self.assertRegex(funcdesc, rf"\{{ {op}, ENTRY\(oc{name}_ARY\), 0, ID_FUNCTION_GRP_TABLE, HID_FUNC_{name}_MS, {args},")
        self.assertIn("sal_uInt8 aOptionalArgs[11];", funcdesc)
        self.assertIn("nMaxParams = 11;", new_side(PATCH, "sc/source/core/inc/parclass.hxx"))

    def test_functions_passed_as_values_use_xleta_in_xlsx(self):
        self.assertIn('rBuffer.append(u"_xleta." + (aName.startsWith(u"_xlfn.") ? aName.copy(6) : aName));',
                      new_side(PATCH, "formula/source/core/api/FormulaCompiler.cxx"))
        self.assertIn('u"_XLFN." + aName.toAsciiUpperCase()', new_side(PATCH, "sc/source/core/tool/compiler.cxx"))

    def test_wizard_text_is_vietnamese(self):
        hrc = re.findall(r'NC_\("(oc(?:GROUPBY|PIVOTBY))", "((?:[^"\\]|\\.)*)"\)', new_side(PATCH, "sc/inc/scfuncs.hrc"))
        self.assertEqual(len(hrc), 17 + 23)
        po = dict(((c, i), s) for c, i, s in re.findall(
            r'msgctxt "(\w+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"',
            new_side(PATCH, "translations/source/vi/sc/messages.po")))
        for key in hrc:
            with self.subTest(key):
                self.assertTrue(po.get(key))
                self.assertNotRegex(po[key] + key[1], r"(?i)excel|microsoft")
        self.assertRegex(po[hrc[0]], VIETNAMESE)


if __name__ == "__main__":
    unittest.main()
