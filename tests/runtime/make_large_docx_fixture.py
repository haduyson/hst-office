#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Write a synthetic large .docx for the recovery checks: ~19 MB, so a save of it takes long enough to be killed
part-way.

The document is generated, not copied from anywhere: numbered paragraphs of fixed Vietnamese and English filler
text, one table, and one picture of seeded random noise (incompressible, so the zip stays as large as the pixels).
It holds no personal data. The same arguments always give the same bytes (fixed seed, fixed zip timestamps).

Usage: python3 make_large_docx_fixture.py OUT.docx [--picture-side 2500] [--paragraphs 400]
Runs with any Python 3.9+ (the office's own python.exe too); only the standard library is used.
"""
import argparse
import random
import struct
import sys
import zipfile
import zlib
from xml.sax.saxutils import escape

STAMP = (2026, 1, 1, 0, 0, 0)  # fixed zip entry time: reproducible output
TEXT = ("Đoạn văn mẫu số {n}: văn bản tổng hợp để kiểm tra lưu và khôi phục tài liệu lớn. "
        "Sample paragraph {n}: synthetic text for the large document save and recovery check.")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EMU_PER_PX = 9525

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdImg1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/noise.png"/>
</Relationships>"""


def noise_png(side, seed=1031):
    """An RGB PNG of side x side seeded random pixels, stored without compression (zlib level 0)."""
    rng = random.Random(seed)
    rows = b"".join(b"\x00" + rng.randbytes(side * 3) for _ in range(side))  # filter byte 0 per row

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 0)) + chunk(b"IEND", b"")


def paragraph(text):
    return '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escape(text)


def table(rows, cols):
    cells = lambda r: "".join('<w:tc><w:tcPr><w:tcW w:w="1800" w:type="dxa"/></w:tcPr>%s</w:tc>'
                              % paragraph("Ô %d.%d / cell %d.%d" % (r, c, r, c)) for c in range(1, cols + 1))
    grid = "".join('<w:gridCol w:w="1800"/>' for _ in range(cols))
    body = "".join("<w:tr>%s</w:tr>" % cells(r) for r in range(1, rows + 1))
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
            "<w:tblGrid>%s</w:tblGrid>%s</w:tbl>" % (grid, body))


def picture(side_px, shown_px=400):
    emu = shown_px * EMU_PER_PX
    return (
        '<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        '<wp:extent cx="%d" cy="%d"/><wp:docPr id="1" name="Noise"/>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:nvPicPr><pic:cNvPr id="1" name="noise.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="rIdImg1"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>" % (emu, emu, emu, emu))


def document(paragraphs, side):
    half = paragraphs // 2
    body = "".join(paragraph(TEXT.format(n=n)) for n in range(1, half + 1))
    body += table(20, 4) + picture(side)
    body += "".join(paragraph(TEXT.format(n=n)) for n in range(half + 1, paragraphs + 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="%s" xmlns:r="%s" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            '<w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>'
            % (W_NS, R_NS, body))


def write(path, side=2500, paragraphs=400):
    parts = [("[Content_Types].xml", CONTENT_TYPES.encode(), zipfile.ZIP_DEFLATED),
             ("_rels/.rels", ROOT_RELS.encode(), zipfile.ZIP_DEFLATED),
             ("word/_rels/document.xml.rels", DOC_RELS.encode(), zipfile.ZIP_DEFLATED),
             ("word/document.xml", document(paragraphs, side).encode("utf-8"), zipfile.ZIP_DEFLATED),
             ("word/media/noise.png", noise_png(side), zipfile.ZIP_STORED)]  # noise does not compress
    with zipfile.ZipFile(path, "w") as archive:
        for name, data, method in parts:
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = method
            archive.writestr(info, data)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--picture-side", type=int, default=2500, help="noise picture side in px (2500: ~18.8 MB)")
    parser.add_argument("--paragraphs", type=int, default=400)
    args = parser.parse_args(argv)
    if not 16 <= args.picture_side <= 8000 or not 1 <= args.paragraphs <= 100000:
        parser.error("--picture-side must be 16..8000 and --paragraphs 1..100000")
    write(args.out, args.picture_side, args.paragraphs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
