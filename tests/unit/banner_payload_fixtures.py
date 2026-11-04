# SPDX-License-Identifier: AGPL-3.0-only
"""Maximum-size signed campaigns and an isolated, plain-Python service boundary."""
import copy
import importlib.util
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
from unittest.mock import patch
import zlib

from _paths import ROOT
from banner_fixtures import Remote, image_spec, manifest, signed
from hst_office.banner_schema import MAX_IMAGE, MAX_ITEMS


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def maximum_png(level, identifier):
    header = struct.pack(">IIBBBBB", 360 * level, 104 * level, 8, 2, 0, 0, 0)
    pixels = zlib.compress(bytes((1 + 360 * level * 3) * 104 * level))
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels)
    padding = bytes([identifier]) + bytes(MAX_IMAGE - len(body) - 25)
    return body + chunk(b"npAD", padding) + chunk(b"IEND", b"")


class MaximumRemote(Remote):
    def __init__(self, weight=10):
        doc = manifest()
        template = doc["items"][0]
        doc["items"], self.payloads = [], {}
        for index in range(MAX_ITEMS):
            item = copy.deepcopy(template)
            item.update(id=f"banner-{index:02}", order=index, weight=weight)
            for level in (1, 2, 3):
                data = maximum_png(level, index)
                url = f"https://system.hasontech.vn/hst-office/{index}-{level}.png"
                item["image"][f"{level}x"] = dict(image_spec(data), url=url)
                self.payloads[url] = data
            doc["items"].append(item)
        super().__init__(doc)

    def set_weight(self, weight):
        self.doc["generatedAt"] = "2026-11-05T00:00:00Z"
        for item in self.doc["items"]:
            item["weight"] = weight
        self.data, self.signature = signed(self.doc)

    def __call__(self, url, *args):
        return self.payloads[url] if url in self.payloads else super().__call__(url, *args)


def service_module():
    # Load only the product boundary; do not replace modules used by other suites.
    stubs = {"uno": SimpleNamespace(), "unohelper": SimpleNamespace(Base=type("Base", (), {})),
             "com.sun.star.lang": SimpleNamespace(XServiceInfo=type("XServiceInfo", (), {})),
             "com.sun.star.task": SimpleNamespace(XJob=type("XJob", (), {})),
             "hst_office.update_config": SimpleNamespace(_node=None),
             "hst_office.update_ui": SimpleNamespace(proxy=None)}
    path = Path(ROOT) / "extensions/hst-vietnamese-tools/python/hst_office/banner_uno.py"
    spec = importlib.util.spec_from_file_location("hst_office._payload_service_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def execute(module, feed, scale=3, slot=0):
    arguments = tuple(SimpleNamespace(Name=k, Value=v) for k, v in (("Scale", scale), ("Slot", slot)))
    with patch.object(module, "feed_for_context", return_value=feed):
        return module.BannerService(None).execute(arguments)
