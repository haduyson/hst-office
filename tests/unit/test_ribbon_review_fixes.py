# SPDX-License-Identifier: AGPL-3.0-only
"""Regression guards for the ribbon engine fixes, read from the patches (no build needed).

The behaviour itself is checked on a real GUI by the runtime checks named in each test; these keep
the fixes from being lost when patches are regenerated or reordered.
"""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")


def added(name, path=None):
    """Added lines of a patch, optionally of one file only."""
    lines, current = [], None
    with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = match.group(1)
            elif line.startswith("+") and (path is None or current == path):
                lines.append(line[1:])
    return "".join(lines)


class ReviewFixes(unittest.TestCase):
    def test_content_key_is_unsigned(self):
        # signed nKey * 31 overflowed (undefined behaviour) for groups with a few items
        text = added("hst-ribbon-ladder-key-unsigned.patch")
        self.assertIn("sal_uInt32 GroupContentKey(vcl::Window& rGroup)", text)
        self.assertIn("sal_uInt32 nKey = 0;", text)
        self.assertNotIn("sal_Int32 nKey", text)
        self.assertIn("std::pair<sal_uInt32, std::vector<tools::Long>>", text)

    def test_groups_keep_their_order_after_the_popup(self):
        # runtime: check-ribbon-scaling.py "groups keep their order after the chevron popup"
        text = added("hst-ribbon-fold-keeps-order.patch", "vcl/source/control/PriorityMergedHBox.cxx")
        self.assertIn("HstRestoreOrder();", text)
        self.assertIn("reorderWithinParent(nPos++)", text)
        self.assertIn("m_aHstAuthored.clear();", text)

    def test_smaller_rungs_load_smaller_images(self):
        ladder = added("hst-ribbon-ladder-small-images.patch", "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("DataChanged(DataChangedEvent(DataChangedEventType::NONE))", ladder)
        toolbox = added("hst-ribbon-ladder-small-images.patch", "sfx2/source/sidebar/SidebarToolBox.cxx")
        self.assertIn("DataChangedEventType::NONE", toolbox)
        self.assertIn("ChangedIconHandler(nullptr);", toolbox)
        # the size the ladder chose stays: the default size is switched off around the reload
        self.assertLess(toolbox.index("mbUseDefaultButtonSize = false;"), toolbox.index("ChangedIconHandler(nullptr);"))

    def test_search_box_is_accessible(self):
        # runtime: check-ribbon-tab-search-a11y.py
        tabs = added("hst-ribbon-tab-search-a11y.patch", "vcl/source/accessibility/vclxaccessibletabcontrol.cxx")
        self.assertIn('get_id() == u"hst-tab-search"', tabs)
        box = added("hst-ribbon-tab-search-a11y.patch", "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("css::accessibility::XAccessibleAction", box)
        self.assertIn("return RID_STR_ACC_ACTION_CLICK;", box)
        self.assertIn("pBox->OpenSearch(OUString());", box)

    def test_hover_preview_keeps_direct_formatting(self):
        # runtime: check-style-hover-preview.py check 7 (byte-identical flat ODF after a hover)
        text = added("hst-style-hover-preview-keep-direct.patch")
        self.assertIn("PropertyState_DIRECT_VALUE", text)
        self.assertIn("Snapshot(aParagraph);", text)
        self.assertIn("Restore(*it);", text)
        self.assertIn("setPropertyToDefault", text)
        # the style goes back before the direct formatting is set again
        self.assertLess(text.index('setPropertyValue(u"ParaStyleName"_ustr, css::uno::Any(it->aStyle));'),
                        text.index("Restore(*it);"))

    def test_box_lays_out_its_groups_by_their_real_width(self):
        # the smallest width is for the parent only; VclBox::setAllocation must see the real one
        text = added("hst-ribbon-ladder-own-allocation.patch", "vcl/source/control/PriorityMergedHBox.cxx")
        self.assertIn("m_bHstOwnLayout ? -1 : HstMinWidth()", text)
        self.assertIn("void PriorityMergedHBox::setAllocation(const Size& rAllocation)", text)

    def test_nested_merged_box_has_its_own_ladder(self):
        ladder = added("hst-ribbon-ladder-nested-box.patch", "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("dynamic_cast<PriorityMergedHBox*>(pChild)", ladder)
        self.assertIn("/*bNested*/ true", ladder)
        box = added("hst-ribbon-ladder-nested-box.patch", "vcl/source/control/PriorityMergedHBox.cxx")
        self.assertIn("dynamic_cast<const PriorityMergedHBox*>(GetParent())", box)


if __name__ == "__main__":
    unittest.main()
