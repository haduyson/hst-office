#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Reject new LibreOffice PO edits and exclude retired hunks from the active series."""
import argparse
import hashlib
from pathlib import Path
import re

from po_io import parse_po

ROOT = Path(__file__).resolve().parents[2]
FILES = re.compile(rb"^--- ([^\s]+)[^\n]*\n\+\+\+ ([^\s]+)[^\n]*\n", re.MULTILINE)


def active_patch(data):
    files = list(FILES.finditer(data))
    if not files:
        raise ValueError("missing unified diff")
    code, retired = [], []
    for index, match in enumerate(files):
        # Use traditional diff headers, as consumed by scripts/apply-patches.sh.
        end = files[index + 1].start() if index + 1 < len(files) else len(data)
        section = data[match.start():end]
        metadata = re.search(rb"^(?:diff --git |Index: )", section, re.MULTILINE)
        if metadata:
            section = section[:metadata.start()]
        if any(p.removeprefix(b"a/").removeprefix(b"b/").startswith(b"translations/source/")
               for p in match.groups()):
            retired.append(section)
        else:
            code.append(section)
    return b"".join(code), b"".join(retired)


def check_series(directory, output=None):
    archive = dict(line.split() for line in
                   (ROOT / "l10n/hst/retired-patch-hunks.sha256").read_text().splitlines())
    for name in (directory / "series").read_text().splitlines():
        if not name or name.startswith("#"):
            continue
        content = (directory / name).read_bytes()
        active, retired = active_patch(content)
        if retired and archive.get(name) != hashlib.sha256(retired).hexdigest():
            raise ValueError(f"{name}: write translations to l10n/hst, upstream PO hunk detected")
        if output and active:
            (output / name).write_bytes(active if retired else content)


def check_catalogs():
    root = ROOT / "l10n/hst"
    templates = {p.relative_to(root / "templates").with_suffix(".po")
                 for p in (root / "templates").rglob("*.pot")}
    if not templates:
        raise ValueError("HST templates are missing")
    for lang in ("vi", "en-US"):
        paths = {p.relative_to(root / lang) for p in (root / lang).rglob("*.po")}
        if paths != templates:
            raise ValueError(f"{lang}: HST catalog file list differs from templates")
        for rel in paths:
            template = (root / "templates" / rel).with_suffix(".pot")
            def keys(path):
                return [(e["msgctxt"], e["msgid"], e["msgid_plural"])
                        for e in parse_po(path) if e["msgid"]]
            source, translated = keys(template), keys(root / lang / rel)
            if sorted(source) != sorted(translated) or len(set(source)) != len(source):
                raise ValueError(f"{lang}/{rel}: missing, duplicate or extra HST key")
            for entry in parse_po(root / lang / rel):
                if entry["msgid"] and (not entry["msgstr"] or entry["fuzzy"]):
                    raise ValueError(f"{lang}/{rel}: missing translation of {entry['msgctxt']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-dir", type=Path, default=ROOT / "patches/libreoffice")
    parser.add_argument("--emit", type=Path, help="emit active patches into an empty scratch directory")
    args = parser.parse_args()
    try:
        check_series(args.patch_dir, args.emit)
        if args.emit is None:
            check_catalogs()
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
