# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-tabs-fit-row.patch: in a narrow window no ribbon tab runs under the menu button."""
import unittest

from patch_sections import added

PATCH = "hst-ribbon-tabs-fit-row.patch"


class TabsFitRow(unittest.TestCase):
    def test_a_tab_past_the_row_end_is_left_off(self):
        code = added(PATCH, "vcl/source/control/tabctrl.cxx")
        # the row ends before the menu button, leaving the search box's magnifier and its two gaps
        self.assertIn("const tools::Long nRowEnd = nMaxWidth - 2 * nHstGap - std::lround(32 * fHstDpi);", code)
        self.assertIn("item.maRect = tools::Rectangle();", code)  # not drawn, no clicks (ImplDrawItem, GetPageId)
        # the search box starts after the last tab shown
        self.assertIn("nX = std::max(nX, item.maRect.Right() + 1);", code)


if __name__ == "__main__":
    unittest.main()
