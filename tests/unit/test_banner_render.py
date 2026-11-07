# SPDX-License-Identifier: AGPL-3.0-only
"""Offline banner composition and optional illustration without a browser."""
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

from PIL import Image, ImageFont

from _paths import ROOT

SPEC = importlib.util.spec_from_file_location("render_banners", Path(ROOT) / "scripts/brand/render-banners.py")
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)
ART = RENDERER.ART


class Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class BannerRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.brands = json.loads((ART / "brands.json").read_text())
        cls.solutions = json.loads((Path(ROOT) / "data/hst/solutions.json").read_text())["solutions"]
        cls.solutions.append(dict(id="hasontech", **{k: cls.brands["hasontech"][k] for k in ("name", "tagline")}))

    def test_only_echatbot_wide_uses_local_decorative_illustration(self):
        for solution in self.solutions:
            for template in ("template.html", "template-compact.html"):
                with self.subTest(brand=solution["id"], template=template):
                    markup = RENDERER.markup(solution, self.brands[solution["id"]], template)
                    tags = Elements(markup).tags
                    images = [attrs for tag, attrs in tags if tag == "img" and attrs.get("class") == "illustration"]
                    expected = solution["id"] == "echatbot" and template == "template.html"
                    self.assertEqual(len(images), int(expected))
                    self.assertNotIn("https://", markup)
                    self.assertNotIn("http://", markup)
                    self.assertNotIn("$illustration", markup)
                    if expected:
                        self.assertEqual(images[0]["src"], (ART / "logos/echatbot-chibi.png").as_uri())
                        self.assertEqual(images[0]["alt"], "")
                        self.assertEqual(images[0]["aria-hidden"], "true")
                        self.assertIn(solution["tagline"], markup)
                        self.assertIn("HASON TECH", markup)

    def test_illustration_is_opt_in_and_compact_markup_is_unchanged(self):
        for solution in self.solutions:
            brand = dict(self.brands[solution["id"]])
            brand.pop("illustration", None)
            plain = {t: RENDERER.markup(solution, brand, t) for t in ("template.html", "template-compact.html")}
            brand["illustration"] = "echatbot-chibi.png"
            self.assertIn('class="illustration"', RENDERER.markup(solution, brand))
            self.assertEqual(RENDERER.markup(solution, brand, "template-compact.html"), plain["template-compact.html"])
            brand["illustration"] = ""
            self.assertEqual(RENDERER.markup(solution, brand), plain["template.html"])

    def test_chibi_asset_preserves_alpha_at_three_times_banner_height(self):
        path = ART / "logos/echatbot-chibi.png"
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (312, 312))
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
        self.assertLess(path.stat().st_size, 110 * 1024)

    def test_full_echatbot_tagline_fits_two_lines_with_bundled_font(self):
        # Measure at 10x for the fractional 12.5px font. Browser bounds remain the render-time gate.
        font = ImageFont.truetype(str(RENDERER.FONT / "BeVietnamPro-Regular.ttf"), 125)
        solution = next(s for s in self.solutions if s["id"] == "echatbot")
        width = 360 - 2 - 14 - 104 - 10  # border, left inset, illustration and clear gap
        lines = [""]
        for word in solution["tagline"].split():
            candidate = (lines[-1] + " " + word).strip()
            if font.getlength(candidate) / 10 > width:
                lines.append(word)
            else:
                lines[-1] = candidate
        self.assertEqual(" ".join(lines), solution["tagline"])
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(font.getlength(line) / 10 <= width for line in lines))
        self.assertLessEqual(41 + 17 * len(lines), 76)


if __name__ == "__main__":
    unittest.main()
