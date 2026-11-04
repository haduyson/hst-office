# SPDX-License-Identifier: AGPL-3.0-only
"""Owner-requested logo deliverables retain the company mark and use real vector paths."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from PIL import Image

from _paths import ROOT

ART = Path(ROOT) / "extensions/hst-vietnamese-tools/banners"
SVG = "{http://www.w3.org/2000/svg}"


class ArtworkTests(unittest.TestCase):
    def test_logo_and_square_share_the_same_vector_mark(self):
        full = ET.parse(ART / "logos/hst-post.svg").getroot()
        icon = ET.parse(ART / "logos/hst-post-icon.svg").getroot()
        def mark(root):
            return root.find(f".//{SVG}g[@id='company-mark']")
        self.assertEqual(ET.tostring(mark(full)), ET.tostring(mark(icon)))
        self.assertEqual(mark(full).get("fill"), "#0072bb")
        for root in (full, icon):
            self.assertEqual(root.findall(f".//{SVG}image"), [])
            self.assertEqual(root.findall(f".//{SVG}text"), [])  # portable outlined lettering
        self.assertEqual(full.find(SVG + "title").text, "HST POST")
        self.assertEqual(json.loads((ART / "brands.json").read_text())["hst-post"]["logo"], "hst-post.svg")

    def test_png_dimensions_and_transparency(self):
        for file, size in (("hst-post-512.png", (512, 374)), ("hst-post-1024.png", (1024, 748)),
                           ("hst-post-icon-512.png", (512, 512))):
            with Image.open(ART / "logos" / file) as image:
                self.assertEqual(image.size, size)
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_trace_preserves_original_mark_silhouette(self):
        with Image.open(ART / "logos/hasontech.png") as original, Image.open(ART / "logos/hst-post-1024.png") as logo:
            expected = original.convert("RGBA").crop((0, 0, 460, 260))
            actual = logo.resize((460, 336), Image.Resampling.LANCZOS).crop((0, 0, 460, 260))
        def mask(image):
            return [a > 128 and b > 100 and r < 50 for r, g, b, a in image.getdata()]
        pairs = list(zip(mask(expected), mask(actual)))
        overlap = sum(a and b for a, b in pairs) / sum(a or b for a, b in pairs)
        self.assertGreater(overlap, .998)  # tolerates edge antialiasing only, not a redesigned triangle
