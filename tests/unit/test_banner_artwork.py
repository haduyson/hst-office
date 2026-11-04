# SPDX-License-Identifier: AGPL-3.0-only
"""Owner-supplied source, extracted lettering, shared mark and distinct Post palette."""
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageColor

from _paths import ROOT

ART = Path(ROOT) / "extensions/hst-vietnamese-tools/banners"
SVG = "{http://www.w3.org/2000/svg}"
OFFICIAL_SHA256 = "2f77a5fce52a515d52333cca3879a0aec18e582628a7111c00a05714b1c4d2ef"


def mask(image):
    return {i for i, alpha in enumerate(image.getchannel("A").getdata()) if alpha > 128}


def largest_component(image):
    """Remove neighbouring glyph fringes that enter an italic glyph's bounding box."""
    remaining, components, width = mask(image), [], image.width
    while remaining:
        group, pending = set(), [remaining.pop()]
        while pending:
            point = pending.pop()
            group.add(point)
            for neighbour in (point - 1, point + 1, point - width, point + width):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    pending.append(neighbour)
        components.append(group)
    return max(components, key=len)


class ArtworkTests(unittest.TestCase):
    def test_official_owner_source_is_unchanged(self):
        source = ART / "logos/hasontech.png"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), OFFICIAL_SHA256)
        with Image.open(source) as image:
            self.assertEqual(image.size, (476, 393))
            self.assertEqual(image.mode, "RGBA")
        self.assertEqual((ART / "SOURCES.md").read_bytes(), (Path(ROOT) / "assets/banners/SOURCES.md").read_bytes())

    def test_logo_and_square_share_the_same_vector_mark(self):
        full = ET.parse(ART / "logos/hst-post.svg").getroot()
        icon = ET.parse(ART / "logos/hst-post-icon.svg").getroot()
        favicon = ET.parse(Path(ROOT) / "assets/hst-post/favicon.svg").getroot()
        def mark(root):
            return root.find(f".//{SVG}g[@id='company-mark']")
        for root in (full, icon, favicon):
            self.assertEqual(ET.tostring(mark(full)), ET.tostring(mark(root)))
            self.assertEqual(mark(root).get("fill"), "#0072bb")
            self.assertEqual(root.findall(f".//{SVG}image"), [])
            self.assertEqual(root.findall(f".//{SVG}text"), [])
        self.assertEqual(full.find(SVG + "title").text, "HST POST")
        wordmark = full.find(f".//{SVG}g[@id='wordmark']")
        self.assertEqual(wordmark.get("fill"), "#322e2e")
        self.assertEqual(''.join(p.get("data-letter") for p in wordmark), "HSTPOST")
        self.assertTrue(all(p.get("fill") is None for p in wordmark))
        self.assertIsNone(icon.find(f".//{SVG}g[@id='wordmark']"))

    def test_png_dimensions_and_transparency(self):
        for file, size in (("hst-post-512.png", (512, 423)), ("hst-post-1024.png", (1024, 845)),
                           ("hst-post-icon-512.png", (512, 512))):
            with Image.open(ART / "logos" / file) as image:
                self.assertEqual(image.size, size)
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_trace_preserves_official_mark_silhouette(self):
        with Image.open(ART / "logos/hasontech.png") as original, Image.open(ART / "logos/hst-post-1024.png") as logo:
            expected = mask(original.crop((0, 0, 476, 290)))
            actual = mask(logo.resize((476, 393), Image.Resampling.LANCZOS).crop((0, 0, 476, 290)))
        self.assertGreater(len(expected & actual) / len(expected | actual), .998)

    def test_letter_shapes_match_the_official_wordmark(self):
        # Independent source coordinates and positions in the final wordmark: catches font substitution.
        with Image.open(ART / "logos/hasontech.png") as original, Image.open(ART / "logos/hst-post-1024.png") as logo:
            logo = logo.resize((476, 393), Image.Resampling.LANCZOS)
            for char, source_x, dest_x, width in (("H", 26, 68, 45), ("S", 114, 112, 45),
                                                  ("T", 272, 156, 40), ("O", 159, 260, 45)):
                expected = largest_component(original.crop((source_x, 304, source_x + width, 354)))
                actual = mask(logo.crop((dest_x, 304, dest_x + width, 354)))
                with self.subTest(letter=char):
                    self.assertGreater(len(expected & actual) / len(expected | actual), .98)

    def test_post_icon_and_violet_palette_reach_generated_assets(self):
        brands = json.loads((ART / "brands.json").read_text())
        post = brands["hst-post"]
        self.assertEqual(post["logo"], "hst-post-icon.svg")
        self.assertEqual(post["logoWidth"], 30)
        self.assertEqual(post["accent"], "#6d28d9")
        self.assertNotEqual(post["accent"], brands["hst-seo"]["accent"])
        for path in [ART / f"hst-post@{scale}x.png" for scale in (1, 2, 3)] + [
            Path(ROOT) / "assets/hst-post" / name for name in
            ("og-hst-post.png", "og-hst-post@2x.png", "og-hst-post-square.png")
        ]:
            with Image.open(path) as image:
                count = sum(pixel == ImageColor.getrgb(post["accent"]) for pixel in image.convert("RGB").getdata())
                self.assertGreater(count, 100, path)
        for name in ("favicon-32.png", "apple-touch-icon.png", "icon-512.png"):
            with Image.open(Path(ROOT) / "assets/hst-post" / name) as image:
                self.assertEqual(image.getpixel((0, 0)), ImageColor.getrgb(post["tint"]))
