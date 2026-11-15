# SPDX-License-Identifier: AGPL-3.0-only
"""Remaining HST Sheets error values follow the leading spreadsheet application; no OpenCL formula results.

Read from the new side of hst-sheets-error-parity.patch (no LibreOffice tree needed); runtime rows are in
tests/runtime/sheets_formula_cases.py (check-sheets-excel-formula-conventions.py).
"""
import unittest

from test_vi_ui_default import new_side, series

PATCH = "hst-sheets-error-parity.patch"


class SheetsErrorParity(unittest.TestCase):
    def test_in_series_after_num_errors(self):
        names = series()
        self.assertIn(PATCH, names)
        self.assertLess(names.index("hst-sheets-num-errors.patch"), names.index(PATCH))

    def test_opencl_never_computes_formulas(self):
        cxx = new_side(PATCH, "sc/source/core/tool/calcconfig.cxx")
        # isOpenCLEnabled(): only the forced test mode, otherwise false (no UseOpenCL lookup left).
        self.assertRegex(cxx, r"return force == ForceCalculationOpenCL;\n(\s*//[^\n]*\n)+\s*return false;\n}")
        self.assertNotIn('u"UseOpenCL"_ustr', cxx)
        self.assertIn("m_xAllowOpenCL->set_sensitive(false);", new_side(PATCH, "sc/source/ui/optdlg/tpcalc.cxx"))

    def test_prob_weekend_wrap(self):
        self.assertIn("PushNumError();", new_side(PATCH, "sc/source/core/tool/interpr3.cxx"))
        self.assertIn("return FormulaError::IllegalFPOperation;", new_side(PATCH, "sc/source/core/tool/interpr2.cxx"))
        self.assertIn("nWrapCount < 1", new_side(PATCH, "sc/source/core/tool/interpr1.cxx"))

    def test_convert_unknown_unit_is_not_available(self):
        helper = new_side(PATCH, "scaddins/source/analysis/analysishelper.cxx")
        self.assertIn('throw uno::RuntimeException(u"#N/A"_ustr);', helper)
        self.assertEqual(helper.count("ThrowNotAvailable();"), 2)
        self.assertIn("FormulaError::NotAvailable", new_side(PATCH, "sc/source/core/tool/addincol.cxx"))

    def test_pricing_option_words_are_value_errors(self):
        cxx = new_side(PATCH, "scaddins/source/pricing/pricing.cxx")
        self.assertEqual(cxx.count("throw uno::RuntimeException();"), 3)


if __name__ == "__main__":
    unittest.main()
