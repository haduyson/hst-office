# SPDX-License-Identifier: AGPL-3.0-only
"""HST Sheets formulas follow the leading spreadsheet application's conventions in every UI language.

Read from the patch (the new side of each hunk) and the Vietnamese l10n data, so no LibreOffice tree is
needed (hst-sheets-excel-formula-conventions.patch; runtime: tests/runtime/check-sheets-excel-formula-conventions.py):
- Excel A1 is the default formula syntax, a plain schema default the profile can override;
- the vi_VN locale's boolean words are true/false, so cells show TRUE/FALSE and =TRUE parses;
- TRUE/FALSE parse as boolean constants in every locale, error cells never show "Err:5xx";
- CEILING/FLOOR in the UI are the .xlsx functions, the OpenDocument variants are CEILING.ODF/FLOOR.ODF;
- no Vietnamese translation localizes a function name (built-in or add-in), so the vi UI shows the
  English names users type in the leading application.
"""
import json
import re
import tarfile
import unittest
from pathlib import Path

from test_vi_ui_default import new_side, series

ROOT = Path(__file__).resolve().parents[2]
PATCH = "hst-sheets-excel-formula-conventions.patch"
TARBALL = Path("/home/office/upstream/cache/libreoffice/libreoffice-translations-26.8.1.1.tar.xz")
# Contexts of function names: built-in (formula), Analysis/DateFunc/Pricing add-ins (scaddins).
NAME_CONTEXT = re.compile(r"^(RID_STRLIST_FUNCTION_NAMES|[A-Z]+_FUNCNAME_\w+)$")


def l10n_rows():
    files = sorted((ROOT / "l10n/vi").glob("*.jsonl")) + [ROOT / "l10n/vi-overrides.jsonl"]
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield path.name, json.loads(line)


class SheetsExcelFormulaConventions(unittest.TestCase):
    def test_patch_is_in_series(self):
        self.assertIn(PATCH, series())

    def test_excel_a1_is_the_default_syntax(self):
        xcs = new_side(PATCH, "officecfg/registry/schema/org/openoffice/Office/Calc.xcs")
        # Grammar is the enumerated property right before EnglishFunctionName (Calc.xcs Formula/Syntax).
        self.assertRegex(xcs, r"</enumeration>\s*</constraints>\s*<value>1</value>\s*</prop>"
                              r'\s*<prop oor:name="EnglishFunctionName"')
        self.assertNotIn("finalized", xcs)

    def test_vietnamese_locale_booleans_are_true_false(self):
        xml = new_side(PATCH, "i18npool/source/localedata/data/vi_VN.xml")
        self.assertIn("<trueWord>true</trueWord>", xml)
        self.assertIn("<falseWord>false</falseWord>", xml)

    def test_vietnamese_short_date_has_four_digit_year(self):
        xml = new_side(PATCH, "i18npool/source/localedata/data/vi_VN.xml")
        self.assertRegex(xml, r'formatindex="18">\s*<FormatCode>DD/MM/YYYY</FormatCode>')
        self.assertIn('default="true" type="medium" usage="DATE" formatindex="21">', xml)
        self.assertIn('default="false" type="medium" usage="DATE" formatindex="20">', xml)

    def test_true_false_parse_in_every_locale(self):
        cxx = new_side(PATCH, "sc/source/core/tool/compiler.cxx")
        self.assertIn('rSym.equalsIgnoreAsciiCase("TRUE")', cxx)
        self.assertIn('rSym.equalsIgnoreAsciiCase("FALSE")', cxx)

    def test_error_cells_show_leading_application_values(self):
        cxx = new_side(PATCH, "sc/source/core/data/global.cxx")
        body = cxx.split("OUString ScGlobal::GetErrorString", 1)[1].split("OUString ScGlobal::GetLongErrorString", 1)[0]
        self.assertNotIn("STR_ERROR_STR", body)
        self.assertNotIn("STR_NO_ADDIN", body)
        self.assertIn("GetNativeSymbol(ocErrValue)", body)

    def test_ceiling_floor_ui_names(self):
        hrc = new_side(PATCH, "formula/inc/core_resource.hrc")
        for name in ("CEILING", "FLOOR"):
            op = "ocCeil" if name == "CEILING" else "ocFloor"
            self.assertIn(f'NC_("RID_STRLIST_FUNCTION_NAMES", "{name}") , {op}_MS', hrc)
            self.assertIn(f'NC_("RID_STRLIST_FUNCTION_NAMES", "{name}.ODF") , {op} ', hrc)
            self.assertIn(f'{{ "{name}" , {op}_MS }}', hrc)  # English function names list
            self.assertNotIn(f"{name}.XCL", hrc)

    def test_xlsx_names_for_renamed_functions(self):
        hrc = new_side(PATCH, "formula/inc/core_resource.hrc")
        for name, op in (("FORMULATEXT", "ocFormula"), ("SKEW.P", "ocSkewp"), ("FORECAST.ETS", "ocForecast_ETS_ADD"),
                         ("FORECAST.ETS.CONFINT", "ocForecast_ETS_PIA"), ("FORECAST.ETS.STAT", "ocForecast_ETS_STA")):
            self.assertIn(f'NC_("RID_STRLIST_FUNCTION_NAMES", "{name}") , {op} }}', hrc)
            self.assertIn(f'{{ "{name}" , {op} }}', hrc)

    def test_xlsx_export_skips_uncompiled_formulas(self):
        cxx = new_side(PATCH, "sc/source/filter/excel/xetable.cxx")
        self.assertIn("bool bValid = aTokenArray.GetCodeError() == FormulaError::NONE;", cxx)

    def test_ceiling_floor_help_does_not_name_a_product(self):
        for ctx in ("ocCEIL_MS", "ocFLOOR_MS"):
            rows = [r for _, r in l10n_rows() if r["msgctxt"] == ctx and r["msgid"].startswith("Round")]
            self.assertTrue(rows, ctx)
            for row in rows:
                self.assertNotIn("Microsoft", row["msgid"] + row["msgstr"])

    def test_hst_l10n_keeps_function_names_english(self):
        for source, row in l10n_rows():
            if NAME_CONTEXT.match(row["msgctxt"]):
                self.assertEqual(row["msgstr"], row.get("msgid_new") or row["msgid"], f"{source}: {row}")

    @unittest.skipUnless(TARBALL.is_file(), "pinned translations tarball not cached here")
    def test_upstream_vi_keeps_function_names_english(self):
        with tarfile.open(TARBALL) as tar:
            for member in ("formula/messages.po", "scaddins/messages.po"):
                text = tar.extractfile(f"libreoffice-26.8.1.1/translations/source/vi/{member}").read().decode("utf-8")
                for ctx, msgid, msgstr in re.findall(r'msgctxt "([^"]*)"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"', text):
                    if NAME_CONTEXT.match(ctx) and msgstr:
                        self.assertEqual(msgstr, msgid, f"{member} {ctx}")


if __name__ == "__main__":
    unittest.main()
