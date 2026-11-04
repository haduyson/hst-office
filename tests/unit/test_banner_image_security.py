# SPDX-License-Identifier: AGPL-3.0-only
import io
import json
from pathlib import Path
import struct
import zlib

from PIL import Image

from _paths import ROOT
from banner_fixtures import Remote, image_spec, signed
from banner_review_fixtures import FeedCase
from hst_office import banner_cache as cache, banner_store as store, banner_verify as verify


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def bomb(width, height):
    header = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    # Stream compression avoids allocating the 900M-pixel raster during the test.
    compressor = zlib.compressobj()
    row = bytes(1 + (width + 7) // 8)
    encoded = b"".join(compressor.compress(row) for _ in range(height)) + compressor.flush()
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", encoded) + chunk(b"IEND", b"")


def raster(kind, size=(360, 104)):
    out = io.BytesIO()
    Image.new("RGB", size, "#0072bb").save(out, format=kind)
    return out.getvalue()


class ImageSecurityTests(FeedCase):
    def test_exact_scale_dimensions_for_each_supported_format(self):
        for kind in ("PNG", "JPEG", "WEBP"):
            for level in (1, 2, 3):
                data = raster(kind, (360 * level, 104 * level))
                self.assertIn(verify.verify_image(data, image_spec(data), f"{level}x"), (".png", ".jpg", ".webp"))
                with self.assertRaises(ValueError):
                    verify.verify_image(data, image_spec(data), f"{level % 3 + 1}x")

    def test_signed_valid_formats_survive_offline_restart(self):
        for kind in ("PNG", "JPEG", "WEBP"):
            remote = Remote()
            remote.doc["generatedAt"] = f"2026-11-{4 + ('PNG', 'JPEG', 'WEBP').index(kind):02d}T00:00:00Z"
            payloads = {}
            for scale, spec in remote.doc["items"][0]["image"].items():
                data = raster(kind, (360 * int(scale[0]), 104 * int(scale[0])))
                spec.update(image_spec(data))
                payloads[spec["url"]] = data
            remote.data, remote.signature = signed(remote.doc)
            def fetch(url, *args):
                return payloads[url] if url in payloads else remote(url, *args)
            feed = self.feed(fetch)
            self.assertEqual(self.refresh(feed)["items"][0].image_bytes_for_scale(1), payloads[next(iter(payloads))])
            remote.offline = True
            self.assertEqual(self.refresh(self.feed(remote))["items"][0]["name"], "Online AIOS")
            self.now += 86400

    def test_signed_oversized_images_never_publish_or_load(self):
        for kind in ("PNG", "JPEG", "WEBP", "BOMB"):
            with self.subTest(kind=kind):
                data = bomb(30000, 30000) if kind == "BOMB" else raster(kind, (1081, 312))
                remote = Remote()
                spec = remote.doc["items"][0]["image"]["1x"]
                spec.update(image_spec(data))
                remote.data, remote.signature = signed(remote.doc)
                def fetch(url, *args):
                    return data if url == spec["url"] else remote(url, *args)
                feed = self.feed(fetch)
                self.refresh(feed)
                self.assertFalse((self.root / "current.json").exists())
                cache.atomic_write(self.root / "current.json", json.dumps(store.envelope(remote.data, remote.signature)).encode())
                cache.atomic_write(cache.image_path(self.root, spec, "." + kind.lower().replace("jpeg", "jpg").replace("bomb", "png")), data)
                self.assertEqual(store.load(self.root, feed.key), ())
                (self.root / "current.json").unlink()
                self.now += 86400

    def test_small_compressed_bomb_and_integer_boundaries(self):
        data = bomb(30000, 30000)
        self.assertLess(len(data), 300 * 1024)
        with self.assertRaises(ValueError):
            verify.verify_image(data, image_spec(data))
        for width, height in ((0, 104), (360, 0), (2**32 - 1, 104), (360, 2**32 - 1)):
            body = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
            data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", body) + chunk(b"IDAT", b"x") + chunk(b"IEND", b"")
            with self.assertRaises(ValueError):
                verify.verify_image(data, image_spec(data))

    def test_animation_and_malformed_headers_fail_closed(self):
        png = (Path(ROOT) / "extensions/hst-vietnamese-tools/banners/aios@1x.png").read_bytes()
        apng = png[:33] + chunk(b"acTL", struct.pack(">II", 2**32 - 1, 0)) + png[33:]
        for data in (apng, png[:-1], png[:29] + b"bad!" + png[33:]):
            with self.assertRaises(ValueError):
                verify.verify_image(data, image_spec(data))
        out = io.BytesIO()
        Image.new("RGB", (360, 104), "blue").save(out, format="WEBP", save_all=True,
                                                  append_images=[Image.new("RGB", (360, 104), "red")])
        with self.assertRaises(ValueError):
            verify.verify_image(out.getvalue(), image_spec(out.getvalue()))
        for kind in ("JPEG", "WEBP"):
            data = raster(kind)
            for malformed in (data[:20], data[:-1], data + b"trailing"):
                with self.assertRaises(ValueError):
                    verify.verify_image(malformed, image_spec(malformed))

    def test_jpeg_and_webp_header_dimension_overflows(self):
        jpeg = raster("JPEG")
        pos = jpeg.index(b"\xff\xc0")
        corrupt = jpeg[:pos + 5] + b"\xff\xff\xff\xff" + jpeg[pos + 9:]
        webp = raster("WEBP")
        pos = webp.index(b"\x9d\x01\x2a") + 3
        large_webp = webp[:pos] + b"\xff\x3f\xff\x3f" + webp[pos + 4:]
        for data in (corrupt, large_webp):
            with self.assertRaises(ValueError):
                verify.verify_image(data, image_spec(data))
