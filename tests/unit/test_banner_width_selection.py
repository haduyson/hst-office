# SPDX-License-Identifier: AGPL-3.0-only
"""The 1.0.3 ribbon's banner picks the standard size (360/640/960 x 96) that fits its width: the feed downloads the
standard sizes with the other images (client_specs), every serialized variant tells its standard width, and the
Width argument of org.hst.office.BannerFeed selects the variant (banner_snapshot.variant_key)."""
import json
import unittest

import _paths  # noqa: F401 - puts the extension's python on the path
from hst_office import banner_schema, banner_sizes, banner_snapshot
from hst_office.data_files import load_data

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def sized_item():
    """A validated item's shape with legacy art and the three standard sizes."""
    descriptor = {"url": "https://example.invalid/a.png", "sha256": "0" * 64, "size": 100}
    return {"id": "acme", "name": "Acme", "tagline": "Tagline", "url": "https://hasontech.vn/go/acme",
            "image": {scale: dict(descriptor) for scale in ("1x", "2x", "3x")},
            "sizes": [{"width": w, "height": 96, "1x": dict(descriptor), "2x": dict(descriptor)}
                      for w in banner_sizes.WIDTHS]}


def snapshot(with_sizes=True):
    item = sized_item()
    if not with_sizes:
        del item["sizes"]
    keys = [key for key, _ in banner_schema.client_specs(item)]
    images = {"acme": {key: PNG + key.encode() for key in keys}}
    doc = {"items": [item]}
    candidates = banner_snapshot.prepare([(doc, images)], load_data("solutions.json")["utm"])
    _doc, banners = candidates[0]
    return {"rotateSeconds": 10, "items": [banners["acme"]]}


def shown(snap, **kwargs):
    item = json.loads(banner_snapshot.selected_json(snap, **kwargs))["items"][0]
    return item["standard_width"], item["image_base64"]


class WidthSelectionTest(unittest.TestCase):
    def test_client_downloads_the_standard_sizes_after_the_legacy_art(self):
        keys = [key for key, _ in banner_schema.client_specs(sized_item())]
        self.assertEqual(keys, ["1x", "2x", "3x", "360@1x", "360@2x", "640@1x", "640@2x", "960@1x", "960@2x"])
        legacy = dict(sized_item())
        del legacy["sizes"]
        self.assertEqual([key for key, _ in banner_schema.client_specs(legacy)], ["1x", "2x", "3x"])

    def test_width_picks_the_largest_standard_size_that_fits(self):
        snap = snapshot()
        for width, scale, expected in ((360, 1, 360), (639, 1, 360), (640, 1, 640), (959.5, 2, 640),
                                       (960, 1, 960), (1500, 3, 960), (200, 1, 360)):
            standard, _image = shown(snap, scale=scale, width=width)
            self.assertEqual(standard, expected, (width, scale))
        self.assertNotEqual(shown(snap, scale=1, width=640)[1], shown(snap, scale=2, width=640)[1])  # 1x vs 2x

    def test_without_width_or_sizes_the_legacy_art_shows(self):
        self.assertEqual(shown(snapshot(), scale=2)[0], 0)  # 1.0.2 callers pass no Width
        self.assertEqual(shown(snapshot(with_sizes=False), scale=1, width=960)[0], 0)
        for bad in (True, "960", float("nan"), None):
            self.assertEqual(shown(snapshot(), scale=1, width=bad)[0], 0, bad)


if __name__ == "__main__":
    unittest.main()
