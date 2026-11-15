# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-styles-gallery-states.patch: Writer's Styles gallery keeps 6, 4, 3 previews at the large, medium and
small group (gap list G05), through the ribbon ladder's "hst-gallery-state" property."""
import unittest

from patch_sections import added, after, po_entries, removed, sections

PATCH = "hst-ribbon-styles-gallery-states.patch"


class StylesGalleryStates(unittest.TestCase):
    def test_answers_the_ladder_state(self):
        code = added(PATCH, "svx/source/tbxctrls/StylesPreviewWindow.cxx")
        self.assertIn("constexpr int HST_PREVIEWS[] = { 6, 4, 3 };", code)
        self.assertIn('if (rKey != "hst-gallery-state")', code)
        self.assertIn("return false; // nothing changed", code)  # the ladder lays out again only on a change
        header = added(PATCH, "svx/source/inc/StylesPreviewWindow.hxx")
        self.assertIn("bool set_property(const OUString& rKey, const OUString& rValue) override;", header)


MOCKUP = "hst-ribbon-mockup-gallery-combos.patch"
GALLERY = "svx/source/tbxctrls/StylesPreviewWindow.cxx"


class MockupGallery(unittest.TestCase):
    """The approved 1.0.2 mockup: one-line previews of 96 px, 6/4/3 of them, never stretched, short names."""

    def test_height_survives_the_width_request(self):
        # set_size_request(width, -1) dropped the .ui's height-request on gtk3: a 2 px view, a blank gallery
        code = added(MOCKUP, GALLERY)
        self.assertIn("m_xHstScroll->set_size_request(std::lround((nTiles * HST_TILE_WIDTH + 2) * fScale),", code)
        self.assertIn("std::lround(HST_GALLERY_HEIGHT * fScale));", code)
        self.assertNotIn(", -1);", code)
        self.assertIn("constexpr tools::Long HST_GALLERY_HEIGHT = 76;", code)

    def test_fixed_tiles_not_the_view_width(self):
        code = added(MOCKUP, GALLERY)
        self.assertIn("constexpr int HST_PREVIEWS[] = { 6, 4, 3 };", after(MOCKUP, GALLERY))
        self.assertIn("constexpr tools::Long HST_TILE_WIDTH = 96;", code)
        self.assertIn("return std::max<size_t>(1, m_nHstTiles); }", code)
        self.assertIn("connect_size_allocate", removed(MOCKUP, GALLERY))
        self.assertNotIn("ViewSizeHdl", after(MOCKUP, "svx/source/inc/StylesPreviewWindow.hxx"))
        # 92 x 70 and the item padding 2 on each side make the 96 x 74 preview
        self.assertIn("HST_PREVIEW_IMAGE_WIDTH = 92;", code)
        self.assertIn("HST_PREVIEW_IMAGE_HEIGHT = 70;", code)
        ui = after(MOCKUP, "svx/uiconfig/ui/stylespreview.ui")
        for prop in ('"item-padding">2<', '"item-width">92<', '"height-request">76<', '"width-request">16<'):
            self.assertIn(prop, ui)
        ui_added = added(MOCKUP, "svx/uiconfig/ui/stylespreview.ui")
        self.assertNotIn('"hexpand">True<', ui_added)
        self.assertIn('<property name="halign">start</property>', ui_added)
        self.assertEqual(ui_added.count('<property name="expand">False</property>'), 2)

    def test_one_line_name(self):
        code = added(MOCKUP, GALLERY)
        self.assertIn("DrawTextFlags::Center | DrawTextFlags::VCenter | DrawTextFlags::EndEllipsis);", code)
        self.assertNotIn("DrawTextFlags::MultiLine", code)

    def test_short_names(self):
        hrc = added(MOCKUP, "svx/inc/hststylesshortnames.hrc")
        po = po_entries(added(MOCKUP, "translations/source/vi/svx/messages.po"))
        expected = {"STANDARD": ("Normal", "Thường"), "TEXT_BODY": ("Body Text", "Văn bản"),
                    "HEADING_1": ("Heading 1", "Tiêu đề 1"), "HEADING_2": ("Heading 2", "Tiêu đề 2"),
                    "TITLE": ("Title", "Tựa đề"), "QUOTATIONS": ("Quote", "Trích dẫn")}
        for key, (english, vietnamese) in expected.items():
            ctx = f"RID_HST_STYLE_SHORT_{key}"
            self.assertIn(f'NC_("{ctx}", "{english}")', hrc)
            self.assertEqual(po[ctx], (english, vietnamese))
        code = added(MOCKUP, GALLERY)
        # keyed by the programmatic names, in the mockup's order; the styles come first in that order
        order = ['u"Standard"', 'u"Text body"', 'u"Heading 1"', 'u"Heading 2"', 'u"Title"', 'u"Quotations"']
        positions = [code.index(name) for name in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("std::stable_sort(m_aAllStyles.begin(), m_aAllStyles.end(),", code)

    def test_row_buttons(self):
        po = po_entries(after(MOCKUP, "translations/source/vi/svx/messages.po"))
        self.assertEqual(po["stylespreview|prevstyles"], ("Previous Styles", "Hàng trước"))
        self.assertEqual(po["stylespreview|nextstyles"], ("Next Styles", "Hàng sau"))
        self.assertEqual(po["stylespreview|morestyles"], ("All Styles", "Xem hết các kiểu"))


class MockupFontBoxes(unittest.TestCase):
    def test_widths_in_the_ribbon_only(self):
        helper = added(MOCKUP, "svx/source/inc/HstRibbonCombos.hxx")
        self.assertIn("constexpr tools::Long FONT_NAME_BOX_WIDTH = 128;", helper)
        self.assertIn("constexpr tools::Long FONT_SIZE_BOX_WIDTH = 46;", helper)
        self.assertIn("dynamic_cast<const NotebookBar*>(pParent)", helper)
        name = added(MOCKUP, "svx/source/tbxctrls/tbcontrl.cxx")
        self.assertIn("if (hst::ribbon::InNotebookbar(*this))", name)
        self.assertIn("hst::ribbon::FONT_NAME_BOX_WIDTH", name)
        size = added(MOCKUP, "svx/source/tbxctrls/tbunocontroller.cxx")
        self.assertIn("pCombo->set_entry_width_chars(2);", size)  # FontSizeBox asks for "105 pt"; "12" stays readable
        self.assertIn("hst::ribbon::FONT_SIZE_BOX_WIDTH", size)
        # gtk3 sizes the entry and puts the ▾ button on top: the overshoot is taken off the request
        self.assertIn("rWindow.get_preferred_size().Width() - nTarget;", helper)

    def test_fit_again_once_shown(self):
        # gtk3 counts the box's ▾ button only once it is shown: 128 px became 165
        helper = added(MOCKUP, "svx/source/inc/HstRibbonCombos.hxx")
        self.assertIn("class RibbonRefit final : public Idle", helper)
        self.assertIn("pBox->SetItemWindow(nId, &rWindow); // the item takes the window's new size", helper)
        for path in ("svx/source/tbxctrls/tbcontrl.cxx", "svx/source/tbxctrls/tbunocontroller.cxx"):
            code = added(MOCKUP, path)
            self.assertIn("nStateChange == StateChangedType::InitShow && !m_xHstRefit", code)
            self.assertIn("m_xHstRefit.reset();", code)  # stopped before the window goes
        self.assertNotIn("svx/UIConfig_svx.mk", sections(MOCKUP))  # no padding-free variant: it lost its frame


class CalcCellStylesGallery(unittest.TestCase):
    def test_mockup_order(self):
        code = added(MOCKUP, "svx/source/tbxctrls/StylesPreviewToolBoxControl.cxx")
        order = ['u"Default"', 'u"Good"', 'u"Neutral"', 'u"Bad"', 'u"Warning"', 'u"Heading 1"', 'u"Heading 2"']
        positions = [code.index(name) for name in order]
        self.assertEqual(positions, sorted(positions))

    def test_cell_look_and_writer_unchanged(self):
        code = added(MOCKUP, GALLERY)
        self.assertIn('if (lcl_HstModuleIs(u"scalc"))', code)
        self.assertIn("pItemSet->GetItem<SvxBrushItem>(SID_ATTR_BRUSH)", code)
        self.assertIn("rRenderContext.SetLineColor(Color(0xd6, 0xd6, 0xd6));", code)
        self.assertIn('if (lcl_HstModuleIs(u"swriter"))', code)  # the short-name order is Writer's only
        self.assertIn('const size_t nRank = lcl_HstModuleIs(u"swriter") ? lcl_HstShortRank(rStyle)', code)
        # Calc's font heights are twips; the shell's unit (1/100 mm) made the previews a third of their size
        self.assertIn("pItemSet->GetPool()->GetMetric(pFontHeightItem->Which())", code)
        # Writer's and Calc's "Heading 1" are different previews
        self.assertIn('(lcl_HstModuleIs(u"scalc") ? u"scalc:"_ustr : OUString()) + rStyle.translatedName;', code)


class CompactPixelsOnWindows(unittest.TestCase):
    def test_px_is_tools_long(self):
        # MSVC: long is 32 bit and tools::Long 64 bit, so std::max(tools::Long, long) did not compile
        code = added("hst-ribbon-adaptive-compact.patch", "sfx2/source/notebookbar/HstRibbonCompact.hxx")
        self.assertIn("inline tools::Long px(tools::Long nLogical, double fDpi)", code)


if __name__ == "__main__":
    unittest.main()
