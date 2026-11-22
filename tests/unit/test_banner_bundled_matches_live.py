# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The installed default banners equal the set published on system.hasontech.vn.

The fixture is the signed manifest served at https://system.hasontech.vn/hst-office/banners.json
(generatedAt 2026-11-14T09:13:27Z) with its detached signature, downloaded on 2026-11-15. The online
manifest names each image `<id>-<first 12 hex of sha256>@<scale>x.png`; the bundled one uses relative
`banners/<id>@<scale>x.png`. Everything else (copy, click URL, order, every image's SHA-256 and size)
must be identical, and the PNG files shipped in the extension must hash to the published values.

Set HST_LIVE_BANNERS=1 to also compare the fixture with the feed being served right now.
"""
import hashlib
import json
import os
import unittest
import urllib.request

from _paths import ROOT
from hst_office import banner_verify

LIVE_URL = "https://system.hasontech.vn/hst-office/banners.json"
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "banners", "banners-live-2026-11-14T091327Z.json")
BUNDLED = os.path.join(ROOT, "data", "hst", "banners.json")
EXTENSION = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
COPY_FIELDS = ("name", "tagline", "url", "order")
IMAGE_KINDS = ("image", "imageCompact")


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def published():
    data = read_bytes(FIXTURE)
    with open(FIXTURE + ".sig", encoding="ascii") as handle:
        signature = handle.read()
    # verified with the production banner key: the fixture is the genuine published manifest
    return banner_verify.verify_manifest(data, signature), json.loads(data)


class BundledMatchesLive(unittest.TestCase):
    def setUp(self):
        self.verified, self.live = published()
        self.bundled = json.loads(read_bytes(BUNDLED))

    def test_fixture_is_the_signed_publication(self):
        self.assertEqual(self.live["generatedAt"], "2026-11-14T09:13:27Z")
        self.assertEqual([i["id"] for i in self.verified["items"]], [i["id"] for i in self.live["items"]])

    def test_bundled_is_the_same_generation_and_set(self):
        self.assertEqual(self.bundled["generatedAt"], self.live["generatedAt"])
        self.assertEqual(self.bundled.get("rotateSeconds"), self.live.get("rotateSeconds"))
        self.assertEqual([i["id"] for i in self.bundled["items"]], [i["id"] for i in self.live["items"]])

    def test_every_item_and_image_matches(self):
        bundled = {item["id"]: item for item in self.bundled["items"]}
        checked = 0
        for item in self.live["items"]:
            local = bundled[item["id"]]
            for field in COPY_FIELDS:
                self.assertEqual(local[field], item[field], (item["id"], field))
            for kind in IMAGE_KINDS:
                self.assertEqual(sorted(local[kind]), sorted(item[kind]), (item["id"], kind))
                for scale, spec in item[kind].items():
                    mine = local[kind][scale]
                    label = (item["id"], kind, scale)
                    self.assertEqual((mine["sha256"], mine["size"]), (spec["sha256"], spec["size"]), label)
                    self.assertIn("-%s@%s.png" % (spec["sha256"][:12], scale), spec["url"], label)
                    shipped = read_bytes(os.path.join(EXTENSION, mine["url"]))
                    self.assertEqual(hashlib.sha256(shipped).hexdigest(), spec["sha256"], label)
                    self.assertEqual(len(shipped), spec["size"], label)
                    checked += 1
        self.assertEqual(checked, 42)  # 7 banners x (wide, compact) x 3 scales

    @unittest.skipUnless(os.environ.get("HST_LIVE_BANNERS") == "1", "set HST_LIVE_BANNERS=1 to query the live feed")
    def test_live_feed_is_still_the_fixture(self):
        with urllib.request.urlopen(LIVE_URL, timeout=20) as response:
            self.assertEqual(response.read(), read_bytes(FIXTURE))


if __name__ == "__main__":
    unittest.main()
