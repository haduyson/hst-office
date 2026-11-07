# SPDX-License-Identifier: AGPL-3.0-only
"""Widget snapshots carry immutable verified bytes. Workers publish one coherent state tuple."""
import json
import os
from pathlib import Path
import threading
import time

from . import banner_cache as cache
from . import banner_store as store
from . import banner_verify
from .banner_fetch import fetch
from .banner_schema import INTERVAL, MAX_MANIFEST, active, image_specs, parse_manifest
from .banner_snapshot import Banner as Banner, prepare
from .banner_urls import TEST_KEY_ENV, TEST_URL_ENV, feed_url, transport_url
from .data_files import EXT_ROOT, load_data


def test_mode_from_release(release):
    """The package stamp written by build-extensions.py --update-test-mode; release packages never carry it."""
    return isinstance(release, dict) and release.get("update_test_mode") is True


def test_key(text):
    """32-byte Ed25519 public key from hex text, or None."""
    try:
        key = bytes.fromhex(text.strip()) if isinstance(text, str) and len(text) <= 128 else b""
    except ValueError:
        return None
    return key if banner_verify.valid_key(key) else None


class BannerFeed:
    def __init__(self, profile_dir, version, override="", proxy=None, *, public_key=None, fetcher=fetch, clock=time.time,
                 test_mode=False, environ=None):
        """test_mode comes only from the package stamp (release.json update_test_mode, which release checks
        reject). Only then are HST_BANNER_TEST_URL (plain HTTP to the local test host, or HTTPS) and HST_BANNER_TEST_KEY read;
        test state lives in its own cache so it never mixes with the production feed."""
        self.allow_test = test_mode is True
        environ = (os.environ if environ is None else environ) if self.allow_test else {}
        self.root = Path(profile_dir) / ("hst-banners-test" if self.allow_test else "hst-banners")
        test_url = environ.get(TEST_URL_ENV, "")
        if test_url and "?" not in test_url and transport_url(test_url, self.allow_test):
            self.url = test_url
        else:
            self.url = feed_url(override)
        self.version, self.proxy = version, proxy
        env_key = test_key(environ.get(TEST_KEY_ENV, ""))
        self.key = public_key if public_key is not None else env_key or banner_verify.PUBLIC_KEY
        self.fetcher, self.clock = fetcher, clock
        self.utm = load_data("solutions.json")["utm"]
        self.bundle = parse_manifest(json.dumps(load_data("banners.json"), ensure_ascii=False).encode("utf-8"), bundled=True)
        self.bundle_images = {i["id"]: {s: (Path(EXT_ROOT) / v["url"]).read_bytes() for s, v in image_specs(i)}
                              for i in self.bundle["items"]}
        try:
            encoded = load_data("banner-snapshots.json")  # prepared by the package builder
        except FileNotFoundError:
            encoded = None  # uninstalled source-tree callers only
        self._bundle = prepare(((self.bundle, self.bundle_images),), self.utm, encoded)
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
            candidates = store.load(self.root, self.key, self.allow_test)
            if candidates:
                self._state = prepare(candidates, self.utm, allow_test=self.allow_test)
            claimed, self._next_check = cache.claim_attempt(self.root, now)
            if not claimed:
                return
            data = self._fetch(self.url, MAX_MANIFEST)
            signature = self._fetch(self.url + ".sig", 128)
            doc = banner_verify.verify_manifest(data, signature, self.key, self.allow_test)
            store.check_generation(store.metadata(self.root, self.key), doc, data)
            blobs = {}
            for item in doc["items"]:
                blobs[item["id"]] = {}
                for scale, spec in image_specs(item):
                    try:
                        blob = cache.cached_image(self.root, spec, scale)
                    except (OSError, ValueError):
                        blob = self._fetch(spec["url"], spec["size"])
                        banner_verify.verify_image(blob, spec, scale)
                    blobs[item["id"]][scale] = blob
            candidates = store.publish(self.root, self.key, data, signature, blobs, self.clock(), self.version,
                                       self.allow_test)
            self._state = prepare(candidates, self.utm, allow_test=self.allow_test)
        except Exception:  # noqa: BLE001 - never log URLs, profile paths or exception details
            print("HST banners: refresh unavailable; using local content", flush=True)
        finally:
            self._lock.release()

    def _fetch(self, url, limit):
        if self.allow_test:
            return self.fetcher(url, limit, self.version, self.proxy, allow_test=True)
        return self.fetcher(url, limit, self.version, self.proxy)

    def bundled(self, compact=False):
        return self._snapshot(self._bundle, self.clock(), compact)

    def current(self, compact=False):
        """Capture a single coherent state, without ever taking the long worker/publication locks.

        compact: the first state (online, cached, installed) that has active items with compact art."""
        state = self._state
        return self._snapshot(state + self._bundle, self.clock(), compact)

    def _snapshot(self, candidates, now, compact=False):
        for doc, banners in candidates:
            eligible = [i for i in doc["items"] if active(i, now, self.version)
                        and (not compact or banners[i["id"]].has_compact())]
            if not eligible:
                continue
            unique = {i["id"]: banners[i["id"]].copy() for i in eligible}
            items = []
            for repeat in range(max(i.get("weight", 1) for i in eligible)):
                for i in eligible:
                    if repeat < i.get("weight", 1):
                        items.append(unique[i["id"]])
            return {"items": items, "rotateSeconds": doc["rotateSeconds"]}
        return {"items": [], "rotateSeconds": 10}


def get_banners(feed, compact=False):
    """Start a due refresh and immediately return an ordered snapshot, with an installed fallback."""
    try:
        feed.refresh_async()
        return feed.current(compact)
    except Exception:  # noqa: BLE001 - service failures must not escape into the editing UI
        return feed.bundled(compact)
