# SPDX-License-Identifier: AGPL-3.0-only
"""Small deterministic OpenDocument packaging primitives (standard library only)."""
import datetime as dt
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

BASE = Path(__file__).resolve().parents[2]
NS = {n: f"urn:oasis:names:tc:opendocument:xmlns:{v}:1.0" for n, v in {
    "office": "office", "style": "style", "text": "text", "table": "table",
    "draw": "drawing", "presentation": "presentation", "meta": "meta",
    "number": "datastyle", "manifest": "manifest", "config": "config",
    "svg": "svg-compatible", "fo": "xsl-fo-compatible", "chart": "chart",
}.items()}
NS.update(dc="http://purl.org/dc/elements/1.1/",
          xlink="http://www.w3.org/1999/xlink",
          of="urn:oasis:names:tc:opendocument:xmlns:of:1.2")
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
EXT = {"writer": "ott", "sheets": "ots", "slides": "otp"}
MIME = {k: "application/vnd.oasis.opendocument." + v + "-template"
        for k, v in {"writer": "text", "sheets": "spreadsheet", "slides": "presentation"}.items()}


def q(name):
    prefix, local = name.split(":", 1)
    return "{" + NS[prefix] + "}" + local


def node(parent, tag, attrs=None, text=None):
    attrs = {q(k): str(v) for k, v in (attrs or {}).items()}
    result = ET.Element(q(tag), attrs) if parent is None else ET.SubElement(parent, q(tag), attrs)
    result.text = text
    return result


def document(kind):
    return node(None, "office:document-" + kind, {"office:version": "1.3"})


def xml(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def epoch():
    value = int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))
    return dt.datetime.fromtimestamp(value, dt.timezone.utc)


def package(path, mime, parts):
    """Store all entries to avoid zlib-version differences and keep mimetype first."""
    manifest = node(None, "manifest:manifest", {"manifest:version": "1.3"})
    entries = {"/": mime, **{n: "text/xml" for n in parts}}
    for name in parts:
        if name.endswith("/content.xml"):
            entries[name.removesuffix("content.xml")] = "application/vnd.oasis.opendocument.chart"
    for name, media in sorted(entries.items()):
        node(manifest, "manifest:file-entry", {
            "manifest:full-path": name, "manifest:media-type": media})
    parts = {**parts, "META-INF/manifest.xml": xml(manifest)}
    stamp = max(dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc), epoch())
    if stamp.year > 2107:
        raise ValueError("SOURCE_DATE_EPOCH exceeds ZIP timestamp range")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name in ["mimetype", *sorted(parts)]:
            info = ZipInfo(name, stamp.timetuple()[:6])
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_STORED
            archive.writestr(info, mime.encode() if name == "mimetype" else parts[name])


def metadata(entry):
    root = document("meta")
    meta = node(root, "office:meta")
    node(meta, "meta:generator", text="HST Office template generator")
    node(meta, "dc:title", text=entry["title"]["vi"])
    node(meta, "dc:description", text=entry["description"]["vi"])
    node(meta, "dc:language", text="vi-VN")
    node(meta, "meta:initial-creator", text="HST Office")
    node(meta, "meta:user-defined", {"meta:name": "License"}, "CC-BY-4.0")
    stamp = epoch().strftime("%Y-%m-%dT%H:%M:%SZ")
    node(meta, "meta:creation-date", text=stamp)
    node(meta, "dc:date", text=stamp)
    return xml(root)


def fonts(root, writer=False):
    decls = node(root, "office:font-face-decls")
    for name in (["Times New Roman"] if writer else []) + ["Liberation Sans", "Arial"]:
        node(decls, "style:font-face", {"style:name": name, "svg:font-family": name})


def style(parent, name, family, properties=None, extra=None):
    result = node(parent, "style:style", {"style:name": name, "style:family": family,
                                         **(extra or {})})
    for kind, attrs in (properties or {}).items():
        node(result, "style:" + kind + "-properties", attrs)
    return result


def paragraph(parent, value="", name=None):
    return node(parent, "text:p", {"text:style-name": name} if name else {}, value)
