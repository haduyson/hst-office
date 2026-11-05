#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Presentation backgrounds of the source tree (extras/source/templates/presnt): Vietnamese placeholder text, no upstream name.

Usage: apply-presnt-vi.py --tree upstream/libreoffice [--check]
Replaces the Lorem Ipsum text (only Freshes holds it as text; the others held it in their thumbnail), drops descriptions and
generator strings and an SVG export path that name the upstream project and copies the thumbnails of
assets/templates/presnt-thumbnails. Layouts, slides and masters stay as they are; a removed description's licence is kept as the property "License". Idempotent, runs in
the build steps next to apply-icon-overrides.py. --check only verifies, exit 1 when something is left.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THUMBNAILS = ROOT / "assets/templates/presnt-thumbnails"
PRESNT = "extras/source/templates/presnt"
TEXT = (("Lorem Ipsum Dolor", "Hạng mục"), (">Sit<", ">Chỉ tiêu<"))
LATIN = re.compile(r"lorem|ipsum|dolor sit|consectetur", re.I)
UPSTREAM = re.compile(r"LibreOffice|Impress Template|Document Foundation", re.I)
DESCRIPTION = re.compile(r"\s*<dc:description>(.*?)</dc:description>", re.S)
SVG_EXPORT_PATH = re.compile(r'\s*inkscape:export-filename="[^"]*"')
GENERATOR = re.compile(r"\s*<meta:generator>.*?</meta:generator>", re.S)
LICENCE = re.compile(r"(?:Creative Commons Attribution-ShareAlike|CC by SA) (\d\.\d)", re.I)


def clean_meta(text):
    """Metadata without the upstream name; the licence named by a removed description stays as a property."""
    match = DESCRIPTION.search(text)
    if match and UPSTREAM.search(match.group(1)):
        licence = LICENCE.search(match.group(1))
        property_ = ""
        if licence:
            property_ = '\n    <meta:user-defined meta:name="License">CC-BY-SA-%s</meta:user-defined>' % licence.group(1)
        text = text[:match.start()] + property_ + text[match.end():]
    return GENERATOR.sub("", text)


def clean_content(text):
    for old, new in TEXT:
        text = text.replace(old, new)
    return text


def problems(directory):
    found = []
    for svg in directory.glob("Pictures/*.svg"):
        if UPSTREAM.search(svg.read_text(encoding="utf-8")):
            found.append(f"{directory.name}/{svg.name}: upstream name")
    for name in ("content.xml", "styles.xml"):
        if LATIN.search((directory / name).read_text(encoding="utf-8")):
            found.append(f"{directory.name}/{name}: Latin placeholder text")
    if UPSTREAM.search((directory / "meta.xml").read_text(encoding="utf-8")):
        found.append(f"{directory.name}/meta.xml: upstream name")
    thumbnail = directory / "Thumbnails/thumbnail.png"
    source = THUMBNAILS / (directory.name + ".png")
    if not source.is_file() or thumbnail.read_bytes() != source.read_bytes():
        found.append(f"{directory.name}: thumbnail is not HST's")
    return found


def apply(directory):
    for name, clean in (("content.xml", clean_content), ("meta.xml", clean_meta)):
        path = directory / name
        before = path.read_text(encoding="utf-8")
        after = clean(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
    for svg in directory.glob("Pictures/*.svg"):  # a designer's export path names the upstream source tree
        before = svg.read_text(encoding="utf-8")
        after = SVG_EXPORT_PATH.sub("", before)
        if after != before:
            svg.write_text(after, encoding="utf-8")
    shutil.copyfile(THUMBNAILS / (directory.name + ".png"), directory / "Thumbnails/thumbnail.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directories = sorted(p for p in (args.tree / PRESNT).iterdir() if p.is_dir())
    if len(directories) != 23:
        print(f"expected 23 presentation backgrounds, found {len(directories)}", file=sys.stderr)
        return 1
    if not args.check:
        for directory in directories:
            apply(directory)
    left = [item for directory in directories for item in problems(directory)]
    print("\n".join(left) or f"presentation backgrounds: {len(directories)} clean")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
