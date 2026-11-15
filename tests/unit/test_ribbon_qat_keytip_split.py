# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-qat-keytip-split.patch: a quick access split button's KeyTip runs its command (Alt+2: Undo)."""
import unittest

from patch_sections import added

PATCH = "hst-ribbon-qat-keytip-split.patch"


class QatKeyTipSplit(unittest.TestCase):
    def test_quick_access_split_button_runs_its_command(self):
        code = added(PATCH, "sfx2/source/notebookbar/HstRibbonKeyTips.cxx")
        self.assertIn("std::to_string(nDigit),\n                                   true))", code)  # the QAT asks for it
        # DROPDOWNONLY (0x00a0) includes the DROPDOWN bit: the split-button test comes first and is exact
        self.assertIn("else if (bMainPart && (nBits & ToolBoxItemBits::DROPDOWNONLY) == ToolBoxItemBits::DROPDOWN", code)
        self.assertLess(code.index("comphelper::dispatchCommand"), code.index("else if (nBits & ToolBoxItemBits::DROPDOWNONLY)"))
        self.assertIn("comphelper::dispatchCommand(xBox->GetItemCommand(nId)", code)
        self.assertIn("bool bMainPart = false", code)  # the ribbon's split buttons keep opening their list


    def test_quick_access_tips_close_before_their_command(self):
        # the tips of the tab level open the next level for a tab only: a quick access command closes them first,
        # else the next Alt closes them instead of showing them (Alt, 2 then Alt, 3 typed the 3; Windows, 15/11)
        code = added("hst-ribbon-qat-keytips-close.patch", "sfx2/source/notebookbar/HstRibbonKeyTips.cxx")
        start = code.index("aTargets.back().aRun = [this, aRun = aTargets.back().aRun] {")
        self.assertLess(code.index("Close();", start), code.index("aRun();", start))


if __name__ == "__main__":
    unittest.main()
