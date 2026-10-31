# SPDX-License-Identifier: AGPL-3.0-only
"""Add the old-style tone placement of open oa/oe/uy syllables to the bundled Hunspell vi_VN.dic.

Usage: python3 scripts/dict/generate-vi-tone-variants.py [--apply|--check] [--tree upstream/libreoffice]

The upstream dictionary spells open syllables ending in oa, oe or uy with the tone mark on the
second vowel (hoá, khoẻ, thuỷ, tuỳ). Vietnamese writers equally use the mark on the first vowel
(hóa, khỏe, thủy, tùy), which the dictionary rejects. For every upstream entry of that shape the
other placement is added; nothing else is added, so no non-words appear. "qu" is an initial, not
a vowel: quý, quỳ, ... have a single placement and are skipped (quí/quý is a spelling choice, not
a tone placement, and is left alone). Idempotent; --check only reports.
"""
import argparse
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TONES = {"̀", "̉", "̃", "́", "̣"}  # grave, hook, tilde, acute, dot below
PAIRS = {("o", "a"), ("o", "e"), ("u", "y")}


def split_tone(char):
    """(letter without tone mark, tone mark or "") for one NFC character."""
    decomposed = unicodedata.normalize("NFD", char)
    tone = "".join(c for c in decomposed if c in TONES)
    rest = "".join(c for c in decomposed if c not in TONES)
    return unicodedata.normalize("NFC", rest), tone


def other_placement(word):
    """The word with the tone mark moved to the other vowel of a final oa/oe/uy, or None."""
    if len(word) < 2 or word != unicodedata.normalize("NFC", word):
        return None
    first, second = split_tone(word[-2]), split_tone(word[-1])
    if (first[0].lower(), second[0].lower()) not in PAIRS or bool(first[1]) == bool(second[1]):
        return None
    if first[0].lower() == "u" and len(word) > 2 and word[-3].lower() == "q":
        return None  # qu + y: the u belongs to the initial
    if bool(first[1]) is False:
        moved = (first[0] + second[1], second[0])  # tone from the 2nd vowel to the 1st
    else:
        moved = (first[0], second[0] + first[1])  # old style given: produce the new style
    return unicodedata.normalize("NFC", word[:-2] + moved[0] + moved[1])


def merge(lines):
    """(new line list, added words) for the .dic lines (first line is the entry count)."""
    entries = [line for line in lines[1:] if line]
    have = set(entries)
    added = []
    for entry in entries:
        variant = other_placement(entry)
        if variant and variant not in have:
            have.add(variant)
            added.append(variant)
    return [str(len(entries) + len(added))] + entries + sorted(added), added


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", default=os.path.join(ROOT, "upstream", "libreoffice"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="rewrite vi_VN.dic in the tree")
    mode.add_argument("--check", action="store_true", help="exit 1 when variants are missing")
    args = parser.parse_args()
    path = os.path.join(args.tree, "dictionaries", "vi", "vi_VN.dic")
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    trailing = lines[-1] == ""
    if trailing:
        lines.pop()
    if not lines[0].strip().isdigit():
        sys.exit(f"{path}: first line is not the entry count")
    merged, added = merge(lines)
    print(f"{path}: {len(lines) - 1} entries, {len(added)} old-style variants {'to add' if added else 'missing'}")
    if args.apply and added:
        # Replace the file instead of rewriting it: copies hard-linked to the old file stay untouched.
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8", newline="") as handle:
            handle.write(newline.join(merged) + (newline if trailing else ""))
        os.replace(temp, path)
    return 1 if args.check and added else 0


if __name__ == "__main__":
    sys.exit(main())
