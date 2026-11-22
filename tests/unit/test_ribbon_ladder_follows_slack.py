# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-ladder-follows-slack.patch: the ribbon's groups are fitted again when the banner's room changes.

The ladder runs in Resize at the box's width plus the slack; a slack change with the box keeping its size gave no
Resize, so the groups stayed fitted at the old width (Sheets › Chèn on Linux at 1920 after 1366: 45 px over)."""
import unittest

from patch_sections import added

PATCH = "hst-ribbon-ladder-follows-slack.patch"
CODE = "vcl/source/control/HstRibbonV3MergedBox.cxx"


class LadderFollowsSlackTest(unittest.TestCase):
    def test_a_new_slack_fits_the_groups_again_at_once(self):
        code = added(PATCH, CODE)
        self.assertIn("if (GetSizePixel().Width() > 0)", code)
        self.assertIn("Resize();", code)

    def test_the_dump_gives_the_fit_width_and_the_widest_large_button(self):
        code = added(PATCH, CODE)
        self.assertIn("m_nHstLadderWidth = nWidth;", code)
        self.assertIn("m_nHstLargeNatural = nLarge <= 0 ? 0 : nLogical;", code)
        self.assertIn('\\"ladder_width\\":', code)
        self.assertIn('\\"large_natural\\":', code)


if __name__ == "__main__":
    unittest.main()
