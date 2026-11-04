# SPDX-License-Identifier: AGPL-3.0-only
import base64
import json
import threading
import time
from unittest.mock import patch

from banner_fixtures import Remote
from banner_payload_fixtures import MaximumRemote, execute, service_module
from banner_review_fixtures import FeedCase
from hst_office import banner_feed, banner_snapshot
from hst_office.banner_schema import MAX_IMAGE, MAX_ITEMS


class PayloadTests(FeedCase):
    def test_maximum_campaign_returns_one_image_with_weight_independent_size(self):
        remote = MaximumRemote(weight=10)
        feed = self.feed(remote)
        self.refresh(feed)
        service = service_module()
        sizes = []
        for weight in (10, 1):
            if weight == 1:
                remote.set_weight(weight)
                self.now += 86400
                self.refresh(feed)
            for scale in (1, 2, 3):
                started = time.perf_counter()
                result = execute(service, feed, scale)
                elapsed = time.perf_counter() - started
                size = len(result.encode("utf-8"))
                print(f"Payload: weight={weight}, scale={scale}, bytes={size}, caller={elapsed:.6f}s")
                self.assertLessEqual(size, 432 * 1024)
                value = json.loads(result)
                self.assertEqual(len(value["items"]), 1)
                blob = base64.b64decode(value["items"][0]["image_base64"], validate=True)
                self.assertEqual(len(blob), MAX_IMAGE)
                self.assertEqual(blob, remote.payloads[remote.doc["items"][0]["image"][f"{scale}x"]["url"]])
                self.assertEqual(value["slotCount"], MAX_ITEMS * weight)
                sizes.append(size)
        self.assertEqual(sizes[:3], sizes[3:])

    def test_weighted_slots_reference_the_same_banner_and_image_map(self):
        feed = self.feed(MaximumRemote())
        items = self.refresh(feed)["items"]
        self.assertEqual(len(items), 240)
        self.assertEqual(len({id(item) for item in items}), MAX_ITEMS)
        self.assertEqual(len({id(item["images"]) for item in items}), MAX_ITEMS)
        for index, item in enumerate(items):
            self.assertIs(item, items[index % MAX_ITEMS])

    def test_worker_prepares_remote_and_cached_responses_without_ui_encoding(self):
        feed = self.feed()
        service = service_module()
        threads = []
        encode = banner_snapshot.encoded_items
        def record(*args):
            threads.append(threading.get_ident())
            return encode(*args)
        with patch.object(banner_snapshot, "encoded_items", side_effect=record):
            self.refresh(feed)
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)
        offline = Remote()
        offline.offline = True
        cached = self.feed(offline)
        threads.clear()
        with patch.object(banner_snapshot, "encoded_items", side_effect=record):
            self.refresh(cached)
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)
        with patch.object(base64, "b64encode", side_effect=AssertionError("UI encoding")), \
                patch.object(json, "dumps", side_effect=AssertionError("UI serialization")):
            for source in (feed, cached):
                for scale in (1, 2, 3):
                    self.assertEqual(json.loads(execute(service, source, scale))["slotCount"], 2)

    def test_installed_bundle_loads_prepared_payloads_and_never_encodes_on_ui(self):
        feed = self.feed()
        encoded = banner_snapshot.encoded_items(feed.bundle, feed.bundle_images, feed.utm)
        load = banner_feed.load_data
        def packaged(name):
            return encoded if name == "banner-snapshots.json" else load(name)
        with patch.object(banner_feed, "load_data", side_effect=packaged), \
                patch.object(banner_snapshot, "encoded_items", side_effect=AssertionError("UI encoding")):
            installed = self.feed(key=b"")
            self.refresh(installed)
            for scale in (1, 2, 3):
                value = json.loads(execute(service_module(), installed, scale))
                blob = base64.b64decode(value["items"][0]["image_base64"], validate=True)
                self.assertEqual(blob, installed.bundled()["items"][0].image_bytes_for_scale(scale))

    def test_service_rotation_wrap_windows_scale_and_verified_bytes(self):
        remote = Remote()
        remote.doc["items"][0].update(weight=2, order=10, endAt="2026-11-05T00:00:00Z")
        remote = Remote(remote.doc)
        feed = self.feed(remote)
        snapshot = self.refresh(feed)
        service = service_module()
        original = snapshot["items"][1].image_bytes_for_scale(2)
        self.cached_path(remote, "2x").write_bytes(b"replaced after verification")
        for slot, identifier in ((0, "echatbot"), (1, "aios"), (2, "aios"), (3, "echatbot")):
            value = json.loads(execute(service, feed, 1.5, slot))
            self.assertEqual(value["items"][0]["id"], identifier)
            self.assertEqual(value["slotCount"], 3)
            self.assertEqual(value["slot"], slot % 3)
            if identifier == "aios":
                self.assertEqual(base64.b64decode(value["items"][0]["image_base64"]), original)
        for slot in (-1, "1", None, True, float("inf")):
            self.assertEqual(json.loads(execute(service, feed, slot=slot))["slot"], 0)
        self.now += 86400
        with patch.object(feed, "refresh_async"):
            value = json.loads(execute(service, feed, slot=2))
        self.assertEqual(value["slotCount"], 1)
        self.assertEqual(value["items"][0]["id"], "echatbot")

    def test_snapshot_maps_are_independent_and_response_limit_is_enforced(self):
        feed = self.feed()
        self.refresh(feed)
        snapshot = feed.current()
        snapshot["items"][0]["images"]["1x"] = b"caller mutation"
        self.assertNotEqual(feed.current()["items"][0].image_bytes_for_scale(1), b"caller mutation")
        snapshot["items"][0].serialized = {"1x": "x" * banner_snapshot.MAX_SNAPSHOT}
        with self.assertRaises(ValueError):
            banner_snapshot.selected_json(snapshot)
