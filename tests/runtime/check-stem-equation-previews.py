# SPDX-License-Identifier: AGPL-3.0-only
"""Equation previews (MathType-style OLE objects) in Word documents: Vietnamese text and PDF export.

Usage: python3 tests/runtime/check-stem-equation-previews.py [--instdir upstream/libreoffice/instdir]
                                                             [--out tests/output/stem-equations] [--objects 60]

Builds a small .docx itself (no downloaded data): N OLE objects with ProgID Equation.DSMT4 whose
WMF previews hold text in Times New Roman, in the TCVN3 font .VnTime and in the VNI font
VNI-Times, as MathType writes them in Vietnamese exam papers. Loads it headless, exports PDF and checks:
  * the PDF text layer holds the decoded Vietnamese words ("rắn", "Hòa tan"): previews are exported
    as vectors and TCVN3/VNI bytes are decoded (before: no text, or "r¾n" / "Hoøa");
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
    words = (18 + len(body)) // 2
    header = struct.pack("<HHHIHIH", 1, 9, 0x0300, words, 1, 32, 0)
    placeable = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, 0, 0, 2000, 1000, 1440, 0)
    checksum = 0
    for (word,) in struct.iter_unpack("<H", placeable[:20]):
        checksum ^= word
    return placeable + struct.pack("<H", checksum) + header + body


def build_docx(path, objects):
    rels = ['<Relationship Id="rIdWmf" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/eq.wmf"/>']
    runs = []
    for i in range(objects):
        rels.append(f'<Relationship Id="rIdOle{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/oleObject{i}.bin"/>')
        runs.append(
            f'<w:p><w:r><w:t xml:space="preserve">Câu {i + 1}: </w:t></w:r><w:r><w:object w:dxaOrig="2000" w:dyaOrig="1000">'
            f'<v:shape id="_x0000_i{1025 + i}" type="#_x0000_t75" style="width:100pt;height:50pt" o:ole="">'
            f'<v:imagedata r:id="rIdWmf" o:title=""/></v:shape>'
            f'<o:OLEObject Type="Embed" ProgID="Equation.DSMT4" ShapeID="_x0000_i{1025 + i}" DrawAspect="Content" ObjectID="_{1000 + i}" r:id="rIdOle{i}"/>'
            f'</w:object></w:r></w:p>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">'
                f'<w:body>{"".join(runs)}<w:sectPr/></w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/><Default Extension="wmf" ContentType="image/x-wmf"/>'
                   '<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(rels) + "</Relationships>")
        z.writestr("word/document.xml", document)
        z.writestr("word/media/eq.wmf", equation_wmf())
        for i in range(objects):
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
        objects = doc.getEmbeddedObjects().getCount()
        start = time.perf_counter()
        doc.storeToURL(uno.systemPathToFileUrl(pdf), (prop("FilterName", "writer_pdf_Export"),))
        export_s = round(time.perf_counter() - start, 3)
        doc.close(True)
    finally:
        office.stop()
    text = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
    flat = "".join(text.split())  # glyphs are placed one by one (WMF dx array): compare without spaces
    images = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True).stdout.splitlines()[2:]
    checks = {
        "objects imported": objects == args.objects,
        "preview text exported as text": flat.count("NaCl+AgNO3") == args.objects,
        "TCVN3 (.VnTime) decoded": flat.count("(rắn)đặc") == args.objects and "r¾n" not in flat,
        "VNI (VNI-Times) decoded": flat.count("Hòatan") == args.objects and "Hoøa" not in flat,
        "no raster previews": len(images) == 0,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    print(f"export: {export_s} s for {objects} objects, {len(images)} images in the PDF")
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"objects": objects, "export_s": export_s, "pdf_images": len(images), "checks": checks}, handle, indent=2,
                  ensure_ascii=False)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
