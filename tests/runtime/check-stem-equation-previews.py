# SPDX-License-Identifier: AGPL-3.0-only
"""Equation previews (MathType-style OLE objects) in Word documents: Vietnamese text and PDF export.

Usage: python3 tests/runtime/check-stem-equation-previews.py [--instdir upstream/libreoffice/instdir]
                                                             [--out tests/output/stem-equations] [--objects 60]

Builds a small .docx itself (no downloaded data): N OLE objects with ProgID Equation.DSMT4 whose
WMF previews hold text in Times New Roman, in the TCVN3 font .VnTime and in the VNI font
VNI-Times, as MathType writes them in Vietnamese exam papers; one object with an EMF preview
(.VnTime/VNI text); one WMF with old MathType Euclid fonts and a Symbol long arrow; two OMML
equations in 12 pt and 14 pt paragraphs. Loads it headless, exports PDF and checks:
  * the PDF text layer holds the decoded Vietnamese words ("rắn", "Hòa tan"): previews are exported
    as vectors and TCVN3/VNI bytes are decoded (before: no text, or "r¾n" / "Hoøa"), WMF and EMF;
  * Euclid Math Two "R" becomes U+211D and Euclid Fraktur "g" U+1D524 in the PDF text;
  * Linux without the Symbol font: the Symbol arrow is drawn with URW Standard Symbols PS
    (pieces that join) when fonts-urw-base35 is installed, not OpenSymbol;
  * the OMML equation in a 14 pt paragraph is 14/12 the size of the same one in a 12 pt paragraph
    (Word sets equations in the text size; before: both 12 pt);
  * the PDF carries no raster image for the previews (before: one bitmap per equation);
  * export time (reported; evidence.json).
Exit 1 on any failure.
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wmf_record(function, words):
    return struct.pack("<IH", 3 + len(words), function) + struct.pack(f"<{len(words)}H", *words)


def byte_words(data):
    data = data + b"\0" * (len(data) % 2)
    return list(struct.unpack(f"<{len(data) // 2}H", data))


def wmf_font(face, height=240):
    logfont = struct.pack("<hhhhhBBBBBBBB", height, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0x12)
    return (wmf_record(0x02FB, byte_words(logfont + face.encode("latin1").ljust(32, b"\0")))
            + wmf_record(0x012D, [0]))


def wmf_text(x, y, data):
    words = [y, x, len(data), 0] + byte_words(data) + [110] * len(data)
    return wmf_record(0x0A32, words) + wmf_record(0x01F0, [0])


def equation_wmf():
    """Placeable WMF, 2000x1000 units at 1440/inch, like a MathType preview."""
    body = (wmf_record(0x0103, [8]) + wmf_record(0x020B, [0, 0]) + wmf_record(0x020C, [1000, 2000])
            + wmf_record(0x012E, [24]) + wmf_record(0x0102, [1])  # TA_BASELINE, transparent
            + wmf_font("Times New Roman") + wmf_text(60, 300, b"NaCl + AgNO3")
            + wmf_font(".VnTime") + wmf_text(60, 600, b"(r\xben) \xae\xc6c")  # (rắn) đặc
            + wmf_font("VNI-Times") + wmf_text(60, 900, b"Ho\xf8a tan")  # Hòa tan
            + wmf_record(0x0000, []))
    return placeable_wmf(body)


def emf_record(rtype, dwords):
    return struct.pack("<II", rtype, 8 + 4 * len(dwords)) + struct.pack(f"<{len(dwords)}I", *dwords)


def emf_font(face):
    name = face.encode("utf-16-le").ljust(64, b"\0")
    dwords = [1, (-12) & 0xFFFFFFFF, 0, 0, 0, 400, 0x01000000, 0] + list(struct.unpack("<16I", name))
    return emf_record(82, dwords) + emf_record(37, [1])


def emf_text(y, text, wide):
    raw = text.encode("utf-16-le") if wide else text.encode("latin1")
    raw = raw.ljust((len(raw) + 3) & ~3, b"\0")
    dwords = [0, 0, 160, 80, 1, 0, 0, 5, y, len(text), 76, 0, 0, 0, 160, 80, 76 + len(raw)]
    return emf_record(84 if wide else 83, dwords + list(struct.unpack(f"<{len(raw) // 4}I", raw)) + [7] * len(text))


def equation_emf():
    """EMF preview (MathType 7 / ChemDraw style) with text in legacy Vietnamese fonts."""
    body = (emf_font(".VnTime") + emf_text(20, "CaCO3 (r\u00ben)", True) + emf_text(45, "\u00ae\u00c6c", False)
            + emf_record(40, [1]) + emf_font("VNI-Times") + emf_text(70, "Ho\u00f8a tan", True)
            + emf_record(14, [0, 16, 20]))
    header_len = 88
    header = emf_record(1, [0, 0, 160, 80, 0, 0, 5000, 2500, 0x464D4520, 0x10000, header_len + len(body), 10, 3,
                            0, 0, 0, 1024, 768, 320, 240])
    return header + body


def euclid_arrow_wmf():
    """Old MathType fonts: Euclid Math Two R (double-struck), Euclid Fraktur g; a Symbol long arrow."""
    body = (wmf_record(0x0103, [8]) + wmf_record(0x020B, [0, 0]) + wmf_record(0x020C, [1000, 2000])
            + wmf_record(0x012E, [24]) + wmf_record(0x0102, [1])
            + wmf_font("Euclid Math Two") + wmf_text(60, 300, b"R")
            + wmf_font("Euclid Fraktur") + wmf_text(300, 300, b"g")
            + wmf_font("Symbol") + wmf_text(60, 700, b"\xbe\xbe\xbe\xae")
            + wmf_record(0x0000, []))
    return placeable_wmf(body)


def placeable_wmf(body):
    words = (18 + len(body)) // 2
    header = struct.pack("<HHHIHIH", 1, 9, 0x0300, words, 1, 32, 0)
    placeable = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, 0, 0, 2000, 1000, 1440, 0)
    checksum = 0
    for (word,) in struct.iter_unpack("<H", placeable[:20]):
        checksum ^= word
    return placeable + struct.pack("<H", checksum) + header + body


OMML = ('<m:oMath><m:f><m:num><m:r><m:t>x+1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f>'
        '<m:r><m:t>=y</m:t></m:r></m:oMath>')


def ole_run(rid, shape, image_rid):
    return (f'<w:r><w:object w:dxaOrig="2000" w:dyaOrig="1000">'
            f'<v:shape id="_x0000_i{shape}" type="#_x0000_t75" style="width:100pt;height:50pt" o:ole="">'
            f'<v:imagedata r:id="{image_rid}" o:title=""/></v:shape>'
            f'<o:OLEObject Type="Embed" ProgID="Equation.DSMT4" ShapeID="_x0000_i{shape}" DrawAspect="Content" '
            f'ObjectID="_{shape}" r:id="{rid}"/></w:object></w:r>')


def build_docx(path, objects):
    image = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    rels = [f'<Relationship Id="rIdWmf" Type="{image}" Target="media/eq.wmf"/>',
            f'<Relationship Id="rIdEmf" Type="{image}" Target="media/eq.emf"/>',
            f'<Relationship Id="rIdEuclid" Type="{image}" Target="media/euclid.wmf"/>']
    runs = []
    for i in range(objects + 2):
        rels.append(f'<Relationship Id="rIdOle{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/oleObject{i}.bin"/>')
        preview = "rIdWmf" if i < objects else ("rIdEmf" if i == objects else "rIdEuclid")
        runs.append(f'<w:p><w:r><w:t xml:space="preserve">Câu {i + 1}: </w:t></w:r>{ole_run(f"rIdOle{i}", 1025 + i, preview)}</w:p>')
    for size in (24, 28):  # the same OMML equation in a 12 pt and a 14 pt paragraph
        runs.append(f'<w:p><w:pPr><w:rPr><w:sz w:val="{size}"/></w:rPr></w:pPr><w:r><w:rPr><w:sz w:val="{size}"/></w:rPr>'
                    f'<w:t xml:space="preserve">OMML {size // 2} pt: </w:t></w:r>{OMML}</w:p>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" '
                'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                f'<w:body>{"".join(runs)}<w:sectPr/></w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/><Default Extension="wmf" ContentType="image/x-wmf"/><Default Extension="emf" ContentType="image/x-emf"/>'
                   '<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(rels) + "</Relationships>")
        z.writestr("word/document.xml", document)
        z.writestr("word/media/eq.wmf", equation_wmf())
        z.writestr("word/media/eq.emf", equation_emf())
        z.writestr("word/media/euclid.wmf", euclid_arrow_wmf())
        for i in range(objects + 2):
            z.writestr(f"word/embeddings/oleObject{i}.bin", b"HST test object: preview only")


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/stem-equations"))
    parser.add_argument("--objects", type=int, default=60)
    parser.add_argument("--port", type=int, default=20941)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    docx, pdf = os.path.join(out, "equations.docx"), os.path.join(out, "equations.pdf")
    build_docx(docx, args.objects)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, out], check=True)
    os.environ["HST_VCLPLUGIN"] = "svp"
    hst_gui.setup_uno(args.instdir)
    import uno
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, extra_args=["--headless"]).start()
    try:
        doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(docx), "_blank", 0, (prop("Hidden", True),))
        embedded = doc.getEmbeddedObjects()
        objects = embedded.getCount()
        math = sorted((embedded.getByName(n) for n in embedded.getElementNames()
                       if embedded.getByName(n).CLSID.upper() == "078B7ABA-54FC-457F-8551-6147E776A997"),
                      key=lambda o: o.Size.Height)
        omml = [(o.Model.BaseFontHeight, o.Size.Height) for o in math]
        start = time.perf_counter()
        doc.storeToURL(uno.systemPathToFileUrl(pdf), (prop("FilterName", "writer_pdf_Export"),))
        export_s = round(time.perf_counter() - start, 3)
        doc.close(True)
    finally:
        office.stop()
    text = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
    flat = "".join(text.split())  # glyphs are placed one by one (WMF dx array): compare without spaces
    fonts = subprocess.run(["pdffonts", pdf], capture_output=True, text=True).stdout
    families = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout.splitlines()
    no_symbol = "Symbol" not in {f.strip() for line in families for f in line.split(",")}
    urw = "Standard Symbols PS" in subprocess.run(["fc-list"], capture_output=True, text=True).stdout
    images = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True).stdout.splitlines()[2:]
    checks = {
        "objects imported": objects == args.objects + 4,
        "preview text exported as text": flat.count("NaCl+AgNO3") == args.objects,
        "TCVN3 (.VnTime) decoded": flat.count("(rắn)đặc") == args.objects + 1 and "r¾n" not in flat,
        "VNI (VNI-Times) decoded": flat.count("Hòatan") == args.objects + 1 and "Hoøa" not in flat,
        "EMF preview decoded": "CaCO3(rắn)" in flat and flat.count("đặc") == args.objects + 1,
        "Euclid letters": "\u211d" in flat and "\U0001d524" in flat,
        "Symbol arrow with URW Standard Symbols PS (Linux, no Symbol font)":
            not (no_symbol and urw) or "StandardSymbolsPS" in fonts,
        "OMML sized like its text": len(omml) == 2 and omml[1][0] == 14
            and abs(omml[1][1] / omml[0][1] - 14 / 12) < 0.03,
        "no raster previews": len(images) == 0,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    print(f"export: {export_s} s for {objects} objects, {len(images)} images in the PDF")
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"objects": objects, "omml": omml, "export_s": export_s, "pdf_images": len(images), "checks": checks}, handle, indent=2,
                  ensure_ascii=False)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
