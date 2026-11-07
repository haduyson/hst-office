# SPDX-License-Identifier: AGPL-3.0-only
"""Signed local banner feed, artwork and package builder fixtures."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

from PIL import Image

from _paths import ROOT
from hst_office import ed25519
from hst_office.banner_urls import TEST_KEY_ENV, TEST_URL_ENV

BASE = "http://127.0.0.1:8032/hst-office/"
TEST_FEED = BASE + "banners.json"
SEED = os.urandom(32)
TEST_KEY = ed25519.secret_to_public(SEED)
ENV = {TEST_URL_ENV: TEST_FEED, TEST_KEY_ENV: TEST_KEY.hex()}


def png(size, colour):
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()


def spec(url, data):
    return {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def local_feed():
    """Manifest in the hstsystem test layout: one item with compact art, one without."""
    blobs, items = {}, []
    for order, (slug, colour, compact) in enumerate((("aios", "#0072bb", True), ("echatbot", "#d33", False))):
        item = {"id": slug, "name": slug.upper(), "tagline": "Test " + slug, "url": BASE + "go/" + slug,
                "order": order, "image": {}}
        for n in (1, 2, 3):
            wide = png((360 * n, 104 * n), colour)
            url = f"{BASE}banners/{slug}-{hashlib.sha256(wide).hexdigest()[:12]}@{n}x.png"
            item["image"][f"{n}x"], blobs[url] = spec(url, wide), wide
            if compact:
                small = png((160 * n, 104 * n), colour)
                url = f"{BASE}banners/{slug}-compact-{hashlib.sha256(small).hexdigest()[:12]}@{n}x.png"
                item.setdefault("imageCompact", {})[f"{n}x"], blobs[url] = spec(url, small), small
        items.append(item)
    doc = {"schemaVersion": 1, "generatedAt": "2026-11-04T00:00:00Z", "rotateSeconds": 10, "items": items}
    data = json.dumps(doc).encode()
    return doc, data, base64.b64encode(ed25519.sign(SEED, data)) + b"\n", blobs


class LocalServer:
    def __init__(self):
        self.doc, self.data, self.signature, self.blobs = local_feed()
        self.calls = []

    def __call__(self, url, limit, version, proxy, allow_test=False):
        self.calls.append((url, allow_test))
        if not allow_test:
            raise OSError("release fetch must never reach the local test server")
        if url == TEST_FEED:
            return self.data
        if url == TEST_FEED + ".sig":
            return self.signature
        return self.blobs[url]


def build_extensions():
    path = Path(ROOT) / "scripts/build-extensions.py"
    spec_ = importlib.util.spec_from_file_location("build_extensions_for_test", path)
    module = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(module)
    return module
