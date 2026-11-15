# SPDX-License-Identifier: AGPL-3.0-only
"""Print scaling of HST Sheets (hst-sheets-print-scaling.patch; the ribbon places it in hst-ribbon-ux-calc.patch), read
from the patches.

The print dialog list, the commands with their menu, toolbar and ribbon places, the mapping onto the page style
scale items that .xlsx/.ods store, the Vietnamese strings, the Alt+Q words and the help page.
"""
import glob
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
MAIN = os.path.join(PATCHES, "hst-sheets-print-scaling.patch")
RIBBON = os.path.join(PATCHES, "hst-ribbon-ux-calc.patch")  # the ribbon rework places .uno:PrintScaleMenu
EXTENSION = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
COMMANDS = ("PrintScaleMenu", "PrintScaleNone", "PrintScaleFitSheet", "PrintScaleFitColumns", "PrintScaleFitRows",
            "PrintScaleOptions")
SLOTS = ("SID_PRINTSCALE_NONE", "SID_PRINTSCALE_FIT_SHEET", "SID_PRINTSCALE_FIT_COLUMNS", "SID_PRINTSCALE_FIT_ROWS",
         "SID_PRINTSCALE_OPTIONS", "SID_PRINTSCALE_MENU")
# the owner's wording of the choices (Vietnamese UI)
VI_CHOICES = ("Không thu phóng (in kích thước thật)", "Vừa trang tính trên một trang",
              "Vừa tất cả các cột trên một trang", "Vừa tất cả các hàng trên một trang")


def added(patch):
    """Added lines per target file of a patch."""
    result, current = {}, None
    with open(patch, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None and line.startswith("+"):
                current.append(line[1:])
    return {name: "\n".join(lines) for name, lines in result.items()}


def po_entries(text):
    """msgid -> msgstr of the added po entries (single-line ids)."""
    return dict(re.findall(r'^msgid "(.*)"\nmsgstr "(.*)"$', text, re.M))


class PrintScalingPatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = added(MAIN)
        cls.ribbon = added(RIBBON)

    def test_patches_are_in_the_series(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertIn("hst-sheets-print-scaling.patch", series)
        self.assertIn("hst-ribbon-ux-calc.patch", series)
        # one ribbon owner: a second notebookbar.ui patch would place the drop-down twice
        self.assertNotIn("hst-sheets-print-scaling-ribbon.patch", series)

    def test_slots_are_declared_once_and_reach_both_shells(self):
        ids = re.findall(r"#define (SID_PRINTSCALE_\w+)\s+\(SID_NEW_SLOTS\+(\d+)\)", self.main["sc/inc/sc.hrc"])
        self.assertEqual(sorted(name for name, _ in ids), sorted(SLOTS))
        self.assertEqual(len({number for _, number in ids}), len(SLOTS))
        for sdi in ("sc/sdi/docsh.sdi", "sc/sdi/prevwsh.sdi"):
            for slot in SLOTS:
                self.assertIn(slot, self.main[sdi], sdi)
        for command, slot in zip(COMMANDS[1:] + COMMANDS[:1], SLOTS):
            self.assertRegex(self.main["sc/sdi/scalc.sdi"], r"\b%s %s\b" % (command, slot))

    def test_choices_map_onto_the_page_style_scale_items(self):
        code = self.main["sc/source/ui/docshell/printscale.cxx"]
        # percent, pages, width, height: what .xlsx writes as fitToPage + fitToWidth/fitToHeight
        self.assertIn("case PrintScaleMode::FitSheet:\n            return { 0, 0, 1, 1 };", code)
        self.assertIn("case PrintScaleMode::FitColumns:\n            return { 0, 0, 1, 0 };", code)
        self.assertIn("case PrintScaleMode::FitRows:\n            return { 0, 0, 0, 1 };", code)
        self.assertIn("return { 100, 0, 0, 0 };", code)
        for item in ("ATTR_PAGE_SCALE,", "ATTR_PAGE_SCALETOPAGES,", "ScPageScaleToItem("):
            self.assertIn(item, code)
        # undoable, per sheet
        self.assertIn("EnterListAction", code)
        self.assertIn('"PageStyle_" + aTabName', code)
        self.assertIn("rDocShell.IsReadOnly()", code)

    def test_print_dialog_offers_the_list_on_the_general_tab(self):
        ui = self.main["vcl/uiconfig/ui/printdialog.ui"]
        self.assertIn('id="scalingbox"', ui)
        self.assertIn('id="scalingboxlabel"', ui)
        self.assertIn("<property name=\"mnemonic-widget\">scalingbox</property>", ui)
        self.assertNotIn('<property name="visible">True</property>', ui)  # hidden in Writer and Slides
        self.assertIn('aID == "scalingbox"', self.main["vcl/source/window/printdlg.cxx"])
        docuno = self.main["sc/source/ui/unoobj/docuno.cxx"]
        self.assertIn('setChoiceListControlOpt(u"scalingbox"_ustr', docuno)
        self.assertIn('u"PrintScaling"_ustr', docuno)
        self.assertIn('rOption.Name == "ExtraPrintUIOptions"', docuno)
        self.assertIn("ApplyScaling( *pDocShell, rOptions, aMark )", docuno)

    def test_commands_have_labels_menu_toolbar_and_controllers(self):
        xcu = self.main["officecfg/registry/data/org/openoffice/Office/UI/CalcCommands.xcu"]
        for command in COMMANDS:
            self.assertIn('oor:name=".uno:%s"' % command, xcu)
        popup = self.main["sc/uiconfig/scalc/popupmenu/printscale.xml"]
        menubar = self.main["sc/uiconfig/scalc/menubar/menubar.xml"]
        for command in COMMANDS[1:]:
            self.assertIn('menu:id=".uno:%s"' % command, popup)
            self.assertIn('menu:id=".uno:%s"' % command, menubar)
        self.assertIn(".uno:PrintScaleMenu", self.main["sc/uiconfig/scalc/toolbar/previewbar.xml"])
        controller = self.main["officecfg/registry/data/org/openoffice/Office/UI/Controller.xcu"]
        self.assertIn("<value>printscale</value>", controller)
        self.assertIn("GenericPopupToolbarController", controller)
        self.assertIn("sc/uiconfig/scalc/popupmenu/printscale", self.main["sc/UIConfig_scalc.mk"])
        self.assertIn("sc/source/ui/docshell/printscale", self.main["sc/Library_sc.mk"])

    def test_ribbon_places_the_drop_down_on_page_layout_and_print_preview(self):
        ui = self.ribbon["sc/uiconfig/scalc/ui/notebookbar.ui"]
        for control in ("bxLayoutPrintScaleMenu", "btnLayoutPrintScaleMenu", "bxPrintPrintScaleMenu",
                        "btnPrintPrintScaleMenu"):
            self.assertIn('id="%s"' % control, ui)
        self.assertEqual(ui.count("<property name=\"action-name\">.uno:PrintScaleMenu</property>"), 2)

    def test_vietnamese_strings(self):
        sc_po = po_entries(self.main["translations/source/vi/sc/messages.po"])
        for choice in VI_CHOICES:
            self.assertIn(choice, sc_po.values())
        ui_po = po_entries(self.main["translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po"])
        self.assertEqual(ui_po["Scaling"], "Thu phóng")
        self.assertEqual(ui_po["Fit All Columns on One Page"], "Vừa tất cả các cột trên một trang")
        self.assertEqual(ui_po["Custom Scaling Options..."], "Tùy chọn thu phóng")  # no ellipsis in vi labels
        vcl_po = po_entries(self.main["translations/source/vi/vcl/messages.po"])
        self.assertEqual(vcl_po["Scal_ing:"], "T_hu phóng:")
        for po in (sc_po, ui_po, vcl_po):
            for source, translation in po.items():
                self.assertEqual(re.findall(r"%\d", source), re.findall(r"%\d", translation), source)
                self.assertTrue(translation, source)

    def test_feature_search_words(self):
        with open(os.path.join(EXTENSION, "FeatureSearch.xcu"), encoding="utf-8") as handle:
            xcu = handle.read()
        match = re.search(r"<value>\.uno:PrintScaleFitColumns</value></prop>\s*<prop oor:name=\"Words\"><value>"
                          r"([^<]*)</value>", xcu)
        self.assertIsNotNone(match)
        for words in ("vừa trang", "in vừa trang", "fit to page", "fit columns", "thu phóng in"):
            self.assertIn(words, match.group(1))
        for command in COMMANDS[1:]:
            self.assertIn("<value>.uno:%s</value>" % command, xcu)

    def test_help_page_is_linked_and_names_no_other_vendor(self):
        help_dir = os.path.join(EXTENSION, "help")
        with open(os.path.join(help_dir, "bang-tinh-in.html"), encoding="utf-8") as handle:
            page = handle.read()
        for text in VI_CHOICES + ("Thu phóng", "Tùy chọn thu phóng", "Ctrl</kbd>+<kbd>Z"):
            self.assertIn(text, page)
        images = re.findall(r'src="(images/[^"]+)"', page)
        for image in images:
            self.assertTrue(os.path.isfile(os.path.join(help_dir, image)), image)
        for path in glob.glob(os.path.join(help_dir, "*.html")):
            with open(path, encoding="utf-8") as handle:
                self.assertIn('href="bang-tinh-in.html"', handle.read(), path)
        user_text = page + self.main["translations/source/vi/sc/messages.po"]
        self.assertNotRegex(user_text, r"(?i)microsoft|excel|\bword\b|powerpoint")


if __name__ == "__main__":
    unittest.main()
