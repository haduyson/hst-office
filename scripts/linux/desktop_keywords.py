# SPDX-License-Identifier: AGPL-3.0-only
"""Launcher search keywords without third-party product names (scripts/linux/make-single-deb.py).

Upstream launchers list other vendors' products in Keywords= (e.g. "<vendor> <word processor>") so that a search for
them finds the suite. HST Office names no third-party product in what users see or search: every Keywords /
Keywords[xx] item that names one is dropped; generic words (Text, Spreadsheet, Slides...) and file extensions (doc,
xlsx, vsd...) stay. MimeType= is technical and untouched. The .rpm and AppImage repack the .deb, so they inherit this;
scripts/linux/check-desktop-entries.py rejects any name that slips through.
"""
import pathlib
import re

THIRD_PARTY = re.compile(r"microsoft|\bms[ -]?office\b|excel|power\s*point|visio|outlook|\bpublisher\b|lotus|word\s*pro\b"
                         r"|word\s*perfect|corel|kingsoft|\bwps\b|apple|keynote|google|adobe|acrobat|star\s*office"
                         r"|\bworks\b", re.IGNORECASE)
_KEYWORDS = re.compile(r"^(Keywords(?:\[[^\]]+\])?\s*=)(.*)$")


def clean_text(text):
    """The .desktop text with third-party items removed from every Keywords line (an emptied line is dropped)."""
    out = []
    for line in text.split("\n"):
        match = _KEYWORDS.match(line)
        if match:
            items = [i for i in match.group(2).split(";") if i.strip() and not THIRD_PARTY.search(i)]
            if not items:
                continue
            line = match.group(1) + ";".join(items) + ";"
        out.append(line)
    return "\n".join(out)


def clean_tree(root):
    """Rewrite every regular .desktop file under `root`; returns the number of files changed."""
    changed = 0
    for path in sorted(pathlib.Path(root).rglob("*.desktop")):
        if path.is_symlink() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        cleaned = clean_text(text)
        if cleaned != text:
            path.write_text(cleaned, encoding="utf-8")
            changed += 1
    return changed
