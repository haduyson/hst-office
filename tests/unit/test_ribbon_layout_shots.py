# SPDX-License-Identifier: AGPL-3.0-only
"""Geometry measured by check-ribbon-layout.py --shots on synthetic screenshots: the ribbon body's height, the
caption line of the groups and the 1 px separators of the approved 1.0.2 mockup (body 106 px, separators 6 px under
its top and over its bottom, one caption line for every tab)."""
import importlib.util
import os
import tempfile
import unittest

from _paths import ROOT

spec = importlib.util.spec_from_file_location("check_ribbon_layout",
                                              os.path.join(ROOT, "scripts", "patches", "check-ribbon-layout.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

TOP = 45  # first row of the body in the synthetic shots (the tab row above it)
WINDOW = (246, 245, 244)
PAGE = (255, 255, 255)
SEPARATOR = (196, 196, 196)


class ShotGeometryTest(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is not installed")
        self.Image, self.Draw = Image, ImageDraw

    def shot(self, body=106, inset=6, separator=1, caption=None):
        """A 1366 px window top: the page left of a 260 px banner, two groups split by a separator, a caption."""
        image = self.Image.new("RGB", (1366, 250), WINDOW)
        draw = self.Draw.Draw(image)
        draw.rectangle((9, TOP, 1366 - 10 - 268, TOP + body - 1), fill=PAGE)
        draw.rectangle((1366 - 5 - 260, 66, 1366 - 6, 140), fill=(240, 247, 252))
        draw.rectangle((300, TOP + inset, 300 + separator - 1, TOP + body - 1 - inset), fill=SEPARATOR)
        line = TOP + body - 9 if caption is None else TOP + caption
        for left in (100, 400):  # caption text: x-height rows above the baseline, a descender under it
            draw.rectangle((left, line - 7, left + 60, line), fill=(60, 60, 60))
            draw.rectangle((left + 5, line + 1, left + 7, line + 3), fill=(60, 60, 60))
        return image

    def measure(self, image):
        captions = {}
        failures = check.geometry_failures("writer-w1366-home.png", image, 106, captions)
        return failures, captions.get("writer-w1366-home.png")

    def test_mockup_geometry_holds(self):
        image = self.shot()
        self.assertEqual(check.body(image), (TOP, 106))
        self.assertEqual(check.separators(image, TOP, 106), [(300, 1, 6, 99)])
        self.assertEqual(self.measure(image), ([], 97))

    def test_body_and_separator_failures(self):
        self.assertIn("ribbon body 124 px high", self.measure(self.shot(body=124))[0][0])
        [failure] = self.measure(self.shot(inset=9, separator=2))[0]
        self.assertIn("2 px wide, rows 9-96", failure)

    def test_caption_line_compared_between_shots(self):
        captions = {"a": 97, "b": 97, "c": 98, "d": 100, "e": None}
        self.assertEqual([f.split(":")[0] for f in check.caption_failures(captions)], ["d"])

    def test_check_shots_counts_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            self.shot().save(os.path.join(folder, "writer-w1366-home.png"))
            self.shot(caption=94).save(os.path.join(folder, "writer-w1366-insert.png"))
            self.shot().save(os.path.join(folder, "writer-w1485-home.png"))
            self.assertEqual(check.check_shots(folder, 200, 2000), 1)


if __name__ == "__main__":
    unittest.main()
