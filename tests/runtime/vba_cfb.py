# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal readers for MS-CFB compound files and MS-OVBA compressed containers (standard library only)."""
import struct

FREE, END = 0xFFFFFFFF, 0xFFFFFFFE


class Cfb:
    """Minimal MS-CFB reader: directory tree and stream contents."""

    def __init__(self, data):
        if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("not a compound file")
        self.data = data
        self.sector = 1 << struct.unpack_from("<H", data, 30)[0]
        self.mini = 1 << struct.unpack_from("<H", data, 32)[0]
        nfat = struct.unpack_from("<I", data, 44)[0]
        dirstart = struct.unpack_from("<I", data, 48)[0]
        self.cutoff = struct.unpack_from("<I", data, 56)[0]
        minifat = struct.unpack_from("<I", data, 60)[0]
        difat_next = struct.unpack_from("<I", data, 68)[0]
        difat = list(struct.unpack_from("<109I", data, 76))
        while difat_next not in (FREE, END):
            sector = self._sector(difat_next)
            values = struct.unpack("<%dI" % (self.sector // 4), sector)
            difat += values[:-1]
            difat_next = values[-1]
        self.fat = []
        for sid in difat[:nfat]:
            self.fat += struct.unpack("<%dI" % (self.sector // 4), self._sector(sid))
        raw_minifat = self._chain(minifat)
        self.minifat = list(struct.unpack("<%dI" % (len(raw_minifat) // 4), raw_minifat))
        raw_dir = self._chain(dirstart)
        self.entries = [self._entry(raw_dir[i:i + 128]) for i in range(0, len(raw_dir), 128)]
        self.ministream = self._chain(self.entries[0]["start"])

    def _sector(self, sid):
        start = (sid + 1) * self.sector
        return self.data[start:start + self.sector]

    def _chain(self, sid):
        out, seen = [], set()
        while sid not in (FREE, END) and sid not in seen and sid < len(getattr(self, "fat", [])):
            seen.add(sid)
            out.append(self._sector(sid))
            sid = self.fat[sid]
        return b"".join(out)

    @staticmethod
    def _entry(raw):
        length = struct.unpack_from("<H", raw, 64)[0]
        d1, d2, d3 = struct.unpack_from("<IHH", raw, 80)
        tail = raw[88:96].hex()
        return dict(name=raw[:max(0, length - 2)].decode("utf-16-le", "replace"), type=raw[66],
                    left=struct.unpack_from("<I", raw, 68)[0], right=struct.unpack_from("<I", raw, 72)[0],
                    child=struct.unpack_from("<I", raw, 76)[0],
                    clsid="%08x-%04x-%04x-%s-%s" % (d1, d2, d3, tail[:4], tail[4:]),
                    start=struct.unpack_from("<I", raw, 116)[0], size=struct.unpack_from("<Q", raw, 120)[0])

    def children(self, entry):
        out, stack = {}, [entry["child"]]
        while stack:
            sid = stack.pop()
            if sid == FREE or sid >= len(self.entries):
                continue
            item = self.entries[sid]
            out[item["name"]] = item
            stack += [item["left"], item["right"]]
        return out

    def read(self, entry):
        if entry["size"] >= self.cutoff:
            return self._chain(entry["start"])[:entry["size"]]
        out, sid = [], entry["start"]
        while sid not in (FREE, END) and sid < len(self.minifat):
            start = sid * self.mini
            out.append(self.ministream[start:start + self.mini])
            sid = self.minifat[sid]
        return b"".join(out)[:entry["size"]]


def decompress(data):
    """MS-OVBA 2.4.1 RLE decompression."""
    if not data or data[0] != 1:
        raise ValueError("bad compressed container")
    out, pos = bytearray(), 1
    while pos + 2 <= len(data):
        header = struct.unpack_from("<H", data, pos)[0]
        size = (header & 0x0FFF) + 3
        end, pos = pos + size, pos + 2
        chunk_start = len(out)
        if not header & 0x8000:
            out += data[pos:pos + 4096]
            pos = end
            continue
        while pos < end:
            flags = data[pos]
            pos += 1
            for bit in range(8):
                if pos >= end:
                    break
                if flags >> bit & 1:
                    token = struct.unpack_from("<H", data, pos)[0]
                    pos += 2
                    done = len(out) - chunk_start
                    bits = 4
                    while (1 << bits) < done and bits < 12:
                        bits += 1
                    length = (token & (0xFFFF >> bits)) + 3
                    offset = (token >> (16 - bits)) + 1
                    for _ in range(length):
                        out.append(out[-offset])
                else:
                    out.append(data[pos])
                    pos += 1
    return bytes(out)
