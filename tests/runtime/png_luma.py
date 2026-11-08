# SPDX-License-Identifier: AGPL-3.0-only
"""Read an 8-bit PNG (grey, RGB, RGBA, grey+alpha; no interlace) into rows of luma values, with zlib only: the office's
own Python has no imaging library. Transparent pixels read as white (the Start Center draws thumbnails on white)."""
import struct
import zlib

_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def _unfilter(raw, width, height, bpp):
    stride = width * bpp
    rows, previous, pos = [], bytearray(stride), 0
    for _ in range(height):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = previous[i]
            corner = previous[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 0xFF
        rows.append(line)
        previous = line
    return rows


def read(data):
    """(width, height, rows of luma 0-255) of the PNG bytes `data`."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, header = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    width, height, depth, colour, _compression, _filter, interlace = header
    if depth != 8 or interlace or colour not in _CHANNELS:
        raise ValueError("unsupported PNG: depth %d colour %d interlace %d" % (depth, colour, interlace))
    bpp = _CHANNELS[colour]
    rows = _unfilter(zlib.decompress(idat), width, height, bpp)
    luma = []
    for line in rows:
        out = []
        for x in range(width):
            px = line[x * bpp:(x + 1) * bpp]
            if colour in (0, 4):
                value, alpha = px[0], px[1] if colour == 4 else 255
            else:
                value, alpha = (299 * px[0] + 587 * px[1] + 114 * px[2]) // 1000, px[3] if colour == 6 else 255
            out.append((value * alpha + 255 * (255 - alpha)) // 255)
        luma.append(out)
    return width, height, luma


def band_stats(luma, top, bottom, left=0.05, right=0.95):
    """(darkest luma, share of pixels darker than 160) in the band [top, bottom) x [left, right) of fractions."""
    height, width = len(luma), len(luma[0]) if luma else 0
    values = [v for row in luma[int(height * top):int(height * bottom)] for v in row[int(width * left):int(width * right)]]
    if not values:
        return 255, 0.0
    return min(values), sum(v < 160 for v in values) / len(values)
