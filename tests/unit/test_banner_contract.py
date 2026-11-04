# SPDX-License-Identifier: AGPL-3.0-only
import copy
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from _paths import ROOT
from banner_fixtures import KEY, NOW, VERSION, image_spec, manifest, signed
from hst_office import banner_schema as schema, banner_verify as verify
from hst_office.banner_urls import FEED_URL, allowed_url, click_url, feed_url
from hst_office.data_files import load_data


class BannerContractTests(unittest.TestCase):
    def parse(self, doc):
        return schema.parse_manifest(json.dumps(doc).encode())

    def test_signature_ok(self):
        self.assertEqual(verify.verify_manifest(*signed(manifest()), KEY)["schemaVersion"], 1)

    def test_signature_bad_or_missing(self):
        data, signature = signed(manifest())
        for payload, sig in ((data + b" ", signature), (data, b""), (data, b"%%%"), (data, b"A" * 200)):
            with self.subTest(sig=sig[:8]), self.assertRaises(ValueError):
                verify.verify_manifest(payload, sig, KEY)

    def test_placeholder_fails_closed(self):
        with self.assertRaises(ValueError):
            verify.verify_manifest(*signed(manifest()), public_key=b"")

    def test_signature_before_schema(self):
        data, signature = signed({"not": "a manifest"})
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify.verify_manifest(data, signature, KEY)

    def test_manifest_limits(self):
        cases = [("schemaVersion", True), ("schemaVersion", 2), ("items", []), ("items", [manifest()["items"][0]] * 25),
                 ("generatedAt", "2026-02-31T00:00:00Z"), ("generatedAt", "2026-11-04"), ("rotateSeconds", True)]
        for field, value in cases:
            doc = manifest(); doc[field] = value
            with self.subTest(field=field, value=str(value)[:30]), self.assertRaises(ValueError):
                self.parse(doc)
        for data in (b"x" * 65537, b"\xff", b'[]', b'{"schemaVersion":1,"schemaVersion":1}', b'{"n": NaN}'):
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                schema.parse_manifest(data)

    def test_item_limits(self):
        changes = [("id", "../oops"), ("name", "x" * 81), ("tagline", "x" * 161), ("name", "A\nB"),
                   ("weight", 0), ("weight", 11), ("weight", True), ("order", -1), ("order", 10000),
                   ("minVersion", "1.0"), ("image", {}), ("url", "https://evil.example")]
        for field, value in changes:
            doc = manifest(); doc["items"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.parse(doc)
        doc = manifest(); doc["items"][1]["id"] = doc["items"][0]["id"]
        with self.assertRaises(ValueError): self.parse(doc)

    def test_image_descriptor_limits(self):
        for key, value in (("size", 0), ("size", 307201), ("size", True), ("sha256", "A" * 64),
                           ("url", "banners/local.png"), ("url", "https://evil.example/image.png")):
            doc = manifest(); doc["items"][0]["image"]["1x"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.parse(doc)

    def test_rotation_default_and_clamp(self):
        for value, expected in ((None, 10), (-1, 5), (0, 5), (10, 10), (999, 60)):
            doc = manifest()
            if value is None: doc.pop("rotateSeconds")
            else: doc["rotateSeconds"] = value
            self.assertEqual(self.parse(doc)["rotateSeconds"], expected)

    def test_allow_list(self):
        for host in ("hasontech.vn", "aios.hasontech.vn", "system.hasontech.vn", "a.b.hasontech.vn",
                     "echatbot.vn", "espace.vn", "aidelam.com"):
            self.assertTrue(allowed_url("https://" + host + "/image.png"), host)
        for url in ("http://hasontech.vn", "https://evilhasontech.vn", "https://hasontech.vn.evil.example", "file:///tmp/a",
                    "https://a.echatbot.vn", "https://hasontech.vn:444/a", "https://user@hasontech.vn/a",
                    "https://hasontech.vn\\@evil.example", "https://hasontech.vn/\nfoo", "https://hasontech.vn./", "//hasontech.vn"):
            self.assertFalse(allowed_url(url), url)

    def test_expert_override(self):
        self.assertEqual(feed_url("https://test.example/feed.json"), "https://test.example/feed.json")
        for url in ("", "http://localhost/feed.json", "file:///tmp/feed.json", "https://test.example/x?id=1"):
            self.assertEqual(feed_url(url), FEED_URL)

    def test_utm(self):
        utm = load_data("solutions.json")["utm"]
        url = click_url("https://espace.vn/zaloapp?utm_medium=wrong&device_id=123", utm)
        self.assertEqual(parse_qs(urlsplit(url).query), {"utm_source": [utm["source"]], "utm_medium": ["banner"],
                                                        "utm_campaign": [utm["campaign"]]})
        self.assertEqual(urlsplit(url).path, "/zaloapp")
        with self.assertRaises(ValueError): click_url("https://evil.example", utm)

    def test_image_magic_types(self):
        png = (Path(ROOT) / "extensions/hst-vietnamese-tools/banners/aios@1x.png").read_bytes()
        jpeg = None  # generated below at an allowed banner size
        # Small real WebP generated from the committed banner; test dependency only, never in extension.
        import io
        from PIL import Image
        stream = io.BytesIO(); Image.open(io.BytesIO(png)).save(stream, format="WEBP")
        jpeg_stream = io.BytesIO(); Image.open(io.BytesIO(png)).convert("RGB").save(jpeg_stream, format="JPEG")
        jpeg = jpeg_stream.getvalue()
        for data, ext in ((png, ".png"), (jpeg, ".jpg"), (stream.getvalue(), ".webp")):
            self.assertEqual(verify.verify_image(data, image_spec(data)), ext)
        for data in (b"<svg></svg>", b"GIF89a", b"<html>fake.png</html>", b"\x89PNG\r\n\x1a\n", b"RIFFxxxxWEBPxxxxxxxx"):
            with self.assertRaises(ValueError): verify.verify_image(data, image_spec(data))

    def test_image_size_and_hash(self):
        for data, spec in ((b"a" * 307201, image_spec(b"a" * 307201)), (b"abc", image_spec(b"abcd")),
                           (b"abc", image_spec(b"xyz"))):
            with self.assertRaises(ValueError): verify.verify_image(data, spec)

    def test_time_and_version_windows(self):
        item = manifest()["items"][0]
        item.update(startAt="2026-11-04T00:00:00Z", endAt="2026-11-05T00:00:00Z",
                    minVersion="1.0.0-beta.2", maxVersion="1.0.0")
        self.assertTrue(schema.active(item, NOW, VERSION))
        self.assertFalse(schema.active(item, NOW - 1, VERSION))
        self.assertFalse(schema.active(item, NOW + 86400, VERSION))
        self.assertTrue(schema.active(item, NOW, "1.0.0"))
        self.assertFalse(schema.active(item, NOW, "1.0.1"))
        self.assertFalse(schema.active(item, NOW, "1.0.0-beta.1"))

    def test_reversed_windows_rejected(self):
        for changes in ({"startAt": "2026-11-05T00:00:00Z", "endAt": "2026-11-04T00:00:00Z"},
                        {"minVersion": "2.0.0", "maxVersion": "1.0.0"}):
            doc = manifest(); doc["items"][0].update(changes)
            with self.assertRaises(ValueError): self.parse(doc)

    def test_bundle_copy_and_images(self):
        doc = schema.parse_manifest((Path(ROOT) / "data/hst/banners.json").read_bytes(), bundled=True)
        solutions = {s["id"]: s for s in load_data("solutions.json")["solutions"]}
        self.assertEqual({i["id"] for i in doc["items"]}, set(solutions))
        for item in doc["items"]:
            solution = solutions[item["id"]]
            for field in ("id", "name", "tagline"): self.assertEqual(item[field], solution[field])
            # Clicks go through the server-side counter; solutions.json keeps the direct page.
            self.assertEqual(item["url"], "https://system.hasontech.vn/hst-office/go/" + item["id"])
            for scale, spec in item["image"].items():
                data = (Path(ROOT) / "extensions/hst-vietnamese-tools" / spec["url"]).read_bytes()
                self.assertEqual(verify.verify_image(data, spec), ".png")
                from PIL import Image
                import io
                self.assertEqual(Image.open(io.BytesIO(data)).size, (360 * int(scale[0]), 104 * int(scale[0])))
        with self.assertRaises(ValueError): schema.parse_manifest(json.dumps(doc).encode())
        bad = copy.deepcopy(doc); bad["items"][0]["image"]["1x"]["url"] = "banners/../../evil.png"
        with self.assertRaises(ValueError): schema.parse_manifest(json.dumps(bad).encode(), bundled=True)


if __name__ == "__main__": unittest.main()
