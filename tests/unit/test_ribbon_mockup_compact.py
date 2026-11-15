# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-mockup-compact.patch and hst-ribbon-mockup-compact-keytips.patch: the compact ribbon (Ctrl+F1) as the
approved 1.0.2 mockup draws it (quick row, dropped page, pin) and its KeyTips as in the reference suite."""
import os
import unittest

from _paths import ROOT
from patch_sections import added

PATCH = "hst-ribbon-adaptive-compact.patch"

MOCKUP_PATCH = "hst-ribbon-mockup-compact.patch"
KEYTIPS_PATCH = "hst-ribbon-mockup-compact-keytips.patch"


class MockupGeometry(unittest.TestCase):
    """The approved 1.0.2 mockup's compact ribbon: quick row, dropped page and its pin."""

    def test_quick_buttons_and_separators(self):
        code = added(MOCKUP_PATCH, "sfx2/source/notebookbar/HstRibbonCompact.cxx")
        self.assertIn("const tools::Long nButton = px(30, fDpi);", code)
        self.assertIn("InsertItem(aCommand, xFrame, ToolBoxItemBits::NONE, Size(0, nButton));", code)
        self.assertIn("static_cast<sal_uInt16>(px(9, fDpi))", code)  # 1 px line, 4 px each side
        widgets = added(MOCKUP_PATCH, "sfx2/source/notebookbar/HstRibbonCompactWidgets.cxx")
        self.assertIn("px(22, GetDPIScaleFactor()) / 2", widgets)
        self.assertIn("GetItemType(i) != ToolBoxItemType::SEPARATOR", widgets)

    def test_quick_row_starts_6_px_in_and_chevron_sits_4_px_from_the_corner(self):
        code = added(MOCKUP_PATCH, "sfx2/source/notebookbar/HstRibbonCompact.cxx")
        self.assertIn("const Point aAt(px(6, fDpi) - aFirst.Left(),", code)
        self.assertIn("Point(aEnd.X() - nInset - aChevron.Width(), aEnd.Y() - nInset - aChevron.Height())", code)

    def test_dropped_page_is_106_between_3_px_strips_with_the_pin(self):
        drop = added(MOCKUP_PATCH, "vcl/source/control/HstRibbonDrop.cxx")
        self.assertIn("SetOutputSizePixel(Size(nWidth, nStrip + nPage + nStrip));", drop)
        self.assertIn("nStrip = px(3, fDpi), nPage = px(106, fDpi);", drop)
        self.assertIn("Point(nWidth - px(4, fDpi) - aPin.Width(), nPage - nStrip - aPin.Height())", drop)
        self.assertNotIn("ImplCalculateRequisition", drop)
        # one id on both sides of the module boundary
        self.assertIn('PIN_ID = u"hstribbonpin"_ustr;', drop)
        self.assertIn('PIN_ID = u"hstribbonpin"_ustr;', added(MOCKUP_PATCH, "sfx2/source/notebookbar/HstRibbonCompact.hxx"))

    def test_pin_goes_with_the_page_and_switches_after_its_click(self):
        code = added(MOCKUP_PATCH, "sfx2/source/notebookbar/HstRibbonCompact.cxx")
        self.assertIn("SfxResId(STR_HST_RIBBON_PIN)", code)
        self.assertIn("m_xPin->SetParent(pPage);", code)
        self.assertIn("m_xPin->SetParent(&m_rTabs);", code)
        self.assertIn("Application::PostUserEvent(LINK(this, HstRibbonCompact, PinToggleHdl))", code)
        self.assertIn("Application::RemoveUserEvent(m_pPinEvent);", code)

    def test_click_on_another_tab_drops_it(self):
        drop = added(MOCKUP_PATCH, "vcl/source/control/HstRibbonDrop.cxx")
        self.assertIn("if (nTab && nTab != m_xTabs->GetCurPageId())", drop)
        self.assertIn("VclPtr<HstRibbonDrop> xKeep(this);", drop)
        self.assertIn("MouseEvent(m_aClickPos, 1, MouseEventModifiers::SIMPLECLICK, MOUSE_LEFT)", drop)


class CompactKeyTips(unittest.TestCase):
    def test_tab_tip_drops_the_page_and_tips_follow_in_the_popup(self):
        code = added(KEYTIPS_PATCH, "sfx2/source/notebookbar/HstRibbonKeyTips.cxx")
        self.assertIn("if (!bFile && DropTab(nId))", code)
        self.assertIn("m_xShown = pPage ? pPage->GetSystemWindow() : nullptr;", code)
        # the tips wait for the popup, then PopupTimerHdl shows them on it
        self.assertIn("m_bAwaitPopup = true;", code)
        self.assertLess(code.index("Close();"), code.index("m_aPopupTimer.Start();"))

    def test_current_tab_posts_a_click(self):
        code = added(KEYTIPS_PATCH, "sfx2/source/notebookbar/HstRibbonKeyTips.cxx")
        self.assertIn("Application::PostMouseEvent(VclEventId::WindowMouseButtonDown, m_xTabs.get(), &aDown);", code)
        self.assertIn('|| m_xTabs->GetPageName(nCurrent) == "FileLabel")', code)

    def test_series_order(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            series = handle.read().split()
        self.assertLess(series.index(PATCH), series.index(MOCKUP_PATCH))
        self.assertLess(series.index(MOCKUP_PATCH), series.index(KEYTIPS_PATCH))



if __name__ == "__main__":
    unittest.main()
