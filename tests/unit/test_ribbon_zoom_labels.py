# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-ribbon-zoom-labels.patch: the View tabs' Zoom groups show large labelled buttons where the reference suite
does, and those keep their labels at every width (gap list G10)."""
import re
import unittest

from patch_sections import added

PATCH = "hst-ribbon-zoom-labels.patch"
LARGE = {  # notebookbar -> the boxes laid out large (the reference suite's large Zoom buttons)
    "sw/uiconfig/swriter/ui/notebookbar.ui": ["bxViewZoom100Percent"],
    "sc/uiconfig/scalc/ui/notebookbar.ui": ["bxViewHstZoom", "bxViewZoom100Percent"],  # Zoom to Selection was large
    "sd/uiconfig/simpress/ui/notebookbar.ui": ["bxViewZoomPage", "bxViewZoomPageWidth"],
    "sd/uiconfig/sdraw/ui/notebookbar.ui": ["bxViewZoomPage", "bxViewZoomPageWidth"],
}


class ZoomLabels(unittest.TestCase):
    def test_reference_large_buttons(self):
        for path, boxes in LARGE.items():
            text = open_after(path)
            for box in boxes:
                head = text[text.index(f'id="{box}"'):]
                head = head[:head.index("<child>")]
                self.assertIn('<property name="toolbar-style">both</property>', head, (path, box))
                self.assertIn('<property name="icon_size">3</property>', head, (path, box))

    def test_zoom_group_keeps_large_labelled_buttons(self):
        code = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn('pWindow->get_id() == u"gdViewZoom"', code)
        self.assertIn("rData.meHstAuthoredSize == ToolBoxButtonSize::Large && inZoomGroup(rToolBox)", code)


def open_after(path):
    """The added lines of the patch's hunks for path, with their context: enough to find each box's head."""
    text = open(__import__("os").path.join(__import__("_paths").ROOT, "patches", "libreoffice", PATCH),
                encoding="utf-8").read()
    section = text[text.index(f"+++ b/{path}"):]
    end = section.find("\n--- a/", 1)
    section = section if end < 0 else section[:end]
    return "\n".join(line[1:] for line in section.splitlines()[1:] if line[:1] in (" ", "+"))


if __name__ == "__main__":
    unittest.main()
