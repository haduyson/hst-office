# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-labels-arrange.patch: Arrange commands of the Layout tabs show their labels (gap list G10)."""
import unittest

from patch_sections import added, sections

PATCH = "hst-ribbon-labels-arrange.patch"


class LabelsArrange(unittest.TestCase):
    def test_icon_only_toolboxes_become_labelled(self):
        for ui, count in (("sw/uiconfig/swriter/ui/notebookbar.ui", 5), ("sc/uiconfig/scalc/ui/notebookbar.ui", 2)):
            code = added(PATCH, ui)
            self.assertEqual(code.count('<property name="toolbar-style">both-horiz</property>'), count, ui)
            removed = [line for line in sections(PATCH)[ui] if line.startswith("-")]
            self.assertEqual(len(removed), count, ui)  # only the toolbar style changes


if __name__ == "__main__":
    unittest.main()
