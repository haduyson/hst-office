# SPDX-License-Identifier: AGPL-3.0-only
"""Optional per-item compact banner artwork ("imageCompact") in the version 1 banner manifest."""
import copy
import json
import unittest

from banner_fixtures import manifest
from hst_office import banner_schema as schema


def compact(url_stem="https://system.hasontech.vn/hst-office/banners/aios-compact"):
    return {scale: {"url": f"{url_stem}@{scale}.png", "sha256": f"{n:x}" * 64, "size": 1000 * n}
            for n, scale in ((1, "1x"), (2, "2x"), (3, "3x"))}


class BannerCompactSchemaTests(unittest.TestCase):
    def parse(self, doc, bundled=False):
        return schema.parse_manifest(json.dumps(doc).encode(), bundled=bundled)

    def test_contract_constants(self):
        self.assertEqual(schema.COMPACT_FIELD, "imageCompact")
        self.assertEqual(schema.COMPACT_SIZE[1], 104)  # the ribbon height never changes

    def test_optional_and_schema_version_unchanged(self):
        doc = manifest()
        parsed = self.parse(doc)
        self.assertEqual(parsed["schemaVersion"], 1)
        self.assertFalse(any(schema.has_compact(i) for i in parsed["items"]))
        doc["items"][0]["imageCompact"] = compact()
        parsed = self.parse(doc)
        item = next(i for i in parsed["items"] if i["id"] == doc["items"][0]["id"])
        self.assertTrue(schema.has_compact(item))
        self.assertEqual(item["imageCompact"], compact())

    def test_all_three_scales_or_none(self):
        for scales in ((), ("1x",), ("1x", "2x"), ("1x", "2x", "3x", "4x")):
            doc = manifest()
            full = compact()
            full["4x"] = full["3x"]
            doc["items"][0]["imageCompact"] = {s: full[s] for s in scales}
            with self.subTest(scales=scales), self.assertRaises(ValueError):
                self.parse(doc)
        for value in (None, [], "x", True):
            doc = manifest(); doc["items"][0]["imageCompact"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(doc)

    def test_descriptor_limits_same_as_image(self):
        for key, value in (("size", 0), ("size", 307201), ("size", True), ("size", None),
                           ("sha256", "A" * 64), ("sha256", "0" * 63), ("url", "banners/local.png"),
                           ("url", "https://evil.example/image.png"), ("url", None)):
            doc = manifest(); doc["items"][0]["imageCompact"] = compact()
            doc["items"][0]["imageCompact"]["2x"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.parse(doc)
        doc = manifest(); doc["items"][0]["imageCompact"] = compact()
        doc["items"][0]["imageCompact"]["3x"]["size"] = schema.MAX_IMAGE
        self.parse(doc)

    def test_bundled_paths(self):
        doc = manifest()
        for item in doc["items"]:
            for scale, spec in item["image"].items():
                spec["url"] = f"banners/{item['id']}@{scale}.png"
        doc["items"][0]["imageCompact"] = compact("banners/aios-compact")
        self.assertTrue(schema.has_compact(self.parse(doc, bundled=True)["items"][0]))
        bad = copy.deepcopy(doc); bad["items"][0]["imageCompact"]["1x"]["url"] = "banners/../evil@1x.png"
        with self.assertRaises(ValueError):
            self.parse(bad, bundled=True)
        remote = copy.deepcopy(doc); remote["items"][0]["imageCompact"] = compact()
        with self.assertRaises(ValueError):
            self.parse(remote, bundled=True)

    def test_compact_items_skip_items_without_compact_art(self):
        doc = manifest()
        doc["items"][1]["imageCompact"] = compact()
        parsed = self.parse(doc)
        chosen = schema.compact_items(parsed["items"])
        self.assertEqual([i["id"] for i in chosen], [doc["items"][1]["id"]])
        for item in doc["items"]:
            item["imageCompact"] = compact()
        parsed = self.parse(doc)
        self.assertEqual([i["id"] for i in schema.compact_items(parsed["items"])],
                         [i["id"] for i in parsed["items"]])  # manifest order is kept
        self.assertEqual(schema.compact_items(self.parse(manifest())["items"]), [])  # no art: slot hidden
        self.assertEqual(schema.compact_items([]), [])


if __name__ == "__main__":
    unittest.main()
