# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-v3-layout.patch: the v3 group layout, the fit, the elastic banner and the details of the locked design."""
import unittest

from patch_sections import added, po_entries, sections

PATCH = "hst-ribbon-v3-layout.patch"


class LayoutTest(unittest.TestCase):
    def test_grid_routes_to_the_v3_layout(self):
        code = added(PATCH, "vcl/source/window/layout.cxx")
        self.assertIn("return hst::ribbon::v3::Requisition(*this);", code)
        self.assertIn("hst::ribbon::v3::Allocate(*this, rAllocation);", code)
        self.assertIn('else if (rKey == "hst-ribbon-layout")', code)
        self.assertIn("vcl/source/control/HstRibbonV3Layout \\", added(PATCH, "vcl/Library_vcl.mk"))

    def test_group_geometry(self):
        code = added(PATCH, "vcl/source/control/HstRibbonV3Layout.cxx")
        # 6 px padding and top, content, 4 px gap, caption band of 18 px at least, the separator at the right edge
        self.assertIn("const tools::Long nPad = px(6, rGrid), nTop = px(6, rGrid);", code)
        self.assertIn("const tools::Long nBand = px(18, rGrid);", code)
        self.assertIn("rSize.Width() - nLine", code)
        # the caption is the child at row 3 (generate-ribbon-v3-ui.py)
        self.assertIn("return rChild.get_grid_top_attach() >= 3;", code)

    def test_style_list_rows_are_24_px_in_gtk_and_vcl(self):
        code = added(PATCH, "svx/source/tbxctrls/StylesPreviewWindow.cxx")
        # vcl's builder sets the .ui's item padding 2 as the icon view's spacing: 4 px of room in both toolkits
        self.assertIn("constexpr tools::Long nRoom = 4;", code)
        self.assertIn("constexpr tools::Long HST_LIST_ROW = 24;", code)

    def test_medium_menu_button_measured_as_painted(self):
        code = added(PATCH, "vcl/source/control/HstRibbonV3Layout.cxx")
        self.assertIn("std::max<tools::Long>(1, 1 + (nTextHeight - 10) / 2);", code)
        self.assertIn("tools::Long nWidth = nFrame + 2 * nSymbol;", code)
        self.assertIn("it = rWidths.emplace(nKey, commandWidth(rCommand, cLook)).first;", code)
        # a large one: its label's lines ("Bam\\ndinh \u25be"), each centred in the frame, not its words
        self.assertIn("pMenu->GetTextWidth(aText.getToken(0, '\\n', nIndex))", code)
        self.assertIn("if (const tools::Long nNeed = menuButtonNeed(rCommand, rCell.look))", code)

    def test_one_button_stretches_over_its_cell(self):
        code = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if ( nButtons == 1 && !pOnly->maRect.IsEmpty() && nRight > pOnly->maRect.Right() + 1 )", code)


class FitTest(unittest.TestCase):
    def test_mockup_fit_steps(self):
        code = added(PATCH, "vcl/source/control/HstRibbonV3MergedBox.cxx")
        self.assertIn("const bool bSparse = freeShare() > 0.4;", code)
        self.assertIn("px(std::max<long>(bWide ? 96 : 52, (nLogical + 1) / 2 * 2))", code)
        self.assertIn("for (const char cStep : { 'M', 'S', 'C' })", code)
        # galleries take more tiles while the tab is still more than 40 % free
        self.assertIn("for (int nExtra = 1; !aGalleries.empty() && nExtra <= 10 && freeShare() > 0.4; ++nExtra)", code)
        self.assertIn('set_property(u"hst-gallery-extra"_ustr, aExtra)',
                      added(PATCH, "vcl/source/control/HstRibbonV3Layout.cxx"))
        self.assertIn('if (rKey == "hst-gallery-extra")', added(PATCH, "svx/source/tbxctrls/HstStyleGalleryWindow.cxx"))
        self.assertIn("HstApplyV3(nWidth);", added(PATCH, "vcl/source/control/PriorityMergedHBox.cxx"))

    def test_new_files_are_hst_owned_and_the_box_keeps_hooks_only(self):
        for path in ("vcl/inc/HstRibbonV3Pack.hxx", "vcl/inc/HstRibbonV3Layout.hxx",
                     "vcl/source/control/HstRibbonV3Layout.cxx", "vcl/source/control/HstRibbonV3MergedBox.cxx"):
            self.assertIn("SPDX-License-Identifier: LicenseRef-HST-Proprietary", added(PATCH, path), path)
        self.assertLess(len(added(PATCH, "vcl/source/control/PriorityMergedHBox.cxx").splitlines()), 30)


class BannerTest(unittest.TestCase):
    def test_elastic_banner(self):
        code = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("nMin = hst::banner::scaled(360, fDpi), nMax = hst::banner::scaled(960, fDpi)", code)
        self.assertIn("Size(nBanner, hst::banner::scaled(96, fDpi))", code)
        self.assertIn("hst::ribbon::SetPageSlack(*pPage, nSmallest - nPageWidth);", code)

    def test_old_artwork_left_aligned_with_fill(self):
        code = added(PATCH, "vcl/source/control/HstBannerCore.cxx")
        self.assertIn("aFit = Rect{ 0, 0, nWidth, nHeight };", code)
        self.assertIn("bool BannerFillsWidth() const override { return true; }", added(PATCH, "vcl/source/control/HstBanner.cxx"))


class DetailsTest(unittest.TestCase):
    def test_keytip_hint_only(self):
        self.assertIn("aText += \"\\n\" + SfxResId(STR_HST_TIP_SEARCH_HINT);",
                      added(PATCH, "sfx2/source/notebookbar/HstRibbonTooltip.cxx"))
        entries = po_entries(added(PATCH, "translations/source/vi/sfx2/messages.po"))
        self.assertEqual(entries["STR_HST_TIP_SEARCH_HINT"][1], "Tìm nhanh lệnh: Alt+Q, gõ tên lệnh")

    def test_style_list_and_gallery_tiles(self):
        code = added(PATCH, "svx/source/tbxctrls/StylesPreviewWindow.cxx")
        self.assertIn("constexpr tools::Long HST_LIST_ROW = 24;", code)
        self.assertIn('return lcl_HstModuleIs(u"scalc") ? 104 : 132;', code)
        self.assertIn("constexpr int COLUMNS[] = { 5, 4, 3 };", added(PATCH, "svx/source/tbxctrls/HstStyleGalleryWindow.cxx"))
        self.assertIn("constexpr int HST_COLUMNS[] = { 5, 4, 3 };",
                      added(PATCH, "svx/source/tbxctrls/ThemeColorsToolBoxControl.cxx"))

    def test_every_file_has_hunks(self):
        for path, lines in sections(PATCH).items():
            self.assertTrue(any(line.startswith("@@") for line in lines), path)


if __name__ == "__main__":
    unittest.main()
