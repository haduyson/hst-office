# SPDX-License-Identifier: AGPL-3.0-only
"""The warning before a Sheets document with HST functions is saved as .xlsx/.xls: rules, remembered answer, the
answer given to the core save code, and that the open document is only read."""
import os
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import _paths  # noqa: F401

from hst_office import save_format_check as check_module
from hst_office import save_format_dialog as dialog
from hst_office import save_format_prefs as prefs
from hst_office import save_format_rules as rules
from hst_office import utilities_texts as T
from hst_office.vietnamese_calc_logic import FUNCTION_NAMES

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
PATCHES = os.path.join(_paths.ROOT, "patches", "libreoffice")
OOR = "{http://openoffice.org/2001/registry}"
DLG = "{http://openoffice.org/2000/dialog}"
XLSX = "Calc MS Excel 2007 XML"


class Rules(unittest.TestCase):
    def test_value_functions_are_the_addin_methods(self):
        root = ET.parse(os.path.join(EXT, "CalcAddIns.xcu")).getroot()
        addin = next(n for n in root.iter("node") if n.get(OOR + "name") == rules.ADDIN)
        methods = {n.get(OOR + "name") for n in addin.find("node").findall("node")}
        self.assertEqual({name.rsplit(".", 1)[1] for name in rules.value_functions()}, methods)
        self.assertEqual(len(rules.value_functions()), len(FUNCTION_NAMES))
        self.assertIn("org.hst.office.vi.CalcFunctions.docso", rules.value_functions())

    def test_file_extension(self):
        cases = {XLSX: ".xlsx", "Calc Office Open XML": ".xlsx", "Calc MS Excel 2007 VBA XML": ".xlsm",
                 "Calc MS Excel 2007 XML Template": ".xltx", "MS Excel 97": ".xls", "MS Excel 97 Vorlage/Template": ".xlt",
                 "MS Excel 95": ".xls", None: ".xls"}
        for name, ext in cases.items():
            self.assertEqual(rules.file_extension(name), ext, name)

    def test_remembered_and_to_remember(self):
        self.assertEqual([rules.remembered(v) for v in ("convert", "keep", "", "cancel", "junk", None)],
                         ["convert", "keep", "", "", "", ""])
        self.assertEqual(rules.to_remember(rules.CONVERT, True), rules.CONVERT)
        self.assertEqual(rules.to_remember(rules.KEEP, True), rules.KEEP)
        self.assertIsNone(rules.to_remember(rules.CONVERT, False))
        self.assertIsNone(rules.to_remember(rules.CANCEL, True))  # Hủy would block every later save

    def test_answer(self):
        self.assertIs(rules.answer(rules.CANCEL), False)
        self.assertIs(rules.answer(rules.KEEP), True)
        self.assertEqual(dict(rules.answer(rules.CONVERT)), {"Proceed": True, "ValueFunctions": rules.value_functions()})


def fake_doc(formulas_per_sheet, spreadsheet=True):
    """A read-only stand-in: any attempt to change a cell or the document fails the test (no such attribute)."""
    def blocks(rows):
        block = mock.Mock(spec=["getFormulaArray"])
        block.getFormulaArray.return_value = rows
        ranges = mock.Mock(spec=["getCount", "getByIndex"])
        ranges.getCount.return_value = 1
        ranges.getByIndex.return_value = block
        return ranges
    sheets_list = []
    for rows in formulas_per_sheet:
        sheet = mock.Mock(spec=["queryContentCells"])
        sheet.queryContentCells.return_value = blocks(rows)
        sheets_list.append(sheet)
    sheets = mock.Mock(spec=["getCount", "getByIndex"])
    sheets.getCount.return_value = len(sheets_list)
    sheets.getByIndex.side_effect = sheets_list.__getitem__
    doc = mock.Mock(spec=["supportsService", "getSheets"])
    doc.supportsService.return_value = spreadsheet
    doc.getSheets.return_value = sheets
    return doc


class Check(unittest.TestCase):
    DOC = [[("=ORG.HST.OFFICE.VI.CALCFUNCTIONS.DOCSO(105)", "=SUM(A1:A2)")], [("=bodau(B1)", "=TACHTEN(C1)")]]

    def run_check(self, remembered, asked=None, filter_name=XLSX, doc=None):
        store = mock.Mock(spec=["load", "save"])
        store.load.return_value = remembered
        ask = mock.Mock(return_value=asked)
        result = check_module.check(None, doc or fake_doc(self.DOC), filter_name, ask=ask, prefs=store)
        return result, ask, store

    def test_find_functions(self):
        self.assertEqual(check_module.find_functions(fake_doc(self.DOC)), (["DOCSO", "BODAU", "TACHTEN"], 3))

    def test_other_formats_and_documents_are_not_checked(self):
        for filter_name, doc in (("calc8", None), ("", None), (XLSX, fake_doc(self.DOC, spreadsheet=False)),
                                 (XLSX, fake_doc([[("=SUM(1)",)]]))):
            result, ask, store = self.run_check(rules.ASK, filter_name=filter_name, doc=doc)
            self.assertIs(result, True)
            ask.assert_not_called()
            store.save.assert_not_called()
        self.assertIs(check_module.check(None, None, XLSX), True)

    def test_convert_without_remembering(self):
        result, ask, store = self.run_check(rules.ASK, (rules.CONVERT, False))
        self.assertEqual(dict(result)["ValueFunctions"], rules.value_functions())
        ask.assert_called_once_with(None, mock.ANY, ["DOCSO", "BODAU", "TACHTEN"], 3, ".xlsx")
        store.save.assert_not_called()

    def test_dont_ask_remembers_convert_or_keep_only(self):
        for choice, expected in ((rules.KEEP, True), (rules.CONVERT, rules.answer(rules.CONVERT))):
            result, _, store = self.run_check(rules.ASK, (choice, True), filter_name="MS Excel 97")
            self.assertEqual(result, expected)
            store.save.assert_called_once_with(None, choice)
        result, _, store = self.run_check(rules.ASK, (rules.CANCEL, True))
        self.assertIs(result, False)
        store.save.assert_not_called()

    def test_remembered_choice_is_used_without_asking(self):
        for remembered, expected in ((rules.CONVERT, rules.answer(rules.CONVERT)), (rules.KEEP, True)):
            result, ask, store = self.run_check(remembered)
            self.assertEqual(result, expected)
            ask.assert_not_called()
            store.save.assert_not_called()

    def test_service_answers_named_values_and_never_blocks(self):
        import uno  # noqa: F401 - the service module needs the UNO runtime types
        values = check_module.to_uno(rules.answer(rules.CONVERT))
        self.assertEqual([(v.Name, v.Value) for v in values],
                         [("Proceed", True), ("ValueFunctions", rules.value_functions())])
        self.assertIs(check_module.to_uno(False), False)
        service = check_module.SaveFormatCheck(None)
        with mock.patch.object(check_module, "check", side_effect=RuntimeError("broken")), \
                mock.patch.object(check_module.diag_log, "exception"):
            self.assertIs(service.execute(()), True)


class Prefs(unittest.TestCase):
    def test_load_and_save(self):
        node = mock.Mock()
        node.getPropertyValue.return_value = "keep"
        with mock.patch.object(prefs, "_access", return_value=node):
            self.assertEqual(prefs.load(None), rules.KEEP)
            self.assertTrue(prefs.save(None, rules.ASK))
            self.assertFalse(prefs.save(None, rules.CANCEL))
        node.setPropertyValue.assert_called_once_with(prefs.KEY, "")
        node.commitChanges.assert_called_once()

    def test_unreadable_profile_asks(self):
        with mock.patch.object(prefs, "_access", side_effect=RuntimeError("no schema")), \
                mock.patch.object(prefs.diag_log, "exception"):
            self.assertEqual(prefs.load(None), rules.ASK)
            self.assertFalse(prefs.save(None, rules.CONVERT))

    def test_page_positions(self):
        self.assertEqual(len(T.SAVE_OPTIONS), len(prefs.PAGE_ORDER))
        self.assertEqual([prefs.page_index(c) for c in ("", "convert", "keep", "junk")], [0, 1, 2, 0])
        self.assertEqual([prefs.from_page_index(i) for i in (0, 1, 2, -1, 9)], ["", "convert", "keep", "", ""])

    def test_schema_page_and_manifest(self):
        root = ET.parse(os.path.join(EXT, "saveformatcheck.xcs")).getroot()
        self.assertEqual("/%s.%s" % (root.get(OOR + "package"), root.get(OOR + "name")), prefs.CONFIG_PATH)
        self.assertEqual({p.get(OOR + "name"): p.findtext("value") or "" for p in root.iter("prop")}, {prefs.KEY: ""})
        with open(os.path.join(EXT, "META-INF", "manifest.xml"), encoding="utf-8") as manifest:
            self.assertIn('full-path="saveformatcheck.xcs"', manifest.read())
        ids = {e.get(DLG + "id") for e in ET.parse(os.path.join(EXT, "dialogs", "NumberWords.xdl")).getroot().iter()}
        self.assertIn("save_choice", ids)


class TextsAndCore(unittest.TestCase):
    def test_texts_name_no_other_vendor_product(self):
        text = " ".join([T.SAVE_TITLE, T.SAVE_TEXT, T.SAVE_DONT_ASK, *T.SAVE_BUTTONS, *T.SAVE_OPTIONS])
        for word in ("Microsoft", "Excel", "Office 365"):
            self.assertNotIn(word, text)
        self.assertEqual(T.SAVE_BUTTONS, ("Chuyển thành giá trị khi lưu", "Vẫn lưu", "Hủy"))
        self.assertIn(".xlsx", T.SAVE_TEXT % ("DOCSO", ".xlsx", 2))
        self.assertEqual(T.SAVE_TITLE % ".xls", "Lưu sang định dạng .xls")

    def test_dialog_buttons_fit(self):
        used = sum(dialog.BUTTON_WIDTHS) + dialog.GAP * (len(dialog.BUTTON_WIDTHS) - 1) + 2 * dialog.MARGIN
        self.assertLessEqual(used, dialog.WIDTH)

    def test_core_patch_reads_this_answer(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertLess(series.index("hst-save-format-check.patch"), series.index("hst-save-hst-functions-as-values.patch"))
        with open(os.path.join(PATCHES, "hst-save-hst-functions-as-values.patch"), encoding="utf-8") as handle:
            patch = handle.read()
        for name in ('u"Proceed"_ustr', 'u"ValueFunctions"_ustr', "sfx2::GetHstValueFunctions", "equalsIgnoreAsciiCase"):
            self.assertIn(name, patch)
        self.assertIn("License: these upstream files remain under their original license (MPL-2.0).", patch)


if __name__ == "__main__":
    unittest.main()
