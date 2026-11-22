# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-contextual-tab-stays-on-row.patch: a short tab row leaves off plain tabs before the contextual tab."""
import unittest

from patch_sections import added, removed

PATCH = "hst-ribbon-contextual-tab-stays-on-row.patch"


class ContextualTabStaysOnRow(unittest.TestCase):
    def test_plain_tabs_go_before_contextual_ones(self):
        helper = added(PATCH, "vcl/inc/HstRibbonTabsFit.hxx")
        self.assertIn("for (TabRank eRank : { TabRank::Plain, TabRank::Contextual, TabRank::Kept })", helper)
        self.assertIn("for (std::size_t i = rWidths.size(); i-- > 0 && nUsed > nRoom;)", helper)

    def test_the_row_ranks_its_tabs_and_closes_up(self):
        code = added(PATCH, "vcl/source/control/tabctrl.cxx")
        # a contextual tab is one whose page is not shown in every context, as the tab painting marks it
        self.assertIn("!item.mpTabPage->HasContext(vcl::EnumContext::Context::Any)", code)
        self.assertIn("item.maTabName == hst::ribbon::FILE_TAB_NAME ? hst::ribbon::TabRank::Kept", code)
        self.assertIn("hst::ribbon::tabsLeftOff(aHstWidths, aHstRanks, nRowEnd - nOffsetX + 1)", code)
        self.assertIn("rItem.maRect.SetPos(Point(nTabX, rItem.maRect.Top()));", code)
        # the old rule left off every tab past the row end, the contextual tab first
        self.assertIn("item.maRect.Right() > nRowEnd", removed(PATCH, "vcl/source/control/tabctrl.cxx"))

    def test_the_regression_test_is_built(self):
        self.assertIn("CppunitTest_vcl_hst_ribbon_tabs_fit \\", added(PATCH, "vcl/Module_vcl.mk"))
        test = added(PATCH, "vcl/qa/cppunit/hst/ribbon-tabs-fit-test.cxx")
        self.assertIn("testSelectedPictureKeepsItsTab", test)


if __name__ == "__main__":
    unittest.main()
