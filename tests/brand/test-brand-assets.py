"""Brand asset tests: source untouched, mark pixel-identical, sizes, reproducibility."""
import hashlib
import json
import os
import subprocess
import sys
import unittest

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(ROOT, "assets", "brand", "brand-spec.json"), encoding="utf-8") as fh:
    SPEC = json.load(fh)


def path(rel):
    return os.path.join(ROOT, rel)


class BrandAssetTests(unittest.TestCase):
    def test_source_logo_unchanged(self):
        with open(path(SPEC["source"]["path"]), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), SPEC["source"]["sha256"])

    def test_mark_pixels_identical_in_logo_and_mark(self):
        box = tuple(SPEC["mark"]["box"])
        source = Image.open(path(SPEC["source"]["path"])).convert("RGBA").crop(box)
        logo = Image.open(path(SPEC["outputs"]["logo"])).convert("RGBA").crop(box)
        mark = Image.open(path(SPEC["outputs"]["mark"])).convert("RGBA")
        # Compare raw RGBA bytes: getbbox() on RGBA only inspects alpha.
        self.assertEqual(source.tobytes(), logo.tobytes())
        self.assertEqual(source.size, mark.size)
        self.assertEqual(source.tobytes(), mark.tobytes())
        self.assertIsNone(ImageChops.difference(source, logo).getbbox(alpha_only=False))

    def test_old_wordmark_removed_and_new_text_inside_box(self):
        logo = Image.open(path(SPEC["outputs"]["logo"])).convert("RGBA")
        self.assertEqual(logo.size, tuple(SPEC["source"]["size"]))
        text_area = logo.crop(tuple(SPEC["replacedText"]["box"]))
        self.assertIsNotNone(text_area.getbbox(), "new wordmark must be drawn")
        # Nothing may be drawn outside the mark box and the text box.
        mask = logo.getchannel("A").copy()
        for box in (SPEC["mark"]["box"], SPEC["replacedText"]["box"]):
            mask.paste(0, tuple(box))
        self.assertIsNone(mask.getbbox())

    def test_icon_sizes(self):
        for size in SPEC["outputs"]["iconSizes"]:
            icon = Image.open(path(SPEC["outputs"]["iconPattern"].format(size=size)))
            self.assertEqual(icon.size, (size, size))
            self.assertEqual(icon.mode, "RGBA")

    def test_generator_reproducible(self):
        script = path("scripts/generate-brand-assets.py")
        result = subprocess.run([sys.executable, script, "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
