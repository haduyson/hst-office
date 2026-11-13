# SPDX-License-Identifier: AGPL-3.0-only
"""A number outside a function's domain is #NUM! in HST Sheets, text or a wrong type stays #VALUE!.

Read from the new side of hst-sheets-num-errors.patch, so no LibreOffice tree is needed (runtime:
tests/runtime/check-sheets-excel-formula-conventions.py, rows in tests/runtime/sheets_formula_cases.py):
- ScInterpreter::PushNumError() raises FormulaError::IllegalFPOperation, shown and saved as #NUM!;
- domain checks of built-in functions (SQRT, LN, LOG, FACT, distributions, financial functions, ...) use it;
- type checks (VALUE, CHAR, REPT, LEFT, ...) keep PushIllegalArgument(), i.e. #VALUE!;
- an add-in's IllegalArgumentException is #NUM!, the Analysis add-in reports text with a RuntimeException (#VALUE!).
"""
import re
import unittest

from test_vi_ui_default import PATCHES, new_side, series

PATCH = "hst-sheets-num-errors.patch"
TOOL = "sc/source/core/tool/"
# File -> functions whose domain check reports the error with PushNumError() (#NUM!) only.
NUM_FUNCTIONS = {
    "interpr1.cxx": ("ScSqrt", "ScArcCosHyp", "ScArcTanHyp", "ScArcCotHyp", "ScBitAnd", "ScBitLshift", "ScRandbetween"),
    "interpr2.cxx": ("ScLog", "ScLn", "ScLog10", "ScGetDate", "ScGetTime", "ScGetWeekOfYear", "ScDDB", "ScVDB", "ScRate",
                     "ScIpmt", "ScCumIpmt", "ScEffect", "ScNominal", "ScPDuration", "ScRRI", "ScBase", "ScDecimal",
                     "ScRoundSignificant", "ScCeil_MS"),
    "interpr3.cxx": ("ScFact", "ScCombin", "ScPermut", "ScGamma", "ScFisher", "ScNormDist", "ScLogNormDist", "ScBinomDist",
                     "ScNormInv", "ScSNormInv", "ScTInv", "ScChiSqInv", "ScConfidence", "ScPercentile", "ScQuartile",
                     "ScTrimMean", "ScWeibull", "ScPoissonDist", "ScExpDist"),
}
# Type errors: the leading spreadsheet application shows #VALUE! for these as well.
VALUE_FUNCTIONS = {
    "interpr1.cxx": ("ScValue", "ScChar", "ScUnichar", "ScRept", "ScLeft", "ScMid", "ScSubstitute", "ScReplace"),
    "interpr2.cxx": ("ScGetDateValue", "ScGetTimeValue", "ScRoman", "ScArabic"),
}


FUNCTION = re.compile(r"^\w[\w:<>&*, ]* ScInterpreter::(\w+)\(")


def changes(path):
    """{function: [(sign, line)]} for every added/removed line of `path`, by enclosing ScInterpreter function.

    The function comes from the hunk header (git's function context) or a definition inside the hunk."""
    result, inside, function = {}, False, None
    for line in (PATCHES / PATCH).read_text(encoding="utf-8").splitlines():
        if line.startswith("--- "):
            inside = False
        elif line.startswith("+++ "):
            inside = line[4:].strip() == "b/" + path
        elif inside and line.startswith("@@"):
            match = FUNCTION.match(line.split("@@", 2)[2].strip())
            function = match.group(1) if match else None
        elif inside and line[:1] in (" ", "+", "-"):
            match = FUNCTION.match(line[1:])
            if match:
                function = match.group(1)
            if line[:1] != " ":
                result.setdefault(function, []).append((line[:1], line[1:].strip()))
    return result


class SheetsNumErrors(unittest.TestCase):
    def test_patch_is_in_series_after_error_strings(self):
        names = series()
        self.assertIn(PATCH, names)
        self.assertLess(names.index("hst-sheets-excel-formula-conventions.patch"), names.index(PATCH))

    def test_push_num_error_is_the_num_error(self):
        self.assertIn("void PushNumError();", new_side(PATCH, "sc/source/core/inc/interpre.hxx"))
        cxx = new_side(PATCH, TOOL + "interpr4.cxx")
        self.assertRegex(cxx, r"void ScInterpreter::PushNumError\(\)\n\{\n\s+PushError\( FormulaError::IllegalFPOperation\);\n\}")
        self.assertIn("PushError( FormulaError::IllegalArgument);", cxx)  # PushIllegalArgument() is unchanged

    def test_domain_errors_are_num(self):
        for name, functions in NUM_FUNCTIONS.items():
            changed = changes(TOOL + name)
            for function in functions:
                lines = changed.get(function, [])
                self.assertIn(("+", "PushNumError();"), lines, function)
                self.assertNotIn(("+", "PushIllegalArgument();"), lines, function)

    def test_type_errors_stay_value(self):
        for name, functions in VALUE_FUNCTIONS.items():
            changed = changes(TOOL + name)
            for function in functions:
                self.assertFalse([t for sign, t in changed.get(function, []) if sign == "+" and "PushNumError" in t], function)
        # CHAR(0) is #VALUE! there, not a NUL character.
        self.assertIn(("+", "if (fVal < 1.0 || fVal >= 256.0)"), changes(TOOL + "interpr1.cxx")["ScChar"])

    def test_mismatched_arrays_are_na_and_no_spread_is_div0(self):
        changed = changes(TOOL + "interpr3.cxx")
        for function in ("ScTTest", "ScChiTest", "CalculatePearsonCovar", "CalculateSlopeIntercept", "ScForecast"):
            self.assertIn(("+", "PushNA();   // arrays of different size: #N/A as in the leading application"),
                          changed[function], function)
        self.assertTrue(any("DivisionByZero" in text for sign, text in changed["CalculateSkewOrSkewp"] if sign == "+"))
        self.assertTrue(any("DivisionByZero" in text for sign, text in changes(TOOL + "interpr2.cxx")["ScFloor_MS"]
                            if sign == "+"))

    def test_add_in_argument_errors_are_num(self):
        cxx = new_side(PATCH, TOOL + "addincol.cxx")
        self.assertRegex(cxx, r"IllegalArgumentException>::get\(\)\) \)\n\s+nErrCode = FormulaError::IllegalFPOperation;")

    def test_analysis_text_arguments_stay_value(self):
        hxx = new_side(PATCH, "scaddins/source/analysis/analysishelper.hxx")
        self.assertIn("[[noreturn]] void ThrowNoValue();", hxx)
        helper = new_side(PATCH, "scaddins/source/analysis/analysishelper.cxx")
        self.assertRegex(helper, r"void ThrowNoValue\(\)\n\{\n\s+throw uno::RuntimeException\(\);")
        text = (PATCHES / PATCH).read_text(encoding="utf-8")
        # Text in a number list, a wrong value type, a COMPLEX suffix, CONVERT units: 10 sites, nothing else.
        self.assertEqual(len(re.findall(r"(?m)^\+\s+ThrowNoValue\(\);", text)), 10)
        self.assertEqual(len(re.findall(r"(?m)^-\s+throw lang::IllegalArgumentException\(\);", text)), 10)
        self.assertIn("ThrowNoValue();", new_side(PATCH, "scaddins/source/analysis/analysis.cxx"))
        convert = re.search(r"if\( \(eStatus != rtl_math_ConversionStatus_Ok\) [^\n]*\n\s+(\S+)", helper)
        self.assertEqual(convert.group(1), "ThrowNoValue();")

    def test_no_plan_ids_in_code(self):
        text = (new_side(PATCH, TOOL + "interpr3.cxx") + new_side(PATCH, TOOL + "addincol.cxx"))
        self.assertNotRegex(text, r"\b(phase|plan)[- ]?\d")
        self.assertNotIn("Microsoft", text)


if __name__ == "__main__":
    unittest.main()
