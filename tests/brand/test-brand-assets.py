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

    def test_app_icons_all_sizes_and_transparent(self):
        cfg = SPEC["appIcons"]
        names = [cfg["productName"]] + [m["name"] for m in cfg["modules"]]
        for name in names:
            for size in cfg["sizes"]:
                icon = Image.open(path(cfg["pattern"].format(name=name, size=size)))
                self.assertEqual((icon.size, icon.mode), ((size, size), "RGBA"))
                self.assertEqual(icon.getpixel((0, size - 1))[3], 0, "corner must stay transparent")

    def test_module_icons_differ_from_each_other(self):
        cfg = SPEC["appIcons"]
        raw = {m["name"]: Image.open(path(cfg["pattern"].format(name=m["name"], size=128))).tobytes()
               for m in cfg["modules"]}
        self.assertEqual(len(set(raw.values())), len(raw))

    def test_lockup_embeds_native_mark_pixels(self):
        import base64, io, re
        svg = open(path("branding/libreoffice/logo.svg"), encoding="utf-8").read()
        png = Image.open(io.BytesIO(base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", svg).group(1))))
        pad = SPEC["libreofficeBranding"]["lockupPad"]
        mark = Image.open(path(SPEC["outputs"]["mark"])).convert("RGBA")
        crop = png.convert("RGBA").crop((pad, pad, pad + mark.width, pad + mark.height))
        self.assertEqual(crop.tobytes(), mark.tobytes())

    def test_platform_icon_containers(self):
        plat = SPEC["platformIcons"]
        ico = Image.open(path(plat["ico"]))
        self.assertEqual(set(ico.info["sizes"]), {(s, s) for s in plat["icoSizes"]})
        self.assertEqual(open(path(plat["icns"]), "rb").read(4), b"icns")

    def test_generator_reproducible(self):
        script = path("scripts/generate-brand-assets.py")
        result = subprocess.run([sys.executable, script, "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
