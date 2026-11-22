# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST Sheets reads LAMBDA/LET parameter lists typed with ';' under a ',' separator, and a typed optional
parameter [b] stays optional in .xlsx and .ods (hst-sheets-lambda-parameter-parsing.patch).

Read from the patch, so no LibreOffice tree is needed. C++: CppunitTest_sc_excelcompat_functions_test
(testGroupByPivotByAndLambda), runtime: tests/runtime/check-sheets-excel-functions.py.
"""
import unittest

from test_vi_ui_default import new_side, series

PATCH = "hst-sheets-lambda-parameter-parsing.patch"
COMPILER = "sc/source/core/tool/compiler.cxx"


class SheetsLambdaParameterParsing(unittest.TestCase):
    def test_patch_follows_the_lambda_patches(self):
        names = series()
        self.assertGreater(names.index(PATCH), names.index("hst-sheets-groupby-pivotby.patch"))

    def test_parameter_count_takes_semicolon_and_stops_at_the_close(self):
        src = new_side(PATCH, COMPILER)
        self.assertIn("(c == cSep || (bSemicolonIsSep && c == ';'))", src)
        self.assertIn("if (--nBrackets <= 0)", src)
        self.assertIn("bInString = !bInString;", src)

    def test_typed_optional_parameter_marks_the_name_token(self):
        src = new_side(PATCH, COMPILER)
        self.assertIn("bLambdaOptionalParam = (eOp == ocTableRefOpen);", src)
        self.assertIn("(mbOptionalLocalName || bLambdaOptionalParam)", src)
        writer = new_side(PATCH, "formula/source/core/api/FormulaCompiler.cxx")
        self.assertIn("FormulaGrammar::isOOXML(meGrammar) || FormulaGrammar::isODFF(meGrammar)", writer)

    def test_cppunit_checks_the_xlsx_text(self):
        test = new_side(PATCH, "sc/qa/unit/functions_excelcompat.cxx")
        self.assertIn("_xlfn.LAMBDA(_xlpm.a,_xlop.b,", test)
        self.assertIn('"=LAMBDA(p;q;p+q)(1;2)", "3"', test)


if __name__ == "__main__":
    unittest.main()
