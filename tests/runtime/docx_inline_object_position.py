# SPDX-License-Identifier: AGPL-3.0-only
"""Inline objects in a run with <w:position> (hst-docx-inline-object-position.patch).

Word puts an inline object's bottom on the baseline and moves the whole run by w:position
(half-points; MathType writes it so the formula baseline meets the text baseline). The import
gives the object VertOrient NONE at -height - position*2540/144; .docx and .doc export write
the position back. Used by check-docx-word-interop.py.
"""
import os
import re
import struct
import zipfile
import zlib

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
NS = (W + ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
      ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
      ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
      ' xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
      ' xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"')
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# half-points per object: DrawingML picture, VML picture, picture without w:position
EXPECTED = {"drawing": -14, "vml": -10, "plain": 0}
HEIGHT_EMU = 457200  # 0.5 in = 1270 mm100


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\0" + b"\0\0\0" * 4 for _ in range(4))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def drawing(name, pid):
    return (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="457200" cy="{HEIGHT_EMU}"/>'
            f'<wp:docPr id="{pid}" name="{name}"/><a:graphic><a:graphicData '
            'uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
            f'<pic:cNvPr id="{pid}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rImg"/>'
            '<a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="457200" cy="{HEIGHT_EMU}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '</pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>')


def run(position, content):
    rpr = f'<w:rPr><w:position w:val="{position}"/></w:rPr>' if position else ""
    return f"<w:r>{rpr}{content}</w:r>"


def write_docx(path):
    vml = ('<w:pict><v:shape id="vml" type="#_x0000_t75" style="width:36pt;height:36pt">'
           '<v:imagedata r:id="rImg" o:title=""/></v:shape></w:pict>')
    text = '<w:r><w:t xml:space="preserve"> chữ </w:t></w:r>'
    body = (f'<w:p>{text}{run(EXPECTED["drawing"], drawing("drawing", 1))}{text}{run(EXPECTED["vml"], vml)}'
            f'{text}{run(0, drawing("plain", 2))}{text}</w:p>')
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
        'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
        f'package/2006/relationships"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/>'
        '</Relationships>',
        "word/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
        f'openxmlformats.org/package/2006/relationships"><Relationship Id="rImg" Type="{REL}/image" '
        'Target="media/image1.png"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8"?><w:document {NS}><w:body>{body}</w:body></w:document>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, data in files.items():
            package.writestr(name, data)
        package.writestr("word/media/image1.png", png())


def positions(doc):
    """Half-points each inline object is lowered/raised by, in document order (None = not NONE-oriented)."""
    found = []
    portions = doc.getText().createEnumeration().nextElement().createEnumeration()
    while portions.hasMoreElements():
        portion = portions.nextElement()
        if portion.TextPortionType != "Frame":
            continue
        contents = portion.createContentEnumeration("com.sun.star.text.TextContent")
        while contents.hasMoreElements():
            obj = contents.nextElement()
            try:
                height = obj.getSize().Height  # drawing shapes
            except AttributeError:
                height = obj.Height  # Writer frames: graphics, OLE objects
            if obj.VertOrient != 0:
                found.append(0 if obj.VertOrient in (1, 3) else None)  # TOP/BOTTOM: on the baseline
            else:
                found.append(round(-(obj.VertOrientPosition + height) * 144 / 2540))
    return found


def run_positions(path):
    body = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    runs = re.findall(r"<w:r>(?:(?!</w:r>).)*?(?:<w:drawing>|<w:pict>|<mc:AlternateContent>).*?</w:r>", body, re.S)
    duplicated = [r for r in runs if len(re.findall(r"<w:position ", r)) > 1]
    return [int(m.group(1)) if (m := re.search(r'<w:position w:val="(-?\d+)"', r)) else 0 for r in runs], duplicated


def check_inline_object_position(desktop, out, expect, prop):
    import uno
    hidden = (prop("Hidden", True),)
    wanted = list(EXPECTED.values())
    source = os.path.join(out, "inline-position.docx")
    write_docx(source)
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(source), "_blank", 0, hidden)
    expect("inline objects with w:position: imported position (half-points)", positions(doc), wanted)
    saved = {}
    for ext, filter_name in (("docx", "MS Word 2007 XML"), ("doc", "MS Word 97")):
        saved[ext] = os.path.join(out, f"inline-position-saved.{ext}")
        doc.storeToURL(uno.systemPathToFileUrl(saved[ext]), (prop("FilterName", filter_name),))
    doc.close(True)
    written, duplicated = run_positions(saved["docx"])
    expect("inline objects: .docx export writes w:position on their runs", written, wanted)
    expect("inline objects: one w:position per run", duplicated, [])
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(saved["docx"]), "_blank", 0, hidden)
    expect("inline objects: position after .docx round trip", positions(doc), wanted)
    doc.close(True)
    # .doc keeps sprmCHpsPos for pictures and OLE objects; Writer's .doc import turns a lowered
    # single picture into CHAR_CENTER (None here), so only check that it no longer sits on the baseline.
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(saved["doc"]), "_blank", 0, hidden)
    expect("inline objects: .doc keeps the picture off the baseline", positions(doc)[0] != 0, True)
    doc.close(True)
