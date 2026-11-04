# SPDX-License-Identifier: AGPL-3.0-only
import threading
from unittest.mock import patch

from banner_review_fixtures import FeedCase
from hst_office.banner_feed import get_banners


class SnapshotSecurityTests(FeedCase):
    def test_publication_between_capture_and_selection_keeps_coherent_snapshot(self):
        feed = self.feed(self.campaign("2026-11-04"))
        self.refresh(feed)
        entered, release = threading.Event(), threading.Event()
        result, errors = [], []
        original = feed._snapshot
        def paused(candidates, now):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return original(candidates, now)
        def reader():
            try:
                result.append(feed.current())
            except Exception as exc:
                errors.append(exc)
        with patch.object(feed, "_snapshot", side_effect=paused):
            worker = threading.Thread(target=reader)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.now += 86400
                feed.fetcher = self.campaign("2026-11-05", "2026-11-10")
                publisher = feed.refresh_async()
                publisher.join(5)
                self.assertFalse(publisher.is_alive())
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(errors, [])
        self.assertEqual(result[0]["items"][0]["name"], "2026-11-04")
        self.assertEqual(feed.current()["items"][0]["name"], "2026-11-04")

    def test_snapshot_failure_returns_usable_installed_fallback(self):
        feed = self.feed()
        with patch.object(feed, "refresh_async"), patch.object(feed, "current", side_effect=TypeError("race")):
            result = get_banners(feed)
        self.assertEqual(len(result["items"]), 6)
        self.assertTrue(result["items"][0].image_bytes_for_scale(1).startswith(b"\x89PNG"))
