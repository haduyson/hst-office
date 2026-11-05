# SPDX-License-Identifier: AGPL-3.0-only
"""Build a real MS-OVBA project (CFB + compressed streams) from source text in a chosen code page, standard library only.

The VBA in these files comes from this writer, not from Office, so they test what the importer does with the bytes Office stores
(code page, module and identifier names). Readers checked: HST's importer and olevba.
"""
import io
import struct
import unicodedata
import zipfile

FREE, END, FATSEC, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


TONES = "\u0300\u0301\u0303\u0309\u0323"


def nfd_for_1258(text):
    """Windows-1258 stores the five tone marks as combining characters after the base letter."""
    out = []
    for char in unicodedata.normalize("NFC", text):
        try:
            char.encode("cp1258")
            out.append(char)
        except UnicodeEncodeError:
            parts = unicodedata.normalize("NFD", char)
            tone = next(c for c in parts if c in TONES)
            out.append(unicodedata.normalize("NFC", parts.replace(tone, "")) + tone)
    return "".join(out)


def encode_source(text, codepage):
    return (nfd_for_1258(text) if codepage == 1258 else text).encode(f"cp{codepage}")


def ovba_compress(data):
    """Compressed container with literal-only tokens; each chunk holds under 4096 bytes, which fits the 4098 limit."""
    out = bytearray(b"\x01")
    for start in range(0, len(data), 3600):
        chunk = data[start:start + 3600]
        body = bytearray()
        for index in range(0, len(chunk), 8):
            body.append(0)
            body += chunk[index:index + 8]
        out += struct.pack("<H", 0xB000 | (len(body) + 2 - 3)) + body
    return bytes(out)


def is_class(source):
    """A class module's source begins with its VB_Base attribute line, as Office stores it."""
    return source.startswith('Attribute VB_Base')


def record(rid, payload):
    return struct.pack("<HI", rid, len(payload)) + payload


def dir_stream(modules, codepage, project):
    enc = project.encode("ascii")
    out = record(1, struct.pack("<I", 1)) + record(2, struct.pack("<I", 0x409)) + record(0x14, struct.pack("<I", 0x409))
    out += record(3, struct.pack("<H", codepage)) + record(4, enc) + record(5, b"") + record(0x40, b"") + record(6, b"") + record(0x3D, b"")
    out += record(7, struct.pack("<I", 0)) + record(8, struct.pack("<I", 0)) + struct.pack("<HIIH", 9, 4, 1, 0) + record(0x0C, b"") + record(0x3C, b"")
    out += record(0x0F, struct.pack("<H", len(modules))) + record(0x13, struct.pack("<H", 0xFFFF))
    for name, source in modules:
        raw, wide = encode_source(name, codepage), name.encode("utf-16-le")
        out += record(0x19, raw) + record(0x47, wide) + record(0x1A, raw) + record(0x32, wide) + record(0x1C, b"") + record(0x48, b"")
        out += record(0x31, struct.pack("<I", 0)) + record(0x1E, struct.pack("<I", 0)) + record(0x2C, struct.pack("<H", 0xFFFF))
        out += struct.pack("<HI", 0x22 if is_class(source) else 0x21, 0) + struct.pack("<HI", 0x2B, 0)
    return out + struct.pack("<HI", 0x10, 0)


def project_stream(modules, project, codepage):
    lines = ['ID="{00000000-0000-0000-0000-000000000000}"'] + [f"{'Class' if is_class(source) else 'Module'}={name}" for name, source in modules]
    lines += [f'Name="{project}"', 'HelpContextID="0"', 'VersionCompatible32="393222000"', 'CMG=""', 'DPB=""', 'GC=""', ""]
    return "\r\n".join(lines).encode(f"cp{codepage}", "replace")


class Node:
    def __init__(self, name, data=None, children=None):
        self.name, self.data, self.children = name, data, children
        self.left = self.right = self.child = NOSTREAM
        self.index = self.start = 0


def cfb(tree):
    """tree: {name: bytes | {name: bytes}}. Small streams go to the mini stream, as Office writes them."""
    def build(name, value):
        return Node(name, children=[build(k, v) for k, v in value.items()]) if isinstance(value, dict) else Node(name, data=value)

    root = Node("Root Entry", children=[build(k, v) for k, v in tree.items()])
    nodes = []

    def number(node):
        node.index = len(nodes)
        nodes.append(node)
        for child in node.children or []:
            number(child)

    number(root)

    def link(node):
        kids = sorted(node.children or [], key=lambda n: (len(n.name), n.name.upper()))
        for kid in kids:
            link(kid)

        def balance(items):
            if not items:
                return NOSTREAM
            mid = len(items) // 2
            items[mid].left, items[mid].right = balance(items[:mid]), balance(items[mid + 1:])
            return items[mid].index

        node.child = balance(kids)

    link(root)
    mini, minifat = bytearray(), []
    big = []
    for node in nodes:
        if node.data is None:
            continue
        if len(node.data) < 4096:
            count = (len(node.data) + 63) // 64
            node.start = len(minifat) if count else END
            minifat += [len(minifat) + i + 1 for i in range(count - 1)] + ([END] if count else [])
            mini += node.data.ljust(count * 64, b"\0")
        else:
            big.append(node)
    streams = [("mini", bytes(mini))] if mini else []
    fat, payload = [], bytearray()

    def place(data):
        count = (len(data) + 511) // 512
        first = len(fat)
        fat.extend(first + i + 1 for i in range(count - 1))
        fat.append(END)
        payload.extend(data.ljust(count * 512, b"\0"))
        return first

    root.start = place(streams[0][1]) if streams else END
    minifat_data = b"".join(struct.pack("<I", v) for v in minifat)
    minifat_data = minifat_data.ljust(((len(minifat_data) + 511) // 512) * 512, b"\xff")
    minifat_start = place(minifat_data) if minifat else END
    for node in big:
        node.start = place(node.data)
    directory = bytearray()
    for node in nodes:
        wide = node.name.encode("utf-16-le") + b"\0\0"
        kind = 5 if node is root else (1 if node.children is not None else 2)
        size = len(mini) if node is root else len(node.data or b"")
        start = node.start if node.data is not None or node is root else 0
        directory += wide.ljust(64, b"\0") + struct.pack("<HBBIII", len(wide), kind, 1, node.left, node.right, node.child) + b"\0" * 16 + struct.pack("<IQQIQ", 0, 0, 0, start, size)
    directory = bytes(directory).ljust(((len(directory) + 511) // 512) * 512, b"\0")
    dir_start = place(directory)
    fat_sectors = 1
    while (len(fat) + fat_sectors) * 4 > fat_sectors * 512:
        fat_sectors += 1
    first_fat = len(fat)
    fat.extend([FATSEC] * fat_sectors)
    table = b"".join(struct.pack("<I", v) for v in fat).ljust(fat_sectors * 512, b"\xff")
    difat = [first_fat + i for i in range(fat_sectors)][:109]
    header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
    header += struct.pack("<IIIIIIIII", 0, fat_sectors, dir_start, 0, 4096, minifat_start, (len(minifat_data) // 512) if minifat else 0, END, 0)
    header += b"".join(struct.pack("<I", v) for v in difat).ljust(436, b"\xff")
    return bytes(header) + bytes(payload) + table


def vba_project(modules, codepage, project="VBAProject"):
    """modules: [(name, source text)]. Returns vbaProject.bin."""
    vba = {"_VBA_PROJECT": b"\xcc\x61\xff\xff\x00\x00\x00", "dir": ovba_compress(dir_stream(modules, codepage, project))}
    for name, source in modules:
        text = f'Attribute VB_Name = "{name}"\r\n' + source.replace("\n", "\r\n")
        stream = nfd_for_1258(name) if codepage == 1258 else name  # the code page's text, read as UTF-16
        vba[stream] = ovba_compress(encode_source(text, codepage))
    return cfb({"VBA": vba, "PROJECT": project_stream(modules, project, codepage)})
