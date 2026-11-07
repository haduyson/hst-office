# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel judgement of check-nd30-type-list.py: whether the open type list is visible in a band of a screenshot.

Each image is judged on its own: a band that is already covered before the pointer moves must fail, never relax the
threshold for the next image."""
import os
import sys
import tempfile
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import nd30_type_list_pixels as px  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - the runtime checks need Pillow anyway
    Image = None


@unittest.skipIf(Image is None, "Pillow missing")
class Visibility(unittest.TestCase):
    def shot(self, covered):
        """40 px band: list rows of text, or an empty white field painted over them."""
        image = Image.new("RGB", (200, 40), "white")
        if not covered:
            draw = ImageDraw.Draw(image)
            for y in range(0, 40, 2):
                draw.line((10 + y, y, 150, y), fill="black")
        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        image.save(path)
        self.addCleanup(os.remove, path)
        return path

    def test_list_rows_are_visible_and_a_field_box_is_not(self):
        box = (0, 0, 200, 40)
        self.assertTrue(px.list_visible(self.shot(False), box))
        self.assertFalse(px.list_visible(self.shot(True), box))

    def test_an_obscured_baseline_fails_on_its_own(self):
        box = (0, 0, 200, 40)
        before, after = self.shot(True), self.shot(True)
        problems = px.visibility_problems({"before": before, "after": after}, box)
        self.assertEqual(sorted(problems), ["after", "before"])
        self.assertEqual(px.visibility_problems({"before": self.shot(False), "after": self.shot(False)}, box), [])


    def test_a_repaint_is_any_pixel_change_of_the_band(self):
        box = (0, 0, 200, 40)
        rows, field = self.shot(False), self.shot(True)
        self.assertTrue(px.unchanged(rows, self.shot(False), box))
        self.assertFalse(px.unchanged(rows, field, box))


if __name__ == "__main__":
    unittest.main()
