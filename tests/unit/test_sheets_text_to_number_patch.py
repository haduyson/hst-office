# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets "Chuyển thành số": the patches wire the triangle, the warning button, the command and the option.

Reads hst-sheets-text-to-number.patch (core) and hst-sheets-text-to-number-files.patch (.xlsx/.ods), the series and
the HST extension (Alt+Q words, offline help page). The parsing rules are run by test_sheets_text_number_parse.py.
"""
import os
import re
import unittest

from _paths import ROOT
from test_ribbon_group_button import added, sections

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
CORE = os.path.join(PATCHES, "hst-sheets-text-to-number.patch")
FILES = os.path.join(PATCHES, "hst-sheets-text-to-number-files.patch")
EXT = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
COMMAND = ".uno:HstConvertTextToNumber"
MENU = {"title": "Số được lưu dưới dạng văn bản", "convert": "_Chuyển thành số", "help": "_Trợ giúp về lỗi này",
        "ignore": "_Bỏ qua lỗi", "options": "Tùy chọn _kiểm tra lỗi"}


def po_entries(text):
    """{(msgctxt, msgid): msgstr} of the added .po lines (one-line msgctxt entries)."""
    found = re.findall(r'msgctxt "([^"]*)"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"', text)
    return {(ctx, msgid): msgstr for ctx, msgid, msgstr in found}


class TextToNumberPatchTest(unittest.TestCase):
    def test_series_ends_with_both_patches_in_order(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            names = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertLess(names.index("hst-sheets-text-to-number.patch"),
                        names.index("hst-sheets-text-to-number-files.patch"))

    def test_command_is_a_cell_slot_with_state(self):
        self.assertIn("#define SID_HST_CONVERT_TEXT_TO_NUMBER  (SC_FUNCTION_START + 7)", added(CORE, "sc/inc/sc.hrc"))
        self.assertIn("SfxVoidItem HstConvertTextToNumber SID_HST_CONVERT_TEXT_TO_NUMBER", added(CORE, "sc/sdi/scalc.sdi"))
        self.assertIn("SID_HST_CONVERT_TEXT_TO_NUMBER [ ExecMethod = ExecuteEdit; StateMethod = GetBlockState; ]",
                      added(CORE, "sc/sdi/cellsh.sdi"))
        self.assertIn("sc::hst::ConvertTextNumbers(GetViewData());", added(CORE, "sc/source/ui/view/cellsh1.cxx"))
        self.assertIn("bDisable = !sc::hst::HasTextNumbers(GetViewData());", added(CORE, "sc/source/ui/view/cellsh.cxx"))

    def test_command_is_offered_everywhere(self):
        self.assertIn(f'<menu:menuitem menu:id="{COMMAND}"/>', added(CORE, "sc/uiconfig/scalc/popupmenu/cell.xml"))
        self.assertIn(f'menu:id="{COMMAND}" menu:style="text"', added(CORE, "sc/uiconfig/scalc/menubar/menubar.xml"))
        ribbon = added(CORE, "sc/uiconfig/scalc/ui/notebookbar.ui")
        self.assertIn('id="btnHstConvertTextToNumber"', ribbon)
        self.assertIn('id="MenuData-HstConvertTextToNumber"', ribbon)
        self.assertEqual(ribbon.count(f"<property name=\"action-name\">{COMMAND}</property>"), 2)
        with open(os.path.join(EXT, "FeatureSearch.xcu"), encoding="utf-8") as handle:
            search = handle.read()
        self.assertIn(f"<value>{COMMAND}</value>", search)
        self.assertIn("chuyển thành số", search)

    def test_one_undo_step_and_formats(self):
        convert = added(CORE, "sc/source/ui/view/hsttextnumberconvert.cxx")
        for code in ("pUndoMgr->EnterListAction(aComment, aComment, 0", "pUndoMgr->LeaveListAction();",
                     "rFunc.SetValueCells(", "rFunc.ApplyAttributes(aFormatMark, aPattern, true);",
                     "ScEditableTester::CreateAndTestSelection(rDoc, aMark)",
                     "aFormatMark.SelectTable(rRange.aStart.Tab(), true);"):
            self.assertIn(code, convert)
        core = added(CORE, "sc/source/core/tool/hsttextnumber.cxx")
        self.assertIn("pEntry->GetMaskedType() == SvNumFormatType::TEXT", core)  # Text-formatted cells stay text
        self.assertIn("nFormat % SV_COUNTRY_LANGUAGE_OFFSET == 0", core)  # only General cells get a format
        self.assertIn('" [$₫-42A]"', core)  # the HST VND format (data/hst/number-formats.json)

    def test_triangle_only_for_painted_cells_and_option(self):
        marks = added(CORE, "sc/source/ui/view/hsttextnumbermarks.cxx")
        self.assertIn("pThisRowInfo->cellInfo(nX)", marks)
        self.assertIn("pIgnored->Contains(", marks)
        grid = added(CORE, "sc/source/ui/view/gridwin4.cxx")
        self.assertIn("sc::hst::TextNumberIndicatorEnabled())\n        aOutputData.DrawHstTextNumberMarks", grid)
        schema = added(CORE, "officecfg/registry/schema/org/openoffice/Office/Calc.xcs")
        self.assertIn('<prop oor:name="HstNumberStoredAsText" oor:type="xs:boolean"', schema)
        self.assertIn("<value>true</value>", schema)
        self.assertIn("HstNumberStoredAsText::set(m_xHstTextNumberCB->get_active()",
                      added(CORE, "sc/source/ui/optdlg/tpview.cxx"))
        self.assertIn('u"HstNumberStoredAsText"_ustr', added(CORE, "sc/source/ui/view/tabvwsh4.cxx"))

    def test_button_menu_items_match_the_code(self):
        ui = added(CORE, "sc/uiconfig/scalc/ui/hsttextnumberbutton.ui")
        code = added(CORE, "sc/source/ui/view/hsttextnumberbutton.cxx")
        for ident in MENU:
            self.assertIn(f'<object class="GtkMenuItem" id="{ident}">', ui)
            if ident != "title":
                self.assertIn(f'rIdent == "{ident}"', code)
        self.assertIn('set_item_sensitive(u"title"_ustr, false)', code)
        self.assertIn('"bang-tinh-so-dang-van-ban.html"', code)
        self.assertIn("SfxUInt16Item aPage(SID_OPTIONS_PAGEID, SID_SC_TP_CONTENT)", code)
        self.assertTrue(os.path.isfile(os.path.join(EXT, "help", "bang-tinh-so-dang-van-ban.html")))

    def test_vietnamese_labels(self):
        sc = po_entries(added(CORE, "translations/source/vi/sc/messages.po"))
        for ident, label in MENU.items():
            self.assertIn(label, [v for (ctx, _), v in sc.items() if ctx == f"hsttextnumberbutton|{ident}"])
        self.assertEqual(sc[("STR_HST_UNDO_TEXT_TO_NUMBER", "Convert to Number")], "Chuyển thành số")
        self.assertEqual(sc[("tpviewpage|hsttextnumber", "Number stored as te_xt indicator")],
                         "Đánh dấu _số được lưu dưới dạng văn bản")
        ui = added(CORE, "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po")
        self.assertIn('"..CalcCommands.UserInterface.Commands..uno:HstConvertTextToNumber\\n"', ui)
        self.assertIn('msgstr "Chuyển thành số"', ui)
        # Vietnamese labels end without an ellipsis (owner rule 2026-11-06)
        self.assertFalse([v for v in sc.values() if v.endswith(("...", "…"))])

    def test_no_product_names_of_other_suites_in_user_text(self):
        user_text = "".join(added(CORE, name) for name in sections(CORE) if name.endswith((".po", ".ui", ".xcu", ".hrc")))
        with open(os.path.join(EXT, "help", "bang-tinh-so-dang-van-ban.html"), encoding="utf-8") as handle:
            user_text += handle.read()
        self.assertIsNone(re.search(r"Microsoft|Excel|Office 365|\bMS Office", user_text))

    def test_ignored_cells_are_saved(self):
        imp = added(FILES, "sc/source/filter/oox/worksheetfragment.cxx")
        self.assertIn("case XLS_TOKEN( ignoredErrors ):", imp)
        self.assertIn("rAttribs.getBool( XML_numberStoredAsText, false )", imp)
        exp = added(FILES, "sc/source/filter/excel/excdoc.cxx")
        self.assertIn("XML_numberStoredAsText, \"1\"", exp)
        self.assertIn("new XclExpHstIgnoredErrors( GetRoot(), mnScTab )", exp)
        self.assertIn('SC_UNO_HST_IGNORED_TEXT_NUMBERS = u"HstIgnoredTextNumbers"_ustr', added(FILES, "sc/inc/unonames.hxx"))
        self.assertIn("UpdateReference(rRef.GetMode()", added(CORE, "sc/source/core/tool/hstignoredtextnumbers.cxx"))

    def test_new_widgets_pass_the_accessibility_check(self):
        suppr = added(CORE, "solenv/sanitizers/ui/modules/scalc.suppr")
        for widget in ("hsttextnumberbutton.ui://GtkMenuButton[@id='menubutton']",
                       "notebookbar.ui://GtkMenuItem[@id='MenuData-HstConvertTextToNumber']",
                       "notebookbar.ui://GtkToolButton[@id='btnHstConvertTextToNumber']"):
            self.assertIn(f"sc/uiconfig/scalc/ui/{widget} button-no-label", suppr)

    def test_new_source_files_stay_short(self):
        for name, (lines, _, _) in sections(CORE).items():
            if os.path.basename(name).startswith(("hsttextnumber", "hstignoredtextnumbers")):
                self.assertLessEqual(len(lines), 199, name)


if __name__ == "__main__":
    unittest.main()
