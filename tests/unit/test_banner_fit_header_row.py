# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""check-banner-fit.py's tab-row rule on synthetic screenshots: the ribbon's tab row must be one surface from the
first tab title to the window's right edge, every title on it.

A header band that stops part-way (the gtk native tab header drawn only as wide as the ribbon's page) leaves the later
titles on the tab control's own background: the rule fails. A band across the whole row passes, with the search box
and the menu button (opaque widgets of the row) and Tệp tin (a coloured button) left out.
"""
import importlib.util
import os
import tempfile
import unittest

from _paths import ROOT

try:
    from PIL import Image, ImageDraw
    import numpy  # noqa: F401  (check-banner-fit needs it)
except ImportError:  # pragma: no cover - the runtime checks' dependencies
    Image = None

FRAME = [0, 0, 1000, 600]
HEADER, OTHER, TEXT = (225, 225, 225), (246, 246, 246), (40, 40, 40)
TITLES = [("Tệp tin", (10, 0, 70, 35))] + [(f"Thẻ {i}", (80 + 90 * i, 0, 90, 35)) for i in range(8)]
WIDGETS = [(800, 3, 140, 30), (950, 3, 40, 30)]  # search box, menu button


def load_fit():
    path = os.path.join(ROOT, "tests", "runtime", "check-banner-fit.py")
    spec = importlib.util.spec_from_file_location("check_banner_fit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(Image is None, "Pillow and numpy are needed")
class HeaderRowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fit = load_fit()

    def shot(self, header_right):
        image = Image.new("RGB", (FRAME[2], FRAME[3]), OTHER)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, header_right, 35), fill=HEADER)
        draw.rectangle((10, 2, 79, 32), fill=(30, 100, 200))  # Tệp tin
        for _name, (x, y, w, h) in TITLES[1:]:
            draw.rectangle((x + 20, 14, x + w - 20, 21), fill=TEXT)
        for x, y, w, h in WIDGETS:
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=(255, 255, 255))
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.close()
        image.save(handle.name)
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_band_across_the_row_passes(self):
        ok, detail = self.fit.header_continuous(self.shot(FRAME[2] - 1), TITLES, WIDGETS, FRAME)
        self.assertTrue(ok, detail)

    def test_band_stopping_part_way_fails(self):
        ok, detail = self.fit.header_continuous(self.shot(530), TITLES, WIDGETS, FRAME)
        self.assertFalse(ok)
        self.assertIn("Thẻ 6", detail)
        self.assertIn("off the header", detail)

    def test_row_widgets_keeps_only_the_row(self):
        tabs = [box for _name, box in TITLES]
        ribbon_button = (100, 60, 30, 30)
        whole_window = (0, 0, 1000, 35)
        kept = self.fit.row_widgets(list(WIDGETS) + [ribbon_button, whole_window], tabs, FRAME)
        self.assertEqual(kept, list(WIDGETS))


if __name__ == "__main__":
    unittest.main()
