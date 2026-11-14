# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-sheets-caption-row.patch: Sheets' tab boxes fill the ribbon height, as Writer's do (gap list G06)."""
import unittest

from patch_sections import sections

PATCH = "hst-ribbon-sheets-caption-row.patch"


class SheetsCaptionRow(unittest.TestCase):
    def test_only_the_centring_goes(self):
        lines = sections(PATCH)["sc/uiconfig/scalc/ui/notebookbar.ui"]
        removed = [line for line in lines if line.startswith("-")]
        self.assertEqual(len(removed), 19)
        self.assertTrue(all('<property name="valign">center</property>' in line for line in removed))
        self.assertFalse([line for line in lines if line.startswith("+")])


if __name__ == "__main__":
    unittest.main()
