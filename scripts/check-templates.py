#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the complete generated catalog, safe archives and reproducible rebuilds."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from templates.catalog import load, validate
from templates.odf import BASE, read_json
from templates.validation import check_archive, require


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(directory, catalog_path):
    catalog, sources = load(catalog_path)
    manifest = read_json(directory / "manifest.json")
    schema = read_json(BASE / "templates/schema.json")
    validate(manifest, schema, schema)
    rules = read_json(BASE / "data/vietnamese/nd30.json")
    require(manifest["nd30Sha256"] == digest(BASE / "data/vietnamese/nd30.json"), "stale ND30 contract")
    require(manifest["numberFormatsSha256"] == digest(BASE / "data/vietnamese/number-formats.json"), "stale format contract")
    require([e["id"] for e in catalog["templates"]] == [e["id"] for e in manifest["templates"]], "manifest IDs differ")
    expected = {e["output"] for e in catalog["templates"]}
    actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.suffix in {".ott", ".ots", ".otp"}}
    require(actual == expected and len(actual) == 18, "expected exactly 18 ODF templates")
    for authored, entry in zip(catalog["templates"], manifest["templates"]):
        require(all(entry[k] == v for k, v in authored.items()), "manifest catalog differs")
        require(entry["sourceSha256"] == digest(catalog_path.parent / entry["source"]), "stale source " + entry["id"])
        require(entry["previewSha256"] == digest(directory / entry["preview"]), "preview hash mismatch")
        result = check_archive(directory / entry["output"], entry, sources[entry["id"]], rules)
        require(entry["outputSha256"] == result, "template hash mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--catalog", type=Path, default=BASE / "templates/catalog.json")
    parser.add_argument("--rebuild-check", action="store_true")
    args = parser.parse_args()
    directory = args.directory or args.path or BASE / "dist/templates"
    manifest = check(directory, args.catalog)
    if args.rebuild_check:
        with tempfile.TemporaryDirectory(prefix="hst-template-rebuild-") as tmp:
            subprocess.run([sys.executable, str(BASE / "scripts/generate-templates.py"), "--out", tmp,
                            "--catalog", str(args.catalog)], check=True,
                           env={**os.environ, "SOURCE_DATE_EPOCH": str(manifest["sourceDateEpoch"])})
            for path in Path(tmp).rglob("*"):
                if path.is_file():
                    require(path.read_bytes() == (directory / path.relative_to(tmp)).read_bytes(), "rebuild mismatch " + str(path))
    print("PASS: 18 ODF templates; structure, Unicode, formulas, links and hashes" +
          ("; byte-identical rebuild" if args.rebuild_check else ""))


if __name__ == "__main__":
    main()
