# SPDX-License-Identifier: AGPL-3.0-only
"""Throwaway banner fixtures: no real network or production keys."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path

from _paths import ROOT
from hst_office import ed25519
from hst_office.banner_urls import FEED_URL

SEED = os.urandom(32)
KEY = ed25519.secret_to_public(SEED)
NOW = 1793750400  # 2026-11-04T00:00:00Z
VERSION = "1.0.0-beta.5"


def manifest():
    doc = json.loads((Path(ROOT) / "data/hst/banners.json").read_text())
    doc["items"] = doc["items"][:2]
    doc["items"][0]["name"] = "Online AIOS"
    for item in doc["items"]:
        for spec in item["image"].values():
            spec["url"] = "https://system.hasontech.vn/hst-office/" + spec["url"]
    return doc


def signed(doc):
    data = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    return data, base64.b64encode(ed25519.sign(SEED, data)) + b"\n"


def image_spec(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class Remote:
    def __init__(self, doc=None):
        self.doc = copy.deepcopy(manifest() if doc is None else doc)
        self.data, self.signature = signed(self.doc)
        self.calls = []
        self.offline = False
        self.bad_image = False

    def __call__(self, url, limit, version, proxy):
        self.calls.append((url, limit, version, proxy))
        if self.offline:
            raise OSError("sensitive profile information must not be logged")
        if url == FEED_URL:
            return self.data
        if url == FEED_URL + ".sig":
            return self.signature
        if self.bad_image:
            return b"not an image"
        return (Path(ROOT) / "extensions/hst-vietnamese-tools/banners" / url.rsplit("/", 1)[1]).read_bytes()
