# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-equal-height.patch: one ribbon height in Writer, Sheets, Slides and Draw (gap list G06)."""
import unittest

from patch_sections import added

PATCH = "hst-ribbon-equal-height.patch"


class EqualHeight(unittest.TestCase):
    def test_full_ribbon_requests_the_shared_height(self):
        code = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("constexpr double HST_RIBBON_HEIGHT = 165;", code)
        # only the full ribbon: the compact one keeps its tab row and quick row
        self.assertIn("    else // HST Office: one ribbon height in every app", code)
        self.assertIn("std::lround(HST_RIBBON_HEIGHT * GetDPIScaleFactor())", code)


if __name__ == "__main__":
    unittest.main()
