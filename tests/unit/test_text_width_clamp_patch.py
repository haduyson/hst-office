# SPDX-License-Identifier: AGPL-3.0-only
"""ScTable::InvalidateTextWidth stops at the last allocated column (hst-calc-text-width-clamp.patch).

Columns are allocated lazily; a range up to MaxCol() read past them and crashed (reached through
ScDocument::ModifyStyleSheet when a page style's zoom changes).
"""
import os
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-calc-text-width-clamp.patch")


class TextWidthClampPatchTest(unittest.TestCase):
    def test_range_end_is_clamped_to_allocated_columns(self):
        with open(PATCH, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("+++ b/sc/source/core/data/table5.cxx", text)
        self.assertIn("-    const SCCOL nCol2 = pAdrTo ? pAdrTo->Col() : aCol.size() - 1;", text)
        self.assertIn("+    const SCCOL nCol2 = pAdrTo ? ClampToAllocatedColumns(pAdrTo->Col()) : aCol.size() - 1;", text)

    def test_listed_in_the_series(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            self.assertIn("hst-calc-text-width-clamp.patch", handle.read().split())


if __name__ == "__main__":
    unittest.main()
