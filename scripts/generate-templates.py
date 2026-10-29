#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate all HST ODF templates directly; no office runtime or third-party libraries."""
import argparse
import hashlib
from pathlib import Path
from xml.sax.saxutils import escape
from templates import catalog, sheets, slides, writer
from templates.odf import BASE, MIME, epoch, json_bytes, metadata, package, read_json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preview(entry, source):
    """A deterministic catalog card, explicitly not a rendered document preview."""
    title = escape(entry["title"]["vi"])
    color = source.get("theme", {}).get("accent", "#16324f")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="280" viewBox="0 0 480 280">'
            f'<title>{title} — thẻ danh mục</title><rect width="480" height="280" fill="#f4f7fa"/>'
            f'<rect width="480" height="12" fill="{color}"/>'
            f'<g font-family="Liberation Sans, Arial, sans-serif" fill="{color}">'
            f'<text x="24" y="65" font-size="18">HST {entry["module"].capitalize()}</text>'
            f'<text x="24" y="130" font-size="28">{title}</text>'
            '<text x="24" y="185" font-size="16">[Nội dung có thể chỉnh sửa]</text>'
            '<text x="24" y="246" font-size="13">Thẻ danh mục · không phải bản kết xuất</text>'
            '</g></svg>\n').encode()


def generate(out, catalog_path):
    data, sources = catalog.load(catalog_path)
    rules_path = BASE / "data/vietnamese/nd30.json"
    formats_path = BASE / "data/vietnamese/number-formats.json"
    rules, formats = read_json(rules_path), read_json(formats_path)
    out = Path(out)
    manifest = {**data, "sourceDateEpoch": int(epoch().timestamp()),
                "generator": "HST Office template generator", "nd30Sha256": sha(rules_path),
                "numberFormatsSha256": sha(formats_path), "templates": []}
    for entry in data["templates"]:
        source = sources[entry["id"]]
        module = entry["module"]
        if module == "writer":
            parts = writer.build(source, rules)
        elif module == "sheets":
            parts = sheets.build(source, formats)
        else:
            parts = slides.build(source)
        parts["meta.xml"] = metadata(entry)
        target = out / entry["output"]
        package(target, MIME[module], parts)
        card = out / entry["preview"]
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_bytes(preview(entry, source))
        manifest["templates"].append({**entry, "sourceSha256": sha(Path(catalog_path).parent / entry["source"]),
                                      "outputSha256": sha(target), "previewSha256": sha(card)})
    (out / "manifest.json").write_bytes(json_bytes(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", "--output", type=Path, default=BASE / "dist/templates")
    parser.add_argument("--catalog", type=Path, default=BASE / "templates/catalog.json")
    args = parser.parse_args()
    manifest = generate(args.out, args.catalog)
    print(f'Generated {len(manifest["templates"])} templates in {args.out}')


if __name__ == "__main__":
    main()
