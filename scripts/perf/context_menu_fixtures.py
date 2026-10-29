# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic, dependency-free fixtures (flat ODF) for context-menu measurements.

Content is synthetic lorem-style text; no private data. `python3 context_menu_fixtures.py
OUTDIR [--manifest FILE]` writes the files and optionally the sha256 manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"')
MIME = {"writer": "text", "calc": "spreadsheet", "impress": "presentation"}
SUFFIX = {"writer": "fodt", "calc": "fods", "impress": "fodp"}
# deliberate misspelling ("teh", "recieve") exercises the Writer spell popup path
SENTENCE = "The quick brown fox jumps over teh lazy dog and will recieve a reward. "


def _head(module: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document {NS} '
            f'office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.{MIME[module]}">\n')


def writer() -> str:
    paras = "".join(f"<text:p>{SENTENCE * 6}</text:p>\n" for _ in range(40))
    return _head("writer") + f"<office:body><office:text>\n{paras}</office:text></office:body></office:document>\n"


def calc() -> str:
    rows = []
    for r in range(1, 41):
        cells = "".join(f'<table:table-cell office:value-type="float" office:value="{r * c}"><text:p>{r * c}</text:p></table:table-cell>'
                        for c in range(1, 9))
        rows.append(f"<table:table-row>{cells}</table:table-row>")
    body = f'<table:table table:name="Sheet1">\n{"".join(rows)}\n</table:table>'
    return _head("calc") + f"<office:body><office:spreadsheet>{body}</office:spreadsheet></office:body></office:document>\n"


def impress() -> str:
    styles = ('<office:automatic-styles><style:page-layout style:name="pm1"><style:page-layout-properties '
              'fo:page-width="28cm" fo:page-height="15.75cm"/></style:page-layout>'
              '<style:style style:name="dp1" style:family="drawing-page"/></office:automatic-styles>'
              '<office:master-styles><style:master-page style:name="Default" style:page-layout-name="pm1"/>'
              '</office:master-styles>')
    # one large text box covering the slide centre, where the harness right-clicks
    shape = ('<draw:frame svg:x="2cm" svg:y="2cm" svg:width="24cm" svg:height="11cm">'
             f'<draw:text-box><text:p>{SENTENCE * 3}</text:p></draw:text-box></draw:frame>')
    page = f'<draw:page draw:name="page1" draw:style-name="dp1" draw:master-page-name="Default">{shape}</draw:page>'
    return _head("impress") + f"{styles}<office:body><office:presentation>{page}</office:presentation></office:body></office:document>\n"


GENERATORS = {"writer": writer, "calc": calc, "impress": impress}


def write_fixtures(outdir: Path) -> dict[str, dict]:
    outdir.mkdir(parents=True, exist_ok=True)
    entries = {}
    for module, gen in GENERATORS.items():
        data = gen().encode("utf-8")
        name = f"context-menu-{module}.{SUFFIX[module]}"
        (outdir / name).write_bytes(data)
        entries[module] = {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return entries


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--manifest", type=Path)
    args = ap.parse_args(argv)
    entries = write_fixtures(args.outdir)
    if args.manifest:
        doc = {"schema": 1, "generator": "scripts/perf/context_menu_fixtures.py",
               "license": "CC BY 4.0 (synthetic text, no private data)", "fixtures": entries}
        args.manifest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(entries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
