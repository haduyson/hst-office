# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-styles-gallery-states.patch: Writer's Styles gallery keeps 6, 4, 3 previews at the large, medium and
small group (gap list G05), through the ribbon ladder's "hst-gallery-state" property."""
import unittest

from patch_sections import added, after, po_entries, removed

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
        self.assertIn("m_xHstScroll->set_size_request(nWidth, nHeight);", code)
        self.assertIn("static_cast<int>(std::lround(HST_GALLERY_HEIGHT * fScale));", code)
        self.assertNotIn(", -1);", code)
        # vcl's builder folds "stylesscroll" into the icon view: the view takes the size there
        self.assertIn("g_bHstVclIconView = !m_xHstScroll;", code)
        self.assertIn("m_xStylesView->set_size_request(nWidth, nHeight);", code)
        self.assertIn("constexpr tools::Long HST_GALLERY_HEIGHT = 76;", code)

    def test_fixed_tiles_not_the_view_width(self):
        code = added(MOCKUP, GALLERY)
        self.assertIn("constexpr int HST_PREVIEWS[] = { 6, 4, 3 };", after(MOCKUP, GALLERY))
        self.assertIn("constexpr tools::Long HST_TILE_WIDTH = 96;", code)
        self.assertIn("constexpr tools::Long HST_TILE_HEIGHT = 74;", code)
        self.assertIn("return std::max<size_t>(1, m_nHstTiles); }", code)
        self.assertIn("connect_size_allocate", removed(MOCKUP, GALLERY))
        # the item window's preferred size is its content's cached requisition: invalidated before measuring,
        # or the ladder measured the large gallery (602 px) at every state
        self.assertIn("    HstApplyPreviews();\n    // the window's preferred size", after(MOCKUP, GALLERY))
        self.assertIn("InvalidateChildSizeCache();\n    SetOptimalSize();", after(MOCKUP, GALLERY))
        self.assertEqual(added(MOCKUP, "svx/source/inc/HstRibbonCombos.hxx").count("rWindow.InvalidateChildSizeCache();"), 2)
        self.assertNotIn("ViewSizeHdl", after(MOCKUP, "svx/source/inc/StylesPreviewWindow.hxx"))
        # the image leaves gtk's item padding 2 (92 x 70) or vcl's own 5 px (86 x 64) of the 96 x 74 tile
        self.assertIn("const tools::Long nRoom = g_bHstVclIconView ? 10 : 4;", code)
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

    def test_ribbon_boxes_narrow_their_padding_on_gtk3(self):
        # owner's decision D9: 46 px on gtk3 too, frame kept ("small-button" took the frame away)
        self.assertIn('hst::ribbon::BoxUIFile(pParent, u"fontnamebox")', added(MOCKUP, "svx/source/tbxctrls/tbcontrl.cxx"))
        self.assertIn('hst::ribbon::BoxUIFile(pParent, u"fontsizebox")',
                      added(MOCKUP, "svx/source/tbxctrls/tbunocontroller.cxx"))
        mk = added(MOCKUP, "svx/UIConfig_svx.mk")
        for name in ("fontnameboxribbon", "fontsizeboxribbon"):
            self.assertIn(f"svx/uiconfig/ui/{name}", mk)
            ui = added(MOCKUP, f"svx/uiconfig/ui/{name}.ui")
            self.assertIn('<class name="hst-ribbon-combo"/>', ui)
            self.assertNotIn("small-button", ui)
            base = name.replace("ribbon", "")
            self.assertIn(f'context="{base}|{base.replace("box", "combobox")}|accessible_name"', ui)
        gtk = added(MOCKUP, "vcl/unx/gtk3/gtkinst.cxx")
        self.assertIn('"hst-ribbon-combo"))', gtk)
        self.assertIn('"entry { padding-left: 4px; padding-right: 2px; min-width: 0; }"', gtk)
        self.assertIn('"button { padding-left: 2px; padding-right: 2px; min-width: 0; }"', gtk)
        self.assertNotIn("border", gtk)  # the frames stay


class RibbonSizeWithoutUnit(unittest.TestCase):
    def test_bare_size_in_the_ribbon_only(self):
        header = added(MOCKUP, "include/svtools/ctrlbox.hxx")
        self.assertIn("bool m_bHstShowUnit : 1;", header)  # in the byte of the other flags: same class layout
        self.assertIn("void set_show_unit(bool bShow) { m_bHstShowUnit = bShow; }", header)
        code = added(MOCKUP, "svtools/source/control/ctrlbox.cxx")
        self.assertIn("if (m_bHstShowUnit || m_bRelative)", code)
        self.assertIn(", m_bHstShowUnit(true)", code)  # every other box keeps "pt"
        size = added(MOCKUP, "svx/source/tbxctrls/tbunocontroller.cxx")
        self.assertIn("if (hst::ribbon::InNotebookbar(*pParent))\n        m_xWidget->set_show_unit(false);", size)


class ThemeGalleryWidthPerState(unittest.TestCase):
    def test_measured_after_the_cache_goes(self):
        code = added("hst-ribbon-ux-gallery-fit.patch", "svx/source/tbxctrls/ThemeColorsToolBoxControl.cxx")
        self.assertIn("HstApplyColumns();\n    // the window's preferred size", code)
        self.assertIn("InvalidateChildSizeCache();\n    SetOptimalSize();\n    return true;", code)


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
