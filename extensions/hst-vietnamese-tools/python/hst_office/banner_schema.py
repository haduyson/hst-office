# SPDX-License-Identifier: AGPL-3.0-only
"""Version 1 banner manifest contract. Shared by installed clients, signing and tests."""
import datetime
import json
import re

from .banner_urls import allowed_url
from .update_logic import version_key

MAX_MANIFEST = 65536
MAX_IMAGE = 300 * 1024
MAX_ITEMS = 24
SCALES = ("1x", "2x", "3x")
INTERVAL = 86400


def _require(condition):
    if not condition:
        raise ValueError("invalid banner manifest")


def _text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit and all(ord(c) >= 32 and ord(c) != 127 for c in value)


def timestamp(value):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value))
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _image(value, bundled):
    _require(isinstance(value, dict))
    url, digest, size = value.get("url"), value.get("sha256"), value.get("size")
    if bundled:
        _require(isinstance(url, str) and re.fullmatch(r"banners/[a-z0-9-]+@[123]x\.png", url))
    else:
        _require(allowed_url(url))
    _require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest))
    _require(_integer(size, 1, MAX_IMAGE))


def _item(item, bundled):
    _require(isinstance(item, dict))
    _require(_text(item.get("id"), 64) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item["id"]))
    _require(_text(item.get("name"), 80) and _text(item.get("tagline"), 160))
    _require(allowed_url(item.get("url")))
    _require(_integer(item.get("order"), 0, 9999))
    _require(_integer(item.get("weight", 1), 1, 10))
    images = item.get("image")
    _require(isinstance(images, dict) and set(images) == set(SCALES))
    for value in images.values():
        _image(value, bundled)
    for field in ("startAt", "endAt"):
        if field in item:
            timestamp(item[field])
    if "startAt" in item and "endAt" in item:
        _require(timestamp(item["startAt"]) < timestamp(item["endAt"]))
    for field in ("minVersion", "maxVersion"):
        if field in item:
            _require(_text(item[field], 80))
            version_key(item[field])
    if "minVersion" in item and "maxVersion" in item:
        _require(version_key(item["minVersion"]) <= version_key(item["maxVersion"]))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def parse_manifest(data, bundled=False):
    """Validate before use; bundled allows only controlled paths under the extension's banners directory."""
    _require(isinstance(data, bytes) and 0 < len(data) <= MAX_MANIFEST)
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=_unique,
                         parse_constant=lambda _: _require(False))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid banner JSON") from exc
    _require(isinstance(doc, dict) and type(doc.get("schemaVersion")) is int and doc["schemaVersion"] == 1)
    timestamp(doc.get("generatedAt"))
    rotate = doc.get("rotateSeconds", 10)
    _require(type(rotate) is int)
    doc["rotateSeconds"] = max(5, min(60, rotate))
    items = doc.get("items")
    _require(isinstance(items, list) and 1 <= len(items) <= MAX_ITEMS)
    for item in items:
        _item(item, bundled)
    _require(len({i["id"] for i in items}) == len(items))
    doc["items"] = sorted(items, key=lambda i: (i["order"], i["id"]))
    return doc


def active(item, now, version):
    """start inclusive, end exclusive; version endpoints inclusive (SemVer prereleases included)."""
    current = version_key(version)
    return (("startAt" not in item or timestamp(item["startAt"]) <= now)
            and ("endAt" not in item or now < timestamp(item["endAt"]))
            and ("minVersion" not in item or version_key(item["minVersion"]) <= current)
            and ("maxVersion" not in item or current <= version_key(item["maxVersion"])))
