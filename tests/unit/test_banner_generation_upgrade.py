# SPDX-License-Identifier: AGPL-3.0-only
"""A revised banner manifest must be a new generation, or clients that cached the old one refuse it.

banner_store.check_generation() rejects a manifest whose generatedAt equals a cached one with other
bytes, and one older than the oldest cached. The fixtures are the manifests published before the
compact art (generatedAt 2026-11-05T00:01:00Z); the bundled and online manifests of this tree must
pass against them and must match the renderer's generation.
"""
import json
import os
import re
import unittest

from _paths import ROOT
from hst_office import banner_store

FIXTURES = os.path.join(ROOT, "tests", "fixtures", "banners")
PAIRS = {
    "data/hst/banners.json": "banners-2026-11-05.json",
    "assets/banners/banners-online.example.json": "banners-online-2026-11-05.json",
}


def read(path):
    with open(path, "rb") as handle:
        data = handle.read()
    return json.loads(data), data


class GenerationUpgrade(unittest.TestCase):
    def test_current_manifests_upgrade_the_published_ones(self):
        for current, previous in PAIRS.items():
            old_doc, old_raw = read(os.path.join(FIXTURES, previous))
            new_doc, new_raw = read(os.path.join(ROOT, current))
            self.assertNotEqual(old_raw, new_raw, current)
            self.assertGreater(new_doc["generatedAt"], old_doc["generatedAt"], current)
            banner_store.check_generation([(old_doc, old_raw, b"")], new_doc, new_raw)

    def test_same_generation_with_new_bytes_is_refused(self):
        # the failure this guards against: new art published under the old timestamp
        old_doc, old_raw = read(os.path.join(FIXTURES, PAIRS["data/hst/banners.json"]))
        new_doc, new_raw = read(os.path.join(ROOT, "data/hst/banners.json"))
        stale = dict(new_doc, generatedAt=old_doc["generatedAt"])
        with self.assertRaises(ValueError):
            banner_store.check_generation([(old_doc, old_raw, b"")], stale, new_raw)

    def test_manifests_carry_the_renderer_generation(self):
        with open(os.path.join(ROOT, "scripts", "brand", "render-banners.py"), encoding="utf-8") as handle:
            generated = re.search(r'^GENERATED_AT = "([^"]+)"', handle.read(), re.M).group(1)
        for current in PAIRS:
            self.assertEqual(read(os.path.join(ROOT, current))[0]["generatedAt"], generated, current)


if __name__ == "__main__":
    unittest.main()
