# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-sheets-caption-row.patch: Sheets' tab boxes take Writer's geometry (gap list G06)."""
import unittest

from patch_sections import sections

PATCH = "hst-ribbon-sheets-caption-row.patch"


class SheetsCaptionRow(unittest.TestCase):
    def test_only_the_centring_goes(self):
        lines = sections(PATCH)["sc/uiconfig/scalc/ui/notebookbar.ui"]
        removed = [line for line in lines if line.startswith("-")]
        self.assertEqual(len(removed), 19)
        self.assertTrue(all('<property name="valign">center</property>' in line for line in removed))
        added = [line for line in lines if line.startswith("+")]
        # Writer's geometry: 2 px above and below the tab box (its groups at y 52, captions at 141 for 1485 px)
        self.assertEqual(sum('<property name="margin-top">2</property>' in line for line in added), 19)
        self.assertEqual(sum('<property name="margin-bottom">2</property>' in line for line in added), 19)
        self.assertEqual(len(added), 38)


if __name__ == "__main__":
    unittest.main()
