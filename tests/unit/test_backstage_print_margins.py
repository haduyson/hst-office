# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Margins box of the File panel's Print page (hst-backstage-print.patch): the presets of Page Setup, one undo
step, the preview of the waiting job shown again. Read from the patch."""
import re
import unittest
import xml.etree.ElementTree as ET

from patch_sections import added, after, po_entries

PATCH = "hst-backstage-print.patch"
PANEL_UI = "vcl/uiconfig/ui/hstprintpanel.ui"
DIALOG = "vcl/source/window/printdlg.cxx"
JOBPANEL = "vcl/source/window/hstprintjobpanel.cxx"
PAGE = "sfx2/source/backstage/hstbackstageprint.cxx"
MARGINS = "sfx2/source/backstage/hstbackstageprintmargins.cxx"
DOCSH = "sc/source/ui/docshell/docsh4.cxx"
VCL_PO = "translations/source/vi/vcl/messages.po"
SFX_PO = "translations/source/vi/sfx2/messages.po"
ENTRIES = ["Normal", "Narrow", "Moderate", "Wide", "Custom Margins"]
IDS = ["normal", "narrow", "moderate", "wide", "custom"]
VIETNAMESE = ["Bình thường", "Hẹp", "Vừa", "Rộng", "Lề tùy chỉnh"]
MM100_PER_TWIP = 2540 / 1440


def by_id(root, oid):
    return next(o for o in root.iter("object") if o.get("id") == oid)


def props(obj):
    return {p.get("name"): p.text for p in obj.findall("property")}


class Box(unittest.TestCase):
    def test_box_under_orientation_hidden_until_offered(self):
        root = ET.fromstring(added(PATCH, PANEL_UI).encode("utf-8"))
        grid = by_id(root, "pagegrid")
        cells = {c.find("object").get("id"): (c.find("packing/property[@name='left-attach']").text,
                                              c.find("packing/property[@name='top-attach']").text)
                 for c in grid.findall("child")}
        self.assertEqual(cells["labelorientation"], ("0", "1"))
        self.assertEqual(cells["labelmargins"], ("0", "2"))
        self.assertEqual(cells["marginsbox"], ("1", "2"))
        label, box = by_id(root, "labelmargins"), by_id(root, "marginsbox")
        self.assertEqual(props(label)["mnemonic-widget"], "marginsbox")
        self.assertEqual(props(label)["visible"], "False")
        self.assertEqual(props(box)["visible"], "False")
        self.assertEqual([i.text for i in box.iter("item")], ENTRIES)
        self.assertEqual([i.get("id") for i in box.iter("item")], IDS)

    def test_dialog_and_job_panel(self):
        code = added(PATCH, DIALOG)
        self.assertIn('mxMarginsBox(m_xBuilder->weld_combo_box(u"marginsbox"_ustr))', code)
        self.assertIn("mxMarginsBox->connect_changed(LINK(this, PrintDialog, SelectMarginsHdl));", code)
        setter = code[code.index("void PrintDialog::setPanelMargins"):
                      code.index("OUString PrintDialog::getPanelMargins")]
        for step in ("mxMarginsBox->remove(nPos);", "mxMarginsBox->set_active_id(rActive);", "mxMarginsLabel->show();",
                     "mxMarginsBox->show();"):
            with self.subTest(step=step):
                self.assertIn(step, setter)
        job = added(PATCH, JOBPANEL)
        # the box comes back when the panel is made again (after the classic dialog was cancelled)
        show = job[job.index("void PrintJobPanel::Show"):job.index("void PrintJobPanel::Print")]
        self.assertIn("ShowMargins();", show)
        self.assertIn("m_xSettings->updatePreviewFromDocument();", job)
        # Writer formats for printing only when a job property changes: the document's change is one
        update = code[code.index("void PrintDialog::updatePreviewFromDocument()"):]
        self.assertIn('maPController->setValue(u"HstLayoutRevision"_ustr, css::uno::Any(++mnLayoutRevision));', update)
        self.assertIn("schedulePreviewUpdate(false);", update[:update.index("IMPL_LINK")])


class Presets(unittest.TestCase):
    def test_presets_are_the_applications_margins_menus(self):
        code = added(PATCH, MARGINS)

        def table(name):
            body = code[code.index("constexpr Preset %s[]" % name):]
            body = body[:body.index(";")]
            return [(i, tuple(int(v) for v in vals.split(", ")))
                    for i, vals in re.findall(r'\{ u"(\w+)", ([\d, ]+) \}', body)]
        writer = dict(table("WRITER"))
        # sw PageMarginUtils.hxx in twips: NORMAL 1136, NARROW 720, HST_MODERATE_LR 1080, WIDE 1440 / 2880
        for preset, twips in (("normal", (1136,) * 4), ("narrow", (720,) * 4), ("moderate", (1080, 1080, 1440, 1440)),
                              ("wide", (2880, 2880, 1440, 1440))):
            with self.subTest(preset=preset):
                self.assertEqual(writer[preset], tuple(round(t * MM100_PER_TWIP) for t in twips))
        self.assertEqual(writer["normal"][0], 2004)  # Bình thường = 2 cm
        self.assertIn("SWPAGE_HST_MODERATE_LR = 1080;", added("hst-writer-margin-moderate.patch",
                                                                "sw/source/uibase/sidebar/PageMarginControl.hxx"))
        # Sheets: the values of its ribbon's Margins menu (left, right, top, bottom), no Moderate
        menu = added("hst-ribbon-ux-calc.patch", "sc/uiconfig/scalc/ui/notebookbar.ui")
        calc = dict(table("CALC"))
        self.assertEqual(sorted(calc), ["narrow", "normal", "wide"])
        for preset, values in calc.items():
            with self.subTest(preset=preset):
                self.assertIn(".uno:CalcPageMargin?Page.LeftMargin:long=%d&amp;Page.RightMargin:long=%d&amp;"
                              "Page.TopMargin:long=%d&amp;Page.BottomMargin:long=%d" % values, menu)

    def test_commands_and_one_undo_step(self):
        code = added(PATCH, MARGINS)
        for name in ('u".uno:PageLRMargin"_ustr', 'u"Page.Left"_ustr', 'u"Page.Right"_ustr',
                     'u".uno:PageULMargin"_ustr', 'u"Page.Upper"_ustr', 'u"Page.Lower"_ustr',
                     'u".uno:CalcPageMargin"_ustr', 'u"Page.LeftMargin"_ustr', 'u"Page.BottomMargin"_ustr',
                     'u"SynchronMode"_ustr', 'u"moderate"'):
            with self.subTest(name=name):
                self.assertIn(name, code)
        self.assertLess(code.index("enterUndoContext(SfxResId(STR_HST_BS_PRINT_MARGINS))"),
                        code.index("leaveUndoContext()"))
        self.assertIn("bool HasMarginPresets(BackstageApp eApp) { return !lcl_presets(eApp).empty(); }", code)

    def test_calc_margins_command_is_undoable(self):
        code = after(PATCH, DOCSH)
        block = code[code.index("pStylePool->Find(aStyleName, SfxStyleFamily::Page);"):]
        self.assertLess(block.index("aOldData.InitFromStyle(pStyleSheet);"),
                        block.index("SfxItemSet& rSet = pStyleSheet->GetItemSet();"))
        self.assertLess(block.index("rSet.Put(aULItem);"), block.index("std::make_unique<ScUndoModifyStyle>("))
        self.assertLess(block.index("std::make_unique<ScUndoModifyStyle>("), block.index("SetDocumentModified();"))


class PageAction(unittest.TestCase):
    def test_preset_keeps_the_job_custom_opens_page_setup(self):
        page = added(PATCH, PAGE)
        margins = page[page.index("if (eAction == Action::Margins && m_xJob)"):page.index("// the job leaves the page")]
        for step in ("if (aPreset != MARGINS_CUSTOM)", "ApplyMarginPreset(m_xFrame, m_eApp, aPreset);",
                     "ShowMargins();", "m_xJob->UpdatePreview();",
                     "eAction = Action::PageSetup;"):
            with self.subTest(step=step):
                self.assertIn(step, margins)
        self.assertIn("if (m_xJob && HasMarginPresets(m_eApp))", page)
        self.assertIn("GetMarginPreset(m_xFrame, m_eApp), RemovedMarginPresets(m_eApp),", page)

    def test_vietnamese(self):
        entries = re.findall(r'msgctxt "hstprintpanel\|marginsbox"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"',
                             added(PATCH, VCL_PO))
        self.assertEqual(entries, list(zip(ENTRIES, VIETNAMESE)))
        self.assertEqual(po_entries(added(PATCH, VCL_PO))["hstprintpanel|labelmargins"][1], "Lề trang:")
        self.assertEqual(po_entries(added(PATCH, SFX_PO))["STR_HST_BS_PRINT_MARGINS"][1], "Đổi lề trang")


if __name__ == "__main__":
    unittest.main()
