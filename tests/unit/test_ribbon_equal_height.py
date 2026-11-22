# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-equal-height.patch: one ribbon height in Writer, Sheets, Slides and Draw (gap list G06); since
hst-ribbon-mockup-frame.patch a fixed 106 px body (tab row + 3 + 106 + 3 = 147 px) in every tab."""
import os
import unittest

from _paths import ROOT

from patch_sections import added

PATCH = "hst-ribbon-equal-height.patch"


class EqualHeight(unittest.TestCase):
    def test_full_ribbon_requests_the_shared_height(self):
        code = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("constexpr double HST_RIBBON_HEIGHT = 165;", code)
        # only the full ribbon: the compact one keeps its tab row and quick row
        self.assertIn("its own height", code)
        self.assertIn("std::lround(HST_RIBBON_HEIGHT * GetDPIScaleFactor())", code)


FRAME = "hst-ribbon-mockup-frame.patch"
TABS = "sfx2/source/notebookbar/NotebookbarTabControl.cxx"


class MockupFrame(unittest.TestCase):
    def test_body_is_106_px_or_the_tallest_page(self):
        code = added(FRAME, TABS)
        # the tab row, the two 3 px insets and a body of 106 logical px rounded once, or the tallest page's content
        # and captions when they ask for more: a fixed body cut the captions under a larger UI font
        self.assertIn("tools::Long nBody = hst::banner::scaled(hst::banner::RIBBON_BODY_HEIGHT, fDpi);", code)
        self.assertIn("nBody = std::max(nBody, VclContainer::getLayoutRequisition(*pPage).Height());", code)
        self.assertIn("aSize.setHeight(HstHeaderHeight() + HST_PAGE_INSETS + nBody);", code)
        self.assertIn("constexpr tools::Long HST_PAGE_INSETS = 2 * 3;", code)
        # only the ribbon with the banner; other notebookbar files keep the old minimum
        self.assertIn("if (m_pHstBanner && HstHeaderHeight() > 0)", code)
        self.assertIn("std::max<tools::Long>(aSize.Height(), std::lround(HST_RIBBON_HEIGHT * fDpi))", code)
        self.assertIn("constexpr long RIBBON_BODY_HEIGHT = 106;", added(FRAME, "include/vcl/HstBannerGeometry.hxx"))

    def test_banner_follows_the_window_frame(self):
        code = added(FRAME, TABS)
        self.assertIn("pFrame ? pFrame->GetOutputSizePixel().Width() : GetOutputSizePixel().Width(), fDpi);", code)
        self.assertIn("nMaxWidth, HstBannerRight());", code)
        self.assertNotIn("GetSystemWindow()", code)
        self.assertIn("hst::banner::scaled(hst::banner::RIGHT_GAP, GetDPIScaleFactor());", code)

    def test_compact_banner_and_reserve(self):
        code = added(FRAME, TABS)
        self.assertIn("const hst::banner::StripSlot aSlot = hst::banner::compactSlot(fDpi);", code)
        self.assertIn("Point(HstBannerRight() - aSlot.w,", code)
        # the tab row, the quick row and the dropped page stop 8 px before the banner (W - 276 px)
        self.assertIn("const tools::Long nBannerLeft = HstBannerRight() - hst::banner::compactSlot(fDpi).w;", code)

    def test_macos_shortcut(self):
        code = added(FRAME, TABS)
        self.assertIn("#ifdef MACOSX", code)
        self.assertIn("nFull == (KEY_R | KEY_MOD1 | KEY_MOD2)", code)
        self.assertIn("const bool bToggle = nFull == (KEY_F1 | KEY_MOD1);", code)  # elsewhere only Ctrl+F1

    def test_in_series(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            names = handle.read().split()
        self.assertIn(FRAME, names)
        self.assertGreater(names.index(FRAME), names.index(PATCH))


if __name__ == "__main__":
    unittest.main()
