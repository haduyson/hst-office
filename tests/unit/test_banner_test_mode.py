# SPDX-License-Identifier: AGPL-3.0-only
"""Local test feed (http://127.0.0.1, throwaway key) and compact art, end to end without network.

Only test-stamped packages (build-extensions.py --update-test-mode) honour HST_BANNER_TEST_URL and
HST_BANNER_TEST_KEY; release packages ignore both and stay HTTPS-only with the production key.
"""
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from _paths import ROOT
from banner_fixtures import NOW, VERSION
from hst_office import banner_fetch, banner_http, banner_schema as schema, banner_verify, ed25519
from hst_office.banner_feed import BannerFeed, test_mode_from_release
from hst_office.banner_snapshot import selected_json
from hst_office.banner_urls import FEED_URL, TEST_KEY_ENV, TEST_URL_ENV, click_url, test_url

from banner_test_mode_fixtures import (
    BASE, ENV, SEED, TEST_FEED, TEST_KEY, LocalServer, build_extensions, local_feed, png, spec,
)


class BannerTestModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = LocalServer()

    def feed(self, test_mode, environ=ENV):
        return BannerFeed(self.temp.name, VERSION, fetcher=self.server, clock=lambda: NOW,
                          test_mode=test_mode, environ=environ)

    def refresh(self, feed):
        thread = feed.refresh_async()
        if thread:
            thread.join(10)
            self.assertFalse(thread.is_alive())
        return feed.current()

    def test_release_package_stamp_never_enables_test_mode(self):
        builder = build_extensions()
        release = json.loads(builder.release_json())
        self.assertNotIn("update_test_mode", release)
        self.assertFalse(test_mode_from_release(release))
        self.assertTrue(test_mode_from_release(json.loads(builder.release_json(test_mode=True))))
        for value in ("true", 1, None, {}):
            self.assertFalse(test_mode_from_release({"release": "1.0.0", "update_test_mode": value}))
        self.assertFalse(test_mode_from_release(None))

    def test_release_build_ignores_test_url_and_key(self):
        with patch.dict(os.environ, ENV):
            for feed in (self.feed(False), self.feed(False, environ=None)):
                self.assertEqual(feed.url, FEED_URL)
                self.assertEqual(feed.key, banner_verify.PUBLIC_KEY)
                self.assertFalse(feed.allow_test)
                self.assertEqual(feed.root.name, "hst-banners")
                snapshot = self.refresh(feed)
        self.assertTrue(all(not allow for _, allow in self.server.calls))
        self.assertNotIn(TEST_FEED, [url for url, _ in self.server.calls])
        self.assertEqual(snapshot["items"][0]["id"], "hasontech")  # bundled defaults only

    def test_test_build_uses_local_feed_key_and_separate_cache(self):
        feed = self.feed(True)
        self.assertEqual((feed.url, feed.key, feed.root.name), (TEST_FEED, TEST_KEY, "hst-banners-test"))
        snapshot = self.refresh(feed)
        self.assertEqual([i["id"] for i in snapshot["items"]], ["aios", "echatbot"])
        self.assertTrue(all(allow for _, allow in self.server.calls))
        wide = json.loads(selected_json(snapshot, 2, 1))
        self.assertEqual(wide["slotCount"], 2)
        self.assertEqual(wide["items"][0]["id"], "echatbot")
        self.assertTrue(wide["items"][0]["click_url_with_utm"].startswith(BASE + "go/echatbot?utm_source="))
        compact = json.loads(selected_json(snapshot, 2, 1, compact=True))
        self.assertEqual((compact["slotCount"], compact["slot"]), (1, 0))  # echatbot has no compact art
        image = Image.open(io.BytesIO(base64.b64decode(compact["items"][0]["image_base64"])))
        self.assertEqual(image.size, (320, 208))
        # cached copies are found again by a new feed in the same profile without the network
        self.server.calls.clear()
        again = self.feed(True)
        again.fetcher = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))
        self.assertEqual([i["id"] for i in self.refresh(again)["items"]], ["aios", "echatbot"])

    def test_feed_without_compact_art_falls_back_to_installed_compact_art(self):
        for item in self.server.doc["items"]:
            item.pop("imageCompact", None)
        self.server.data = json.dumps(self.server.doc).encode()
        self.server.signature = base64.b64encode(ed25519.sign(SEED, self.server.data)) + b"\n"
        feed = self.feed(True)
        wide = self.refresh(feed)
        self.assertEqual([i["id"] for i in wide["items"]], ["aios", "echatbot"])  # online wide art
        compact = feed.current(compact=True)
        self.assertEqual(compact["items"][0]["id"], "hasontech")  # installed compact art, in order
        self.assertTrue(all(i.has_compact() for i in compact["items"]))
        self.assertEqual(json.loads(selected_json(compact, 1, 0, compact=True))["slotCount"], len(compact["items"]))
        # the online wide state itself offers no compact slot
        self.assertEqual(json.loads(selected_json(wide, 1, 0, compact=True))["slotCount"], 0)
        # nothing with compact art anywhere: the compact slot is hidden
        self.assertEqual(feed._snapshot(feed._state, NOW, compact=True)["items"], [])

    def test_bad_test_overrides_fall_back(self):
        for url in ("http://localhost:8032/hst-office/banners.json", "http://127.0.0.2/banners.json",
                    "http://user@127.0.0.1:8032/banners.json", "ftp://127.0.0.1/banners.json",
                    TEST_FEED + "?x=1", "http://127.0.0.1:99999/banners.json"):
            feed = self.feed(True, {TEST_URL_ENV: url, TEST_KEY_ENV: "zz"})
            self.assertEqual(feed.url, FEED_URL, url)
            self.assertEqual(feed.key, banner_verify.PUBLIC_KEY)
        identity = bytes([1]) + bytes(31)
        self.assertEqual(self.feed(True, {TEST_KEY_ENV: identity.hex()}).key, banner_verify.PUBLIC_KEY)

    def test_compact_art_dimensions_are_exact(self):
        doc, _, _, blobs = local_feed()
        item = doc["items"][0]
        for key, value in schema.image_specs(item):
            self.assertEqual(banner_verify.verify_image(blobs[value["url"]], value, key), ".png")
        wide = item["image"]["1x"]
        with self.assertRaises(ValueError):  # wide art offered as compact art
            banner_verify.verify_image(blobs[wide["url"]], wide, "c1x")
        small = item["imageCompact"]["2x"]
        with self.assertRaises(ValueError):  # compact art at the wrong scale
            banner_verify.verify_image(blobs[small["url"]], small, "c3x")
        with self.assertRaises(ValueError):
            banner_verify.verify_image(blobs[small["url"]], small, "2x")

    def test_local_urls_need_test_mode_everywhere(self):
        self.assertTrue(test_url(TEST_FEED))
        for url in ("https://127.0.0.1/x", "http://localhost/x", "http://127.0.0.1/x#f", "http://a@127.0.0.1/x"):
            self.assertFalse(test_url(url), url)
        _, data, signature, _ = local_feed()
        with self.assertRaises(ValueError):
            banner_verify.verify_manifest(data, signature.decode(), TEST_KEY)
        self.assertEqual(len(banner_verify.verify_manifest(data, signature.decode(), TEST_KEY, True)["items"]), 2)
        with self.assertRaises(ValueError):
            click_url(BASE + "go/aios", {"source": "s", "campaign": "c"})
        with patch.object(banner_fetch, "_run", side_effect=AssertionError("no helper for refused URLs")):
            with self.assertRaises(ValueError):
                banner_fetch.fetch(TEST_FEED, 100, VERSION)
            with self.assertRaises(ValueError):
                banner_fetch.fetch(TEST_FEED, 100, VERSION, allow_test="yes")
        with patch.object(banner_fetch, "_run", return_value=b"{}") as run:
            self.assertEqual(banner_fetch.fetch(TEST_FEED, 100, VERSION, allow_test=True), b"{}")
            self.assertTrue(json.loads(run.call_args[0][0])["allow_test"])
            banner_fetch.fetch("https://system.hasontech.vn/hst-office/banners.json", 100, VERSION)
            self.assertNotIn("allow_test", json.loads(run.call_args[0][0]))
        with self.assertRaises(ValueError):
            banner_http.request(TEST_FEED, 100, VERSION)

    def test_compact_field_does_not_break_wide_parsing(self):
        doc, _, _, _ = local_feed()
        older = copy.deepcopy(doc)
        for item in older["items"]:
            item.pop("imageCompact", None)
        parsed = schema.parse_manifest(json.dumps(doc).encode(), allow_test=True)
        self.assertEqual([i["image"] for i in parsed["items"]], [i["image"] for i in older["items"]])


if __name__ == "__main__":
    unittest.main()
