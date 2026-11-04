# SPDX-License-Identifier: AGPL-3.0-only
"""Widget snapshots carry immutable verified bytes. Workers publish one coherent state tuple."""
import json
import math
from pathlib import Path
import threading
import time

from . import banner_cache as cache
from . import banner_store as store
from . import banner_verify
from .banner_fetch import fetch
from .banner_schema import INTERVAL, MAX_MANIFEST, active, parse_manifest
from .banner_urls import click_url, feed_url
from .data_files import EXT_ROOT, load_data


class Banner(dict):
    """Snapshot mapping; bytes remain authentic even if cache files are subsequently replaced."""
    def image_bytes_for_scale(self, scale):
        try:
            value = float(scale)
            level = max(1, min(3, math.ceil(value))) if math.isfinite(value) else 1
        except (ValueError, TypeError):
            level = 1
        return self["images"][str(level) + "x"]


class BannerFeed:
    def __init__(self, profile_dir, version, override="", proxy=None, *, public_key=None, fetcher=fetch, clock=time.time):
        self.root = Path(profile_dir) / "hst-banners"
        self.version, self.url, self.proxy = version, feed_url(override), proxy
        self.key = banner_verify.PUBLIC_KEY if public_key is None else public_key
        self.fetcher, self.clock = fetcher, clock
        self.utm = load_data("solutions.json")["utm"]
        self.bundle = parse_manifest(json.dumps(load_data("banners.json"), ensure_ascii=False).encode("utf-8"), bundled=True)
        self.bundle_images = {i["id"]: {s: (Path(EXT_ROOT) / v["url"]).read_bytes() for s, v in i["image"].items()}
                              for i in self.bundle["items"]}
        self._state = ()  # constructed privately by the worker, never mutated after its single assignment
        self._next_check, self._lock = 0, threading.Lock()

    def refresh_async(self):
        """Return the worker (or None); no cache verification or network work on the caller's thread."""
        if self.clock() < self._next_check or not self._lock.acquire(blocking=False):
            return None
        thread = threading.Thread(target=self._refresh, name="hst-banner-feed", daemon=True)
        try:
            thread.start()
        except Exception:
            self._lock.release()
            raise
        return thread

    def _refresh(self):
        now = self.clock()
        self._next_check = now + INTERVAL
        try:
            if not banner_verify.valid_key(self.key):
                return
            candidates = store.load(self.root, self.key)
            if candidates:
                self._state = candidates
            claimed, self._next_check = cache.claim_attempt(self.root, now)
            if not claimed:
                return
            data = self.fetcher(self.url, MAX_MANIFEST, self.version, self.proxy)
            signature = self.fetcher(self.url + ".sig", 128, self.version, self.proxy)
            doc = banner_verify.verify_manifest(data, signature, self.key)
            store.check_generation(store.metadata(self.root, self.key), doc, data)
            blobs = {}
            for item in doc["items"]:
                blobs[item["id"]] = {}
                for scale, spec in item["image"].items():
                    try:
                        blob = cache.cached_image(self.root, spec, scale)
                    except (OSError, ValueError):
                        blob = self.fetcher(spec["url"], spec["size"], self.version, self.proxy)
                        banner_verify.verify_image(blob, spec, scale)
                    blobs[item["id"]][scale] = blob
            self._state = store.publish(self.root, self.key, data, signature, blobs, self.clock(), self.version)
        except Exception:  # noqa: BLE001 - never log URLs, profile paths or exception details
            print("HST banners: refresh unavailable; using local content", flush=True)
        finally:
            self._lock.release()

    def bundled(self):
        return self._snapshot(((self.bundle, self.bundle_images),), self.clock())

    def current(self):
        """Capture a single coherent state, without ever taking the long worker/publication locks."""
        state = self._state
        return self._snapshot(state + ((self.bundle, self.bundle_images),), self.clock())

    def _snapshot(self, candidates, now):
        for doc, images in candidates:
            eligible = [i for i in doc["items"] if active(i, now, self.version)]
            if not eligible:
                continue
            items = []
            for repeat in range(max(i.get("weight", 1) for i in eligible)):
                for i in eligible:
                    if repeat < i.get("weight", 1):
                        items.append(Banner(id=i["id"], name=i["name"], tagline=i["tagline"],
                                            click_url_with_utm=click_url(i["url"], self.utm), images=dict(images[i["id"]])))
            return {"items": items, "rotateSeconds": doc["rotateSeconds"]}
        return {"items": [], "rotateSeconds": 10}


def get_banners(feed):
    """Start a due refresh and immediately return an ordered snapshot, with an installed fallback."""
    try:
        feed.refresh_async()
        return feed.current()
    except Exception:  # noqa: BLE001 - service failures must not escape into the editing UI
        return feed.bundled()
