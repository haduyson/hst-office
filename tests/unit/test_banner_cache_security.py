# SPDX-License-Identifier: AGPL-3.0-only
import base64
import json
from pathlib import Path
import threading

from _paths import ROOT
from banner_fixtures import KEY, VERSION, Remote
from banner_review_fixtures import FeedCase
from hst_office import banner_store as store


class CacheSecurityTests(FeedCase):
    def test_replacement_after_verification_cannot_change_decoded_buffer(self):
        remote = Remote()
        feed = self.feed(remote)
        before = self.refresh(feed)["items"][0].image_bytes_for_scale(1)
        substitute = (Path(ROOT) / "extensions/hst-vietnamese-tools/banners/hst-post@1x.png").read_bytes()
        self.cached_path(remote).write_bytes(substitute)
        self.assertNotEqual(before, substitute)
        self.assertEqual(feed.current()["items"][0].image_bytes_for_scale(1), before)
        remote.offline = True
        self.assertEqual(self.refresh(self.feed(remote))["items"][0]["name"], "HASON TECH")

    def test_symlink_target_replacement_after_verification(self):
        remote = Remote()
        self.refresh(self.feed(remote))
        path = self.cached_path(remote)
        target = self.root / "target.png"
        path.rename(target)
        path.symlink_to(target)
        feed = self.feed(remote)
        before = self.refresh(feed)["items"][0].image_bytes_for_scale(1)
        target.write_bytes(b"replaced")
        self.assertEqual(feed.current()["items"][0].image_bytes_for_scale(1), before)
        remote.offline = True
        self.assertEqual(self.refresh(self.feed(remote))["items"][0]["name"], "HASON TECH")

    def test_missing_images_do_not_erase_rollback_floor_on_restart(self):
        remote = Remote()
        self.refresh(self.feed(remote))
        self.cached_path(remote).unlink()
        self.now += 86400
        older = self.campaign("2026-11-03")
        before = (self.root / "current.json").read_bytes()
        self.assertEqual(self.refresh(self.feed(older))["items"][0]["name"], "HASON TECH")
        self.assertEqual((self.root / "current.json").read_bytes(), before)
        self.assertEqual(len(older.calls), 2)

    def test_invalid_current_recovers_previous_floor_without_images(self):
        self.refresh(self.feed(self.campaign("2026-11-04")))
        self.now += 86400
        self.refresh(self.feed(self.campaign("2026-11-05")))
        (self.root / "current.json").write_bytes(b"bad")
        for path in (self.root / "images").glob("*"):
            path.unlink()
        self.now += 86400
        older = self.campaign("2026-11-03")
        self.refresh(self.feed(older))
        self.assertEqual(store.metadata(self.root, KEY)[0][0]["generatedAt"], "2026-11-04T00:00:00Z")
        self.assertEqual(len(older.calls), 2)

    def test_equal_timestamp_different_bytes_rejected(self):
        self.refresh(self.feed())
        before = (self.root / "current.json").read_bytes()
        self.now += 86400
        conflict = self.campaign("2026-11-04")
        self.assertEqual(self.refresh(self.feed(conflict))["items"][0]["name"], "Online AIOS")
        self.assertEqual((self.root / "current.json").read_bytes(), before)
        self.assertEqual(len(conflict.calls), 2)

    def test_overlapping_workers_compare_latest_floor_at_publication(self):
        entered, release = threading.Event(), threading.Event()
        older = self.campaign("2026-11-04")
        def delayed(*args):
            result = older(*args)
            if args[0].endswith("@1x.png"):
                entered.set()
                self.assertTrue(release.wait(5))
            return result
        feed = self.feed(delayed)
        worker = feed.refresh_async()
        try:
            self.assertTrue(entered.wait(5))
            self.now += 86400
            self.refresh(self.feed(self.campaign("2026-11-05")))
        finally:
            release.set()
            worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(store.metadata(self.root, KEY)[0][0]["generatedAt"], "2026-11-05T00:00:00Z")
        self.assertEqual(store.load(self.root, KEY)[0][0]["items"][0]["name"], "2026-11-05")

    def test_repeated_and_distinct_future_campaigns_preserve_eligible_cache(self):
        self.refresh(self.feed(self.campaign("2026-11-04")))
        future = self.campaign("2026-11-05", "2026-11-10")
        # Future artwork has different hashes, so this also exercises image retention during GC.
        future.doc["items"][0]["image"] = future.doc["items"][1]["image"]
        future = Remote(future.doc)
        for date, remote in ((5, future), (6, future), (7, self.campaign("2026-11-07", "2026-11-10"))):
            self.now += 86400
            feed = self.feed(remote)
            self.assertEqual(self.refresh(feed)["items"][0]["name"], "2026-11-04", date)
            remote.offline = True
            self.assertEqual(self.refresh(self.feed(remote))["items"][0]["name"], "2026-11-04")
            remote.offline = False
        self.now += 3 * 86400
        self.assertEqual(feed.current()["items"][0]["name"], "2026-11-07")

    def test_idempotent_poll_keeps_metadata_and_previous(self):
        remote = self.campaign("2026-11-04")
        self.refresh(self.feed(remote))
        self.now += 86400
        remote = self.campaign("2026-11-05", "2026-11-10")
        self.refresh(self.feed(remote))
        before = {p.name: p.read_bytes() for p in self.root.glob("*.json")}
        self.now += 86400
        self.refresh(self.feed(remote))
        self.assertEqual({p.name: p.read_bytes() for p in self.root.glob("*.json")}, before)
        decoded = json.loads(base64.b64decode(json.loads(before["current.json"])["fallback"]["manifest"]))
        self.assertEqual(decoded["generatedAt"], "2026-11-04T00:00:00Z")

    def test_publication_lock_serializes_threads(self):
        acquired = threading.Event()
        def other():
            with store.publication_lock(self.root):
                acquired.set()
        with store.publication_lock(self.root):
            worker = threading.Thread(target=other)
            worker.start()
            self.assertFalse(acquired.wait(.05))
        worker.join(2)
        self.assertTrue(acquired.is_set())
