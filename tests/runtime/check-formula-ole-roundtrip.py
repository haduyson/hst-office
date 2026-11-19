#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check: a MathType equation kept as an OLE object ("tự chuyển khi mở" off) keeps its ProgID, its class ID
(MathType's 0002CE03-...) and its OLE data byte for byte when the document is saved as .docx, .doc or .rtf, so
MathType can still open it.

Usage:
    python3 tests/runtime/check-formula-ole-roundtrip.py --soffice PATH --docx WORD.docx [--doc WORD.doc]
        [--out DIR] [--port 2106]

WORD.docx / WORD.doc are Word files with MathType 4-7 equations (files are never stored in the repository). The check
also writes .rtf files holding the first equation of WORD.docx as RTF stores OLE objects (\\objdata, OLE 1.0 data),
one of them in a table cell. Each file is opened and saved in every format; every "Equation Native" stream of the
source, with its ProgID and class ID, must be in the saved file, and the saved .rtf must reopen with the objects at
their shown size. (LibreOffice's RTF import reads only the picture of other OLE objects in tables.) "Open with
MathType" needs MathType, which is not installed anywhere.
"""
import argparse
import hashlib
import os
import re
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402
from vba_cfb import Cfb  # noqa: E402

FILTERS = {".docx": "MS Word 2007 XML", ".doc": "MS Word 97", ".rtf": "Rich Text Format"}
MATH_CLSID = "078B7ABA"
PROGID = re.compile(rb"Equation\.(?:DSMT\d|3)")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def streams(cfb, storage):
    """{name: bytes} of the streams directly in one storage of a compound file, and its "CLSID"."""
    found = {name: cfb.read(e) for name, e in cfb.children(storage).items() if e["type"] == 2}
    found["CLSID"] = storage["clsid"]
    return found


def object_streams(path):
    """{name: bytes} for each OLE object (equation or not) in a .docx, .doc or .rtf."""
    data = open(path, "rb").read()
    files = []
    if path.endswith(".docx"):
        archive = zipfile.ZipFile(path)
        files = [archive.read(n) for n in sorted(archive.namelist()) if n.startswith("word/embeddings/")]
    elif path.endswith(".rtf"):
        for match in re.finditer(rb"\\objdata\s*([0-9a-fA-F\s]+)", data):
            raw = bytes.fromhex(re.sub(rb"\s", b"", match.group(1)).decode())
            files.append(raw[raw.find(b"\xd0\xcf\x11\xe0"):] if b"\xd0\xcf\x11\xe0" in raw else b"")
    else:
        cfb = Cfb(data)
        pool = cfb.children(cfb.entries[0]).get("ObjectPool")
        return [streams(cfb, e) for e in cfb.children(pool).values() if e["type"] == 1] if pool else []
    found = []
    for item in files:
        try:
            cfb = Cfb(item)
        except ValueError:
            continue
        found.append(streams(cfb, cfb.entries[0]))
    return found


def equations(path):
    """Sorted [(ProgID, CLSID, sha1 of Equation Native)] of the equations in a file."""
    found = []
    for item in object_streams(path):
        if "Equation Native" in item:
            progid = PROGID.search(item.get("\x01CompObj", b""))
            found.append((progid.group(0).decode() if progid else "", item["CLSID"],
                          hashlib.sha1(item["Equation Native"]).hexdigest()[:12]))
    return sorted(found)


def first_equation(docx):
    """(ProgID, compound file, RTF picture keyword, picture) of the first MathType equation of a .docx."""
    archive = zipfile.ZipFile(docx)
    rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
    body = archive.read("word/document.xml").decode("utf-8")
    target = {}
    for attributes in re.findall(r"<Relationship ([^>]*)/>", rels):
        found = dict(re.findall(r'(\w+)="([^"]*)"', attributes))
        target[found.get("Id")] = found.get("Target")
    for image, ole in re.findall(r'<v:imagedata r:id="([^"]+)".*?<o:OLEObject [^>]*r:id="([^"]+)"', body, re.S):
        data = archive.read("word/" + target[ole])
        progid = PROGID.search(data)
        if progid and progid.group(0).startswith(b"Equation.DSMT"):
            keyword = b"\\emfblip" if target[image].endswith(".emf") else b"\\wmetafile8"
            return progid.group(0), data, keyword, archive.read("word/" + target[image])
    raise SystemExit("no MathType equation in " + docx)


def write_rtf(docx, path, in_table=False):
    """An .rtf holding the first equation of docx as Word writes it: OLE 1.0 data in \\objdata, picture in \\result;
    in_table puts it in a table cell."""
    name, native, keyword, picture = first_equation(docx)
    progid = name + b"\0"
    ole1 = struct.pack("<III", 0x501, 2, len(progid)) + progid + struct.pack("<III", 0, 0, len(native)) + native
    ole1 += struct.pack("<II", 0x501, 0)
    # MathType's baseline: Word lowers the run 3 pt; MathType writes \\dn in \\result, a cell gets it round \\object
    inner, outer = (b"", b"\\dn6 ") if in_table else (b"\\dn6 ", b"")
    result = b"{\\result {%s{\\pict%s\\picwgoal600\\pichgoal300 %s}}}" % (inner, keyword, picture.hex().encode())
    body = b"{\\object\\objemb\\objw600\\objh300{\\*\\objclass %s}{\\*\\objdata %s}%s}" % (
        name, ole1.hex().encode(), result)
    body = b"{\\f0\\fs24 A {" + outer + body + b"} B}"
    # space after the paragraph, as in Word's Normal style
    body = b"\\pard%s\\sa160 " % (b"\\intbl" if in_table else b"") + body
    if in_table:
        body = b"\\trowd\\cellx4000" + body + b"\\cell\\row\\pard "
    with open(path, "wb") as stream:
        stream.write(b"{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Times New Roman;}}" + body + b"\\par}")


def object_sizes(doc):
    """(width, height, top from the baseline, top and bottom margin) in 1/100 mm of the OLE objects of a Writer
    document that are not Math formulas (a formula, such as a converted Equation 3.0, is sized by its own layout when
    it is opened)."""
    objects = [doc.getEmbeddedObjects().getByIndex(i) for i in range(doc.getEmbeddedObjects().getCount())]
    return [(o.Size.Width, o.Size.Height, o.VertOrientPosition if o.VertOrient == 0 else -o.Size.Height,
             o.TopMargin, o.BottomMargin) for o in objects if not o.CLSID.upper().startswith(MATH_CLSID)]


def keeps_sizes(source, reopened):
    """Each object of the reopened file has the size and the place from the baseline (MathType's baseline, Word's
    run position) of an object of the source, to twips rounding."""
    return all(any(max(abs(a - b) for a, b in zip(item, other)) <= 5 for other in source) for item in reopened)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--docx", required=True)
    parser.add_argument("--doc")
    parser.add_argument("--out", default=os.path.join("tests", "output", "formula-ole-roundtrip"))
    parser.add_argument("--port", type=int, default=2106)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    workdir = os.path.abspath(args.out)
    headless_office.import_uno(args.soffice)
    rtf = os.path.join(workdir, "one-equation.rtf")
    write_rtf(args.docx, rtf)
    in_table = os.path.join(workdir, "one-equation-in-table.rtf")
    write_rtf(args.docx, in_table, in_table=True)
    office = headless_office.Office(args.soffice, workdir, args.port)
    try:
        access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess",
            headless_office.props(nodepath="/org.openoffice.Office.Common/Filter/Microsoft/Import"))
        access.setPropertyValue("MathType5ToMath", False)
        access.commitChanges()
        for source in [p for p in (args.docx, args.doc, rtf, in_table) if p]:
            before = equations(source)
            mathtype = [e for e in before if e[0].startswith("Equation.DSMT")]
            doc = office.load(office.url(source))
            sizes = object_sizes(doc)
            if source in (rtf, in_table):  # an RTF object has no wrap distance, whatever the paragraph spacing
                record("%s opens with no margin round the equation" % os.path.basename(source),
                       sizes and all(size[3:] == (0, 0) for size in sizes), sizes)
                record("%s opens with the equation lowered by \\dn6 (3 pt)" % os.path.basename(source),
                       sizes and all(abs(size[2] + size[1] - 105) <= 2 for size in sizes), sizes)
            for extension, filter_name in FILTERS.items():
                saved = os.path.join(workdir, os.path.basename(source) + ".saved" + extension)
                doc.storeToURL(office.url(saved), headless_office.props(FilterName=filter_name))
                after = equations(saved)
                lost = [e for e in mathtype if e not in after]
                record("%s -> %s keeps MathType data" % (os.path.basename(source), extension),
                       mathtype and not lost, {"mathtype": len(mathtype), "lost": len(lost)})
                if extension == ".rtf":  # the RTF import sizes an object by its picture
                    back = office.load(office.url(saved))
                    reopened = object_sizes(back)
                    back.close(True)
                    record("%s -> .rtf reopens every object at its size and baseline" % os.path.basename(source),
                           len(reopened) == len(sizes) and keeps_sizes(sizes, reopened),
                           {"objects": len(sizes), "reopened": len(reopened)})
            doc.close(True)
    finally:
        office.stop()
    failed = [name for name, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
