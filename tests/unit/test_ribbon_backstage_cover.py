# SPDX-License-Identifier: AGPL-3.0-only
"""The File page covers the ribbon body and the document left of the banner (hst-ribbon-adaptive-backstage.patch)."""
import unittest

from patch_sections import added, removed

PATCH = "hst-ribbon-adaptive-backstage.patch"
WINDOW = "sfx2/source/backstage/hstbackstagewindow.cxx"


class BackstageCover(unittest.TestCase):
    def test_drops_from_the_tab_row_down_to_the_bottom(self):
        code = added(PATCH, WINDOW)
        self.assertIn("pTabs->OutputToAbsoluteScreenPixel(Point(0, pPage->GetPosPixel().Y()))", code)
        self.assertIn("std::min(aFrame.Height() - aTop.Y() - nInset, aScreen.Bottom() - aEdge.Y() - nInset)", code)
        self.assertIn("constexpr tools::Long PANEL_WIDTH = 780;", removed(PATCH, WINDOW))

    def test_stops_left_of_the_banner(self):
        code = added(PATCH, WINDOW)
        self.assertIn("dynamic_cast<const HstRibbonBanner*>(pChild)", code)
        self.assertIn("pBanner->OutputToAbsoluteScreenPixel(Point())", code)


    def test_document_tab_strip_stays_visible(self):
        tabs = "hst-ribbon-adaptive-backstage-tabs.patch"
        self.assertIn('set_id(u"hst-document-tabs"_ustr);', added(tabs, "framework/source/uielement/documenttabbar.cxx"))
        code = added(tabs, WINDOW)
        self.assertIn("if (const vcl::Window* pDocTabs = lcl_findDocumentTabs(*pFrameWindow))", code)
        self.assertIn("const Point aTop = pOrigin->AbsoluteScreenToOutputPixel(aEdgeTop);", code)


if __name__ == "__main__":
    unittest.main()
