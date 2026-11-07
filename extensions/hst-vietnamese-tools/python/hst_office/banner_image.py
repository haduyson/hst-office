# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded static raster headers; never allocate pixels while validating a feed."""
import struct
import zlib

from .banner_schema import COMPACT_PREFIX, COMPACT_SIZE

WIDE_SIZE = (360, 104)
SIZES = {(w * n, h * n) for w, h in (WIDE_SIZE, COMPACT_SIZE) for n in (1, 2, 3)}


def expected_size(scale):
    """Exact pixel size for an image key: 1x..3x wide art, c1x..c3x compact art."""
    compact = scale.startswith(COMPACT_PREFIX)
    width, height = COMPACT_SIZE if compact else WIDE_SIZE
    factor = int(scale[len(COMPACT_PREFIX)] if compact else scale[0])
    return width * factor, height * factor


def dimensions(width, height, scale=None):
    if (width, height) not in SIZES or (scale and (width, height) != expected_size(scale)):
        raise ValueError("invalid banner dimensions")
    return width, height


def png(data):
    pos, size, seen_data = 8, None, False
    while pos + 12 <= len(data):
        count = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        end = pos + 8 + count
        if end + 4 > len(data) or zlib.crc32(data[pos + 4:end]) != int.from_bytes(data[end:end + 4], "big"):
            break
        body = data[pos + 8:end]
        if size is None and kind != b"IHDR":
            break
        if kind == b"IHDR":
            if size is not None or count != 13:
                break
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if depth not in depths.get(color, ()) or comp or filt or interlace not in (0, 1):
                break
            size = dimensions(width, height)
        elif kind in (b"acTL", b"fcTL", b"fdAT"):
            break
        elif kind == b"IDAT":
            seen_data = True
        elif kind == b"IEND":
            if count == 0 and seen_data and end + 4 == len(data):
                return size
            break
        pos = end + 4
    raise ValueError("invalid static PNG")


def jpeg(data):
    pos, size, scanned = 2, None, False
    while pos < len(data):
        if data[pos] != 255:
            break
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            break
        kind = data[pos]
        pos += 1
        if kind == 0xD9:
            if size and scanned and pos == len(data):
                return size
            break
        if kind in (0, 0xD8) or 0xD0 <= kind <= 0xD7 or pos + 2 > len(data):
            break
        count = int.from_bytes(data[pos:pos + 2], "big")
        end = pos + count
        if count < 2 or end > len(data):
            break
        body = data[pos + 2:end]
        if kind in (0xC0, 0xC1, 0xC2):
            if size or len(body) < 6 or body[0] != 8 or body[5] not in (1, 3, 4) or len(body) != 6 + 3 * body[5]:
                break
            size = dimensions(int.from_bytes(body[3:5], "big"), int.from_bytes(body[1:3], "big"))
        elif 0xC0 <= kind <= 0xCF and kind not in (0xC4, 0xCC):
            break  # unsupported frames
        elif kind in (0xDC, 0xDE, 0xDF):
            break  # dimensions may not change after SOF
        if kind == 0xDA:
            if not size or len(body) < 4 or len(body) != 4 + 2 * body[0]:
                break
            scanned = True
            while True:
                end = data.find(b"\xff", end)
                if end < 0 or end + 1 >= len(data):
                    raise ValueError("truncated JPEG scan")
                if data[end + 1] == 0 or 0xD0 <= data[end + 1] <= 0xD7:
                    end += 2
                else:
                    break
        pos = end
    raise ValueError("invalid static JPEG")


def webp(data):
    if len(data) < 20 or int.from_bytes(data[4:8], "little") != len(data) - 8:
        raise ValueError("invalid WebP length")
    pos, canvas, size = 12, None, None
    while pos + 8 <= len(data):
        kind, count = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "little")
        end = pos + 8 + count
        if end + count % 2 > len(data):
            break
        body = data[pos + 8:end]
        if kind == b"VP8X":
            if pos != 12 or count != 10 or body[0] & 0xC3 or any(body[1:4]):
                break  # animation and reserved bits
            canvas = dimensions(1 + int.from_bytes(body[4:7], "little"), 1 + int.from_bytes(body[7:10], "little"))
        elif kind in (b"ANIM", b"ANMF"):
            break
        elif kind in (b"VP8 ", b"VP8L"):
            if size:
                break
            if kind == b"VP8 ":
                if count < 10 or body[0] & 1 or body[3:6] != b"\x9d\x01\x2a":
                    break
                size = dimensions(int.from_bytes(body[6:8], "little") & 0x3FFF,
                                  int.from_bytes(body[8:10], "little") & 0x3FFF)
            else:
                if count < 5 or body[0] != 0x2F or body[4] & 0xE0:
                    break
                bits = int.from_bytes(body[1:5], "little")
                size = dimensions(1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
        pos = end + count % 2
    else:
        if pos == len(data) and size and (canvas is None or canvas == size):
            return size
    raise ValueError("invalid static WebP")


def inspect(data, scale=None):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        size, suffix = png(data), ".png"
    elif data.startswith(b"\xff\xd8"):
        size, suffix = jpeg(data), ".jpg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        size, suffix = webp(data), ".webp"
    else:
        raise ValueError("invalid banner image type")
    dimensions(*size, scale=scale)
    return suffix
