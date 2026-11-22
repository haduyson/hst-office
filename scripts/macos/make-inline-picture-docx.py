# SPDX-License-Identifier: AGPL-3.0-only
"""Write a small .docx with two as-character (wp:inline) PNG pictures in centred paragraphs between text lines.

  make-inline-picture-docx.py <out.docx>

The layout matches a worksheet saved by Writer: the first picture carries a crop (a:srcRect) and both lock their
aspect ratio, nothing is anchored, locked, behind the text or in a header. The first picture is a pale yellow
square on white, so a probe can find it on screen by colour. Standard library only.
"""
import struct
import sys
import zipfile
import zlib


def png(width, height, pixel):
    """An 8-bit RGB PNG whose pixel(x, y) returns an (r, g, b) tuple."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def square(x, y):
    return (249, 231, 159) if 380 <= x < 620 and 100 <= y < 340 else (255, 255, 255)


def stripe(x, y):
    return (93, 173, 226) if 100 <= y < 420 and (x // 100) % 2 == 0 else (255, 255, 255)


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def text_para(text):
    return f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def picture_para(rid, pid, cx, cy, crop):
    src = '<a:srcRect l="5531" t="16472" r="9747" b="13593"/>' if crop else ""
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{pid}" name="image{pid}.png"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{pid}" name="image{pid}.png"/>'
        '<pic:cNvPicPr><a:picLocks noChangeAspect="1" noChangeArrowheads="1"/></pic:cNvPicPr></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/>{src}<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr bwMode="auto"><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def document():
    body = "".join([
        text_para("Line one above the first picture."),
        text_para("Question 3. How many shapes are in the picture below?"),
        picture_para("rId2", 1, 2479017, 900163, True),
        text_para("A. 1      B. 2      C. 3      D. 4"),
        text_para("Question 7. Look at the picture below."),
        picture_para("rId3", 2, 3931920, 1572895, False),
        text_para("Last line."),
    ])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="864" w:right="1008" w:bottom="864" w:left="1008" w:header="0" w:footer="0" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>')


CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>')
IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId2" Type="{IMAGE}" Target="media/image1.png"/>'
    f'<Relationship Id="rId3" Type="{IMAGE}" Target="media/image2.png"/></Relationships>')


def main(out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", document())
        z.writestr("word/media/image1.png", png(1000, 440, square))
        z.writestr("word/media/image2.png", png(1300, 520, stripe))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
