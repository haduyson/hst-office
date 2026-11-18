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

    def test_one_button_stretches_over_its_cell(self):
        code = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if ( nButtons == 1 && !pOnly->maRect.IsEmpty() && nRight > pOnly->maRect.Right() + 1 )", code)


class FitTest(unittest.TestCase):
    def test_mockup_fit_steps(self):
        code = added(PATCH, "vcl/source/control/PriorityMergedHBox.cxx")
        self.assertIn("const bool bSparse = freeShare() > 0.4;", code)
        self.assertIn("px(bWide ? 96 : std::clamp<long>((nLogical + 1) / 2 * 2, 52, 96))", code)
        self.assertIn("for (const char cStep : { 'M', 'S', 'C' })", code)
        self.assertIn("HstApplyV3(nWidth);", code)


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
