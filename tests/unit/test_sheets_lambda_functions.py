# SPDX-License-Identifier: AGPL-3.0-only
"""HST Sheets has the LAMBDA family, backported from LibreOffice master (hst-sheets-lambda-functions.patch).

Read from the patch, so no LibreOffice tree is needed. C++: CppunitTest_sc_lambda_functions_test (upstream
FunctionsTest documents), runtime: tests/runtime/check-sheets-excel-functions.py.
"""
import re
import unittest

from test_sheets_excel_functions import VIETNAMESE
from test_vi_ui_default import new_side, series

PATCH = "hst-sheets-lambda-functions.patch"
# UI name -> (opcode, wizard resource)
FUNCTIONS = {
    "LAMBDA": ("ocLambda", "ocLAMBDA"), "ISOMITTED": ("ocIsOmitted", "ocIS_OMITTED"),
    "BYCOL": ("ocByCol", "ocBYCOL"), "BYROW": ("ocByRow", "ocBYROW"), "MAKEARRAY": ("ocMakeArray", "ocMAKEARRAY"),
    "MAP": ("ocMap", "ocMAP"), "REDUCE": ("ocReduce", "ocREDUCE"), "SCAN": ("ocScan", "ocSCAN"),
}
EASY = ["ocArrayToText", "ocValueToText", "ocDbcs", "ocPhonetic", "ocPercentOf", "ocRegexTest",
        "ocRegexExtract", "ocRegexReplace", "ocTrimRange"]


def wizard_strings():
    text = new_side(PATCH, "sc/inc/scfuncs.hrc")
    return re.findall(r'NC_\("(oc\w+)", "((?:[^"\\]|\\.)*)"\)', text)


class SheetsLambdaFunctions(unittest.TestCase):
    def test_patch_follows_the_easy_functions(self):
        names = series()
        self.assertGreater(names.index(PATCH), names.index("hst-sheets-excel-functions.patch"))

    def test_upstream_license_is_kept(self):
        text = (new_side(PATCH, "sc/source/core/tool/callable.cxx") + new_side(PATCH, "sc/inc/callable.hxx")
                + new_side(PATCH, "include/formula/callable.hxx"))
        self.assertEqual(text.count("Mozilla Public"), 3)

    def test_names_in_every_list(self):
        names = new_side(PATCH, "formula/inc/core_resource.hrc")
        for name, (op, _) in FUNCTIONS.items():
            with self.subTest(name):
                self.assertIn(f'{{ "COM.MICROSOFT.{name}" , {op} }}', names)
                self.assertIn(f'{{ "_xlfn.{name}" , {op} }}', names)
                self.assertIn(f'NC_("RID_STRLIST_FUNCTION_NAMES", "{name}") , {op} }}', names)
        self.assertIn('{ "_xlop." , ocStringName }', names)

    def test_easy_functions_keep_their_dispatch_and_follow_the_upstream_opcodes(self):
        dispatch = new_side(PATCH, "sc/source/core/tool/interpr4.cxx")
        self.assertIn("void ScInterpreter::DispatchOpCode", dispatch)
        for op in EASY:
            self.assertRegex(dispatch, rf"case {op}\s*: Sc\w+\(\);")
        opcode = new_side(PATCH, "include/formula/opcode.hxx")
        self.assertRegex(opcode, r"ocScan\s*= 526,\s*ocArrayToText\s*= 527,")
        self.assertRegex(opcode, r"ocTrimRange\s*= 535,\s*ocStopTwoParameters = 536,")

    def test_function_wizard_is_vietnamese(self):
        po = dict(((c, i), s) for c, i, s in re.findall(
            r'msgctxt "(\w+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"',
            new_side(PATCH, "translations/source/vi/sc/messages.po")))
        resources = {r for _, r in FUNCTIONS.values()}
        strings = [(c, i) for c, i in wizard_strings() if c in resources]
        self.assertGreater(len(strings), 40)
        for key in strings:
            with self.subTest(key):
                self.assertTrue(po.get(key))
                self.assertNotRegex(po[key], r"(?i)excel|microsoft")
        self.assertRegex(po[("ocLAMBDA", strings[[c for c, _ in strings].index("ocLAMBDA")][1])], VIETNAMESE)
        self.assertTrue(po.get(("STR_LONG_ERR_NOT_FUNC", "Error: Attempted to call non-function")))

    def test_function_tests_are_registered(self):
        self.assertIn("CppunitTest_sc_lambda_functions_test", new_side(PATCH, "sc/Module_sc.mk"))
        self.assertIn("sc/source/core/tool/callable \\", new_side(PATCH, "sc/Library_sc.mk"))
        self.assertIn("formula/source/core/api/callable \\", new_side(PATCH, "formula/Library_for.mk"))


if __name__ == "__main__":
    unittest.main()
