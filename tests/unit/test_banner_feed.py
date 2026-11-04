# SPDX-License-Identifier: AGPL-3.0-only
import contextlib
import io
from pathlib import Path
import tempfile
import threading
import unittest

from _paths import ROOT
from banner_fixtures import KEY, NOW, VERSION, Remote, manifest
from hst_office.banner_feed import BannerFeed, get_banners
from hst_office import banner_cache as cache


class BannerFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = NOW
        self.remote = Remote()

    def feed(self, remote=None, **kwargs):
        return BannerFeed(self.temp.name, VERSION, public_key=KEY, fetcher=remote or self.remote,
                          clock=lambda: self.now, **kwargs)

    def run_refresh(self, feed):
        thread = feed.refresh_async()
        if thread: thread.join(10); self.assertFalse(thread.is_alive())
        return feed.current()

    def test_offline_uses_bundle(self):
        self.remote.offline = True
        feed = self.feed()
        self.assertEqual(self.run_refresh(feed)["items"][0]["name"], "AIOS")
        self.assertEqual(len(feed.current()["items"]), 6)

    def test_fresh_online_precedes_bundle(self):
        result = self.run_refresh(self.feed())
        self.assertEqual(result["items"][0]["name"], "Online AIOS")
        self.assertIsInstance(result["items"][0].image_bytes_for_scale(2), bytes)

    def test_valid_cache_when_offline_after_restart(self):
        self.run_refresh(self.feed())
        self.now += 86400
        self.remote.offline = True
        feed = self.feed()
        self.assertEqual(self.run_refresh(feed)["items"][0]["name"], "Online AIOS")

    def test_corrupt_cache_falls_back_to_bundle(self):
        self.run_refresh(self.feed())
        (Path(self.temp.name) / "hst-banners/current.json").write_bytes(b"bad")
        self.remote.offline = True
        self.assertEqual(self.run_refresh(self.feed())["items"][0]["name"], "AIOS")

    def test_tampered_cached_image_rejected(self):
        self.run_refresh(self.feed())
        spec = self.remote.doc["items"][0]["image"]["1x"]
        cache.image_path(Path(self.temp.name) / "hst-banners", spec, ".png").write_bytes(b"corrupt")
        self.remote.offline = True
        self.assertEqual(self.run_refresh(self.feed())["items"][0]["name"], "AIOS")

    def test_cached_signature_rechecked(self):
        self.run_refresh(self.feed())
        feed = BannerFeed(self.temp.name, VERSION, public_key=b"", fetcher=self.remote, clock=lambda: self.now)
        self.assertEqual(self.run_refresh(feed)["items"][0]["name"], "AIOS")

    def test_failed_generation_does_not_replace_cache(self):
        feed = self.feed(); self.run_refresh(feed)
        path = Path(self.temp.name) / "hst-banners/current.json"
        before = path.read_bytes()
        self.now += 86400
        remote = Remote(); remote.signature = b"invalid"
        fresh = self.feed(remote)
        self.assertEqual(self.run_refresh(fresh)["items"][0]["name"], "Online AIOS")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(remote.calls), 2)

    def test_bad_image_leaves_bundle(self):
        self.remote.bad_image = True
        self.assertEqual(self.run_refresh(self.feed())["items"][0]["name"], "AIOS")
        self.assertFalse((Path(self.temp.name) / "hst-banners/current.json").exists())

    def test_out_of_window_feed_falls_back(self):
        doc = manifest()
        for item in doc["items"]: item["startAt"] = "2026-11-05T00:00:00Z"
        feed = self.feed(Remote(doc))
        self.assertEqual(self.run_refresh(feed)["items"][0]["name"], "AIOS")
        self.now += 86400
        self.assertEqual(feed.current()["items"][0]["name"], "Online AIOS")

    def test_future_generation_preserves_last_eligible_cache_on_restart(self):
        self.run_refresh(self.feed())
        doc = manifest()
        doc["generatedAt"] = "2026-11-05T00:00:00Z"
        for item in doc["items"]: item["startAt"] = "2026-11-06T00:00:00Z"
        self.now += 86400
        remote = Remote(doc)
        self.run_refresh(self.feed(remote))
        remote.offline = True
        self.assertEqual(self.run_refresh(self.feed(remote))["items"][0]["name"], "Online AIOS")

    def test_version_window_falls_back(self):
        doc = manifest()
        for item in doc["items"]: item["minVersion"] = "2.0.0"
        self.assertEqual(self.run_refresh(self.feed(Remote(doc)))["items"][0]["name"], "AIOS")

    def test_24_hour_throttle_including_restart_and_failure(self):
        self.remote.offline = True
        feed = self.feed(); self.run_refresh(feed)
        self.assertEqual(len(self.remote.calls), 1)
        self.assertIsNone(feed.refresh_async())
        self.now += 86399
        self.run_refresh(self.feed())
        self.assertEqual(len(self.remote.calls), 1)
        self.now += 1
        self.run_refresh(self.feed())
        self.assertEqual(len(self.remote.calls), 2)

    def test_parallel_claim_and_clock_rollback(self):
        root = Path(self.temp.name) / "hst-banners"
        barrier = threading.Barrier(4)
        claims = []
        def claim():
            barrier.wait(); claims.append(cache.claim_attempt(root, NOW)[0])
        threads = [threading.Thread(target=claim) for _ in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sum(claims), 1)
        self.assertFalse(cache.claim_attempt(root, NOW - 100)[0])

    def test_start_never_waits_for_network(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(*args):
            entered.set(); release.wait(5); raise OSError("offline")
        feed = self.feed(blocked)
        try:
            result = get_banners(feed)
            self.assertEqual(result["items"][0]["name"], "AIOS")
            self.assertTrue(entered.wait(2))
            self.assertIsNone(feed.refresh_async())
        finally:
            release.set()
            # Wait for worker before TemporaryDirectory cleanup.
            with feed._lock: pass

    def test_scale_selection(self):
        banner = self.feed().current()["items"][0]
        for scale, expected in ((.5, 1), (1, 1), (1.25, 2), (2, 2), (2.5, 3), (4, 3), (float("nan"), 1)):
            self.assertEqual(banner.image_bytes_for_scale(scale), banner["images"][f"{expected}x"])

    def test_weight_order_and_rotation(self):
        doc = manifest(); doc["rotateSeconds"] = 12
        doc["items"][0].update(weight=2, order=10)
        feed = self.feed(Remote(doc)); result = self.run_refresh(feed)
        self.assertEqual([i["id"] for i in result["items"]], ["echatbot", "aios", "aios"])
        self.assertEqual(result["rotateSeconds"], 12)

    def test_no_personal_data_logged(self):
        self.remote.offline = True
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture): self.run_refresh(self.feed())
        self.assertEqual(capture.getvalue(), "HST banners: refresh unavailable; using local content\n")

    def test_no_install_directory_writes(self):
        root = Path(ROOT) / "extensions/hst-vietnamese-tools/banners"
        before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
        self.run_refresh(self.feed())
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_unsigned_feed_fetches_no_images(self):
        self.remote.signature = b"wrong"
        self.run_refresh(self.feed())
        self.assertEqual(len(self.remote.calls), 2)

    def test_rollback_rejected(self):
        self.run_refresh(self.feed())
        doc = manifest(); doc["generatedAt"] = "2026-11-03T00:00:00Z"
        doc["items"][0]["name"] = "Older"
        self.now += 86400
        self.assertEqual(self.run_refresh(self.feed(Remote(doc)))["items"][0]["name"], "Online AIOS")


if __name__ == "__main__": unittest.main()
