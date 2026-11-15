# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-styles-gallery-states.patch: Writer's Styles gallery keeps 6, 4, 3 previews at the large, medium and
small group (gap list G05), through the ribbon ladder's "hst-gallery-state" property."""
import unittest

from patch_sections import added

PATCH = "hst-ribbon-styles-gallery-states.patch"


class StylesGalleryStates(unittest.TestCase):
    def test_answers_the_ladder_state(self):
        code = added(PATCH, "svx/source/tbxctrls/StylesPreviewWindow.cxx")
        self.assertIn("constexpr int HST_PREVIEWS[] = { 6, 4, 3 };", code)
        self.assertIn('if (rKey != "hst-gallery-state")', code)
        self.assertIn("return false; // nothing changed", code)  # the ladder lays out again only on a change
        header = added(PATCH, "svx/source/inc/StylesPreviewWindow.hxx")
        self.assertIn("bool set_property(const OUString& rKey, const OUString& rValue) override;", header)


class CompactPixelsOnWindows(unittest.TestCase):
    def test_px_is_tools_long(self):
        # MSVC: long is 32 bit and tools::Long 64 bit, so std::max(tools::Long, long) did not compile
        code = added("hst-ribbon-adaptive-compact.patch", "sfx2/source/notebookbar/HstRibbonCompact.hxx")
        self.assertIn("inline tools::Long px(tools::Long nLogical, double fDpi)", code)


if __name__ == "__main__":
    unittest.main()
