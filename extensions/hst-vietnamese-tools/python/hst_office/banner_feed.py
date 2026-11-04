# SPDX-License-Identifier: AGPL-3.0-only
"""Widget-facing snapshots. Network, signature verification and cache loading run in a daemon thread."""
import json
import math
from pathlib import Path
import threading
import time

from . import banner_cache as cache
from . import banner_verify
from .banner_fetch import fetch
from .banner_schema import INTERVAL, MAX_MANIFEST, active, parse_manifest
from .banner_urls import click_url, feed_url
from .data_files import EXT_ROOT, load_data


class Banner(dict):
    """Python mapping with a scale selector; immutable by convention after snapshot construction."""
    def image_path_for_scale(self, scale):
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
        self.bundle_paths = {i["id"]: {s: str(Path(EXT_ROOT) / v["url"]) for s, v in i["image"].items()}
                             for i in self.bundle["items"]}
        self._online, self._cached, self._previous = None, None, None
        self._next_check, self._lock = 0, threading.Lock()

    def refresh_async(self):
        """Return the worker (or None). Never performs network/cache verification on the caller's thread."""
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
        created = []
        self._next_check = now + INTERVAL
        try:
            try:
                self._cached = cache.load(self.root, self.key)
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                self._previous = cache.load(self.root, self.key, "previous.json")
            except (OSError, ValueError, KeyError, TypeError):
                pass
            claimed, self._next_check = cache.claim_attempt(self.root, now)
            if not claimed or len(self.key) != 32:
                return
            data = self.fetcher(self.url, MAX_MANIFEST, self.version, self.proxy)
            signature = self.fetcher(self.url + ".sig", 128, self.version, self.proxy)
            doc = banner_verify.verify_manifest(data, signature, self.key)
            if self._cached and doc["generatedAt"] < self._cached[0]["generatedAt"]:
                raise ValueError("older banner feed")
            paths = {}
            for item in doc["items"]:
                paths[item["id"]] = {}
                for scale, spec in item["image"].items():
                    try:
                        path = cache.cached_image(self.root, spec)
                    except (OSError, ValueError):
                        blob = self.fetcher(spec["url"], spec["size"], self.version, self.proxy)
                        suffix = banner_verify.verify_image(blob, spec)
                        path = str(cache.image_path(self.root, spec, suffix))
                        cache.atomic_write(path, blob)
                        created.append(path)
                    paths[item["id"]][scale] = path
            cache.publish(self.root, data, signature, doc, paths)
            self._previous = self._cached
            created.clear()  # published files now belong to the cache
            self._online = (doc, paths, now)
            # Keep the last usable generation if the new schedule has no eligible items yet.
            if any(active(i, now, self.version) for i in doc["items"]):
                self._cached = (doc, paths)
        except Exception:  # noqa: BLE001 - fixed message: never print URLs, profile paths or exception details
            for path in created:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass
            print("HST banners: refresh unavailable; using local content", flush=True)
        finally:
            self._lock.release()

    def current(self):
        """Return {items: [Banner], rotateSeconds: int}; current eligibility is evaluated on every call."""
        now = self.clock()
        candidates = []
        fresh = self._online and 0 <= now - self._online[2] < INTERVAL
        if fresh:
            candidates.append(self._online[:2])
        if self._cached:
            candidates.append(self._cached)
        if self._previous:
            candidates.append(self._previous)
        if self._online and not fresh:
            candidates.append(self._online[:2])
        candidates.append((self.bundle, self.bundle_paths))
        for doc, paths in candidates:
            eligible = [i for i in doc["items"] if active(i, now, self.version)]
            if not eligible:
                continue
            items = []
            # Weighted round robin: order is stable within each round, default weight = one appearance.
            for repeat in range(max(i.get("weight", 1) for i in eligible)):
                for i in eligible:
                    if repeat < i.get("weight", 1):
                        items.append(Banner(id=i["id"], name=i["name"], tagline=i["tagline"],
                                            click_url_with_utm=click_url(i["url"], self.utm), images=dict(paths[i["id"]])))
            return {"items": items, "rotateSeconds": doc["rotateSeconds"]}
        return {"items": [], "rotateSeconds": 10}  # bundled defaults have no eligibility windows


def get_banners(feed):
    """Start a due background refresh and immediately return the current ordered snapshot."""
    feed.refresh_async()
    return feed.current()
