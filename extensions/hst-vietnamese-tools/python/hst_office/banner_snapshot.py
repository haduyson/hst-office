# SPDX-License-Identifier: AGPL-3.0-only
"""Prepare unique verified buffers off the UI path; return one bounded rotation slot."""
import base64
import json
import math
from types import MappingProxyType

from .banner_schema import COMPACT_PREFIX, MAX_IMAGE, MAX_ITEMS
from .banner_urls import click_url

MAX_SNAPSHOT = 432 * 1024  # one 400 KiB base64 image plus bounded escaped metadata/header


def scale_key(scale, compact=False):
    try:
        value = float(scale)
        level = max(1, min(3, math.ceil(value))) if math.isfinite(value) else 1
    except (ValueError, TypeError, OverflowError):
        level = 1
    return (COMPACT_PREFIX if compact else "") + str(level) + "x"


class Banner(dict):
    """Snapshot mapping with immutable verified bytes and reusable serialized variants."""
    def image_bytes_for_scale(self, scale, compact=False):
        return self["images"][scale_key(scale, compact)]

    def has_compact(self):
        return scale_key(1, True) in self["images"]

    def copy(self):
        result = Banner(self, images=dict(self["images"]))
        result.serialized = self.serialized
        return result


def encoded_items(doc, images, utm, allow_test=False):
    """Called by the background worker or package builder, never by snapshot selection."""
    result = {}
    for item in doc["items"]:
        fields = {k: item[k] for k in ("id", "name", "tagline")}
        fields["click_url_with_utm"] = click_url(item["url"], utm, allow_test)
        variants = {}
        for scale, blob in images[item["id"]].items():
            if len(blob) > MAX_IMAGE:
                raise ValueError("banner image exceeds snapshot limit")
            fields["image_base64"] = base64.b64encode(blob).decode("ascii")
            value = json.dumps(fields, ensure_ascii=True, separators=(",", ":"))
            if len(value) > MAX_SNAPSHOT - 128:
                raise ValueError("banner metadata exceeds snapshot limit")
            variants[scale] = value
        result[item["id"]] = variants
    return result


def prepare(candidates, utm, encoded=None, allow_test=False):
    """Keep encoded variants and their exact verified buffers in the same published state."""
    result = []
    for doc, images in candidates:
        payloads = encoded if encoded is not None else encoded_items(doc, images, utm, allow_test)
        banners = {}
        for item in doc["items"]:
            banner = Banner({k: item[k] for k in ("id", "name", "tagline")},
                            click_url_with_utm=click_url(item["url"], utm, allow_test), images=dict(images[item["id"]]))
            banner.serialized = MappingProxyType(dict(payloads[item["id"]]))
            banners[item["id"]] = banner
        result.append((doc, banners))
    return tuple(result)


def selected_json(snapshot, scale=1, slot=0, compact=False):
    """A single image, independent of weights. Padding keeps count/index header size constant.

    compact: the compact slot of narrow windows rotates only through items with compact art (the
    wide art is never cropped); slotCount 0 tells the ribbon to hide the slot."""
    items = snapshot["items"]
    if compact is True:
        items = [i for i in items if i.has_compact()]
    count = len(items)
    if count > MAX_ITEMS * 10:
        raise ValueError("banner rotation exceeds snapshot limit")
    slot = slot % count if type(slot) is int and slot >= 0 and count else 0
    item = items[slot].serialized[scale_key(scale, compact is True)] if count else ""
    result = (f'{{"rotateSeconds":{snapshot["rotateSeconds"]:2d},"slot":{slot:3d},'
              f'"slotCount":{count:3d},"items":[' + item + "]}")
    if len(result) > MAX_SNAPSHOT:
        raise ValueError("banner response exceeds snapshot limit")
    return result
