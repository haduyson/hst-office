# SPDX-License-Identifier: AGPL-3.0-only
"""Reusable adversarial fixtures; temporary keys, profiles and immutable artwork only."""
from pathlib import Path
import tempfile
import unittest

from banner_fixtures import KEY, NOW, VERSION, Remote, manifest
from hst_office.banner_feed import BannerFeed
from hst_office import banner_cache as cache


class FeedCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = NOW
        self.root = Path(self.tmp.name) / "hst-banners"

    def feed(self, remote=None, key=KEY):
        return BannerFeed(self.tmp.name, VERSION, public_key=key, fetcher=remote or Remote(), clock=lambda: self.now)

    def refresh(self, feed):
        worker = feed.refresh_async()
        if worker:
            worker.join(10)
            self.assertFalse(worker.is_alive())
        return feed.current()

    def cached_path(self, remote, scale="1x"):
        return cache.image_path(self.root, remote.doc["items"][0]["image"][scale], ".png")

    def campaign(self, date, start=None):
        doc = manifest()
        doc["generatedAt"] = date + "T00:00:00Z"
        doc["items"][0]["name"] = date
        if start:
            for item in doc["items"]:
                item["startAt"] = start + "T00:00:00Z"
        return Remote(doc)
