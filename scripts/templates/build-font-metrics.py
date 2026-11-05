#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Write data/vietnamese/font-metrics-times.json: glyph advances that lay out rule lengths without an office runtime.

Liberation Serif is metric-compatible with Times New Roman for this repertoire (same advance widths by design); the
Times New Roman font itself is not redistributable and is not needed to read its widths this way. Developer tool: needs
fontTools and the Liberation fonts, and its output is committed. The generator and the wizard only read the JSON.
"""
import argparse
import json
from pathlib import Path
import unicodedata

from fontTools.ttLib import TTFont

FONT_DIR = "/usr/share/fonts/truetype/liberation"
STYLES = {"regular": "Regular", "bold": "Bold", "italic": "Italic", "boldItalic": "BoldItalic"}
BASES = "aăâeêioôơuưyAĂÂEÊIOÔƠUƯY"
TONES = "̣̀́̃̉"


def repertoire():
    chars = {chr(c) for c in range(0x20, 0x7F)} | set("đĐ–—…“”‘’•*")
    for base in BASES:
        chars.add(base)
        chars.update(unicodedata.normalize("NFC", base + tone) for tone in TONES)
    return sorted(chars)


def advances(path, chars):
    font = TTFont(path)
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    return font["head"].unitsPerEm, {c: hmtx[cmap[ord(c)]][0] for c in chars}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    chars = repertoire()
    result = {"source": "Liberation Serif, metric-compatible with Times New Roman", "unitsPerEm": 0}
    lines = []
    for key, style in STYLES.items():
        units, table = advances(f"{FONT_DIR}/LiberationSerif-{style}.ttf", chars)
        result["unitsPerEm"] = units
        lines.append(f' "{key}": ' + json.dumps(table, ensure_ascii=False, sort_keys=True))
    head = json.dumps({k: result[k] for k in ("source", "unitsPerEm")}, ensure_ascii=False)[:-1]
    args.out.write_text(head + ",\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
