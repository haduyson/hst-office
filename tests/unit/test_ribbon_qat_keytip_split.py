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


if __name__ == "__main__":
    unittest.main()
