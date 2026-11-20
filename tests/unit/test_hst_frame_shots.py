# SPDX-License-Identifier: AGPL-3.0-only
"""The frame screenshot tool (tests/runtime/hst_frame_shots.py) without an office: which accessibles are which
frame part, the shot and crop names, and cropping the parts of regions.json out of a window shot."""
import json
import os
import sys
import tempfile
import unittest

from PIL import Image

import _paths  # noqa: F401

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import hst_frame_shot_cases as cases  # noqa: E402
import hst_frame_shots as shots  # noqa: E402


class FrameShotCasesTest(unittest.TestCase):
    def test_parts_are_matched_by_role_and_name(self):
        self.assertTrue(cases.matches("statusbar", "STATUS_BAR", ""))
        self.assertTrue(cases.matches("doctabs", "WINDOW", "Thẻ tài liệu"))
        self.assertTrue(cases.matches("doctabs", "PANEL", "Document Tabs"))
        self.assertTrue(cases.matches("sidebar", "PANEL", "Thanh bên"))
        self.assertFalse(cases.matches("sidebar", "STATUS_BAR", "Thanh bên"))
        self.assertFalse(cases.matches("doctabs", "PANEL", "Sidebar"))

    def test_every_look_and_state(self):
        self.assertEqual(len(cases.LOOKS), 8)
        self.assertIn(("before", "dark", "125"), cases.LOOKS)
        self.assertEqual(set(cases.STATES), {"window", "backstage", "context-menu"})
        parts = {part for state in cases.STATES.values() for part in state}
        self.assertEqual(parts, set(cases.REGIONS))
        self.assertEqual(set(cases.DOCUMENT_VIEW), {factory for factory, _text in cases.APPS.values()})

    def test_names(self):
        look = ("after", "light", "125")
        self.assertEqual(cases.shot_name("writer", "context-menu", look), "writer-context-menu-after-light-125")
        self.assertEqual(cases.crop_name("slides", "ribbon", look), "slides-ribbon-after-light-125")


class CropTest(unittest.TestCase):
    def test_parts_are_cut_out_and_clipped_to_the_shot(self):
        with tempfile.TemporaryDirectory() as out:
            shot = cases.shot_name("writer", "window", ("before", "dark", "100"))
            image = Image.new("RGB", (200, 100), (255, 255, 255))
            image.paste((255, 0, 0), (0, 0, 200, 30))       # the ribbon
            image.paste((0, 0, 255), (0, 90, 200, 100))     # the status bar
            image.save(os.path.join(out, shot + ".png"))
            regions = {shot: {"ribbon": [0, 0, 200, 30], "statusbar": [0, 90, 250, 20], "sidebar": [300, 0, 10, 10]}}
            with open(os.path.join(out, shots.REGIONS_FILE), "w", encoding="utf-8") as dst:
                json.dump(regions, dst)
            self.assertEqual(shots.crop(out), 2)  # the sidebar lies outside the shot
            with Image.open(os.path.join(out, "writer-ribbon-before-dark-100.png")) as ribbon:
                self.assertEqual(ribbon.size, (200, 30))
                self.assertEqual(ribbon.getpixel((100, 15)), (255, 0, 0))
            with Image.open(os.path.join(out, "writer-statusbar-before-dark-100.png")) as status:
                self.assertEqual(status.size, (200, 10))
                self.assertEqual(status.getpixel((5, 5)), (0, 0, 255))

    def test_relative_regions(self):
        self.assertEqual(shots.relative({"ribbon": (110, 220, 50, 20)}, (100, 200)), {"ribbon": [10, 20, 50, 20]})


if __name__ == "__main__":
    unittest.main()
