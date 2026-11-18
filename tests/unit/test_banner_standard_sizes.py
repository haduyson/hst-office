# SPDX-License-Identifier: AGPL-3.0-only
"""Standard banner sizes ("sizes": 360/640/960 x 96 at 1x and 2x) in the version 1 banner manifest, and the
publisher's validator scripts/brand/validate-banner-manifest.py."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from _paths import ROOT

from banner_fixtures import manifest as online_manifest
from hst_office import banner_schema as schema
from hst_office import banner_sizes as sizes
from hst_office.banner_verify import verify_image

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is part of the developer requirements
    Image = None

SPEC = importlib.util.spec_from_file_location("validate_banner_manifest",
                                              Path(ROOT) / "scripts/brand/validate-banner-manifest.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
BASE = "https://system.hasontech.vn/hst-office/banners/"


def picture(width, height, kind="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (width, height), "#1d5fa8").save(out, format=kind)
    return out.getvalue()


def descriptor(name, data):
    return {"url": BASE + name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def standard_sizes(banner_id, files=None, kind="PNG"):
    """The "sizes" list of `banner_id`; `files` (dict) receives name -> bytes of each generated image."""
    result = []
    for width in sizes.WIDTHS:
        entry = {"width": width, "height": sizes.HEIGHT}
        for factor, scale in ((1, "1x"), (2, "2x")):
            name = "%s-%dx96@%s.%s" % (banner_id, width, scale, "png" if kind == "PNG" else "jpg")
            data = picture(width * factor, 96 * factor, kind) if Image else b"x" * 100
            entry[scale] = descriptor(name, data)
            if files is not None:
                files[name] = data
        result.append(entry)
    return result


def parse(doc, bundled=False):
    return schema.parse_manifest(json.dumps(doc).encode(), bundled=bundled)


class StandardSizeSchemaTests(unittest.TestCase):
    def test_owner_locked_constants(self):
        self.assertEqual(sizes.WIDTHS, (360, 640, 960))
        self.assertEqual(sizes.HEIGHT, 96)
        self.assertEqual(sizes.SAFE_ZONE, 360)
        self.assertEqual(sizes.MAX_IMAGE, 300 * 1024)
        self.assertEqual([sizes.pixel_size(sizes.size_key(w, s)) for w in sizes.WIDTHS for s in sizes.SCALES],
                         [(360, 96), (720, 192), (640, 96), (1280, 192), (960, 96), (1920, 192)])

    def test_optional_field_keeps_schema_one_and_legacy_image(self):
        doc = online_manifest()
        self.assertFalse(any(sizes.has_sizes(i) for i in parse(doc)["items"]))
        doc["items"][0]["sizes"] = standard_sizes(doc["items"][0]["id"])
        parsed = parse(doc)
        self.assertEqual(parsed["schemaVersion"], 1)
        item = next(i for i in parsed["items"] if i["id"] == doc["items"][0]["id"])
        self.assertEqual([k for k, _ in sizes.size_specs(item)],
                         ["360@1x", "360@2x", "640@1x", "640@2x", "960@1x", "960@2x"])
        # the legacy fields stay mandatory, so the same manifest still serves 1.0.2 clients
        self.assertEqual([k for k, _ in schema.image_specs(item)][:3], ["1x", "2x", "3x"])
        del doc["items"][0]["image"]
        with self.assertRaises(ValueError):
            parse(doc)

    def test_every_standard_size_once_in_order(self):
        doc = online_manifest()
        good = standard_sizes("aios")
        broken = {
            "missing width": good[:2],
            "wrong order": [good[1], good[0], good[2]],
            "duplicate": [good[0], good[0], good[2]],
            "wrong height": [dict(good[0], height=104), good[1], good[2]],
            "boolean width": [dict(good[0], width=True), good[1], good[2]],
            "missing 2x": [{k: v for k, v in good[0].items() if k != "2x"}, good[1], good[2]],
            "3x is not standard": [dict(good[0], **{"3x": good[0]["2x"]}), good[1], good[2]],
            "not a list": {"360": good[0]},
            "webp file": [dict(good[0], **{"1x": dict(good[0]["1x"], url=BASE + "a.webp")}), good[1], good[2]],
            "foreign host": [dict(good[0], **{"1x": dict(good[0]["1x"], url="https://evil.example/a.png")}),
                             good[1], good[2]],
            "over 300 KB": [dict(good[0], **{"1x": dict(good[0]["1x"], size=300 * 1024 + 1)}), good[1], good[2]],
        }
        for label, value in broken.items():
            with self.subTest(label):
                bad = copy.deepcopy(doc)
                bad["items"][0]["sizes"] = value
                with self.assertRaises(ValueError):
                    parse(bad)

    def test_bundled_paths(self):
        doc = json.loads((Path(ROOT) / "data/hst/banners.json").read_text())
        item = doc["items"][0]
        item["sizes"] = standard_sizes(item["id"])
        for entry in item["sizes"]:
            for scale in sizes.SCALES:
                entry[scale]["url"] = entry[scale]["url"].replace(BASE, "banners/")
        parse(doc, bundled=True)
        item["sizes"][0]["1x"]["url"] = "../banners/x-360x96@1x.png"
        with self.assertRaises(ValueError):
            parse(doc, bundled=True)

    def test_fit_width_largest_that_fits_never_stretched(self):
        cases = {200: 360, 359: 360, 360: 360, 639: 360, 640: 640, 959: 640, 960: 960, 2560: 960}
        for available, width in cases.items():
            self.assertEqual(sizes.fit_width(available), width, available)


@unittest.skipIf(Image is None, "Pillow not installed")
class StandardSizeImageTests(unittest.TestCase):
    def test_exact_dimensions_per_key(self):
        data = picture(1280, 192)
        spec = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        self.assertEqual(verify_image(data, spec, "640@2x"), ".png")
        for wrong in ("640@1x", "960@2x", "1x"):
            with self.assertRaises(ValueError):
                verify_image(data, spec, wrong)

    def test_validator_manifest_with_assets(self):
        doc, files = online_manifest(), {}
        for item in doc["items"]:
            item["sizes"] = standard_sizes(item["id"], files, kind="JPEG" if item["id"] == "aios" else "PNG")
        art = Path(ROOT) / "extensions/hst-vietnamese-tools"
        with tempfile.TemporaryDirectory() as tmp:
            for item in doc["items"]:
                for _, spec in schema.image_specs(item):
                    name = spec["url"].rsplit("/", 1)[-1]
                    (Path(tmp) / name).write_bytes((art / "banners" / name).read_bytes())
            for name, data in files.items():
                (Path(tmp) / name).write_bytes(data)
            path = Path(tmp) / "banners.json"
            path.write_text(json.dumps(doc))
            self.assertEqual(validator.check_manifest(path, tmp, require_sizes=True), [])
            Path(tmp, "echatbot-960x96@2x.png").write_bytes(picture(1920, 190))
            problems = validator.check_manifest(path, tmp)
            self.assertTrue(any("echatbot 960@2x" in p and "SHA-256" in p for p in problems), problems)
            self.assertTrue(any("required size 1920x192" in p for p in problems), problems)

    def test_validator_requires_sizes_for_new_campaigns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "banners.json"
            path.write_text(json.dumps(online_manifest()))
            self.assertEqual(validator.check_manifest(path), [])
            self.assertEqual(len(validator.check_manifest(path, require_sizes=True)), 2)

    def test_validator_campaign_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {}
            standard_sizes("acme", files)
            for name, data in files.items():
                (Path(tmp) / name).write_bytes(data)
            self.assertEqual(validator.check_campaign(tmp, "acme"), [])
            self.assertEqual(validator.main(["--campaign", tmp, "--id", "acme"]), 0)
            Path(tmp, "acme-640x96@1x.png").unlink()
            Path(tmp, "acme-960x96@1x.png").write_bytes(picture(960, 96, "WEBP"))
            Path(tmp, "acme-360x96@2x.png").write_bytes(b"\x89PNG" + b"\0" * (300 * 1024))
            problems = validator.check_campaign(tmp, "acme")
            self.assertTrue(any(p.startswith("acme-640x96@1x: missing") for p in problems), problems)
            self.assertTrue(any("must be PNG or JPEG" in p for p in problems), problems)
            self.assertTrue(any("larger than 300 KB" in p for p in problems), problems)
            self.assertEqual(validator.main(["--campaign", tmp, "--id", "acme"]), 1)
            self.assertEqual(validator.main([]), 2)


if __name__ == "__main__":
    unittest.main()
