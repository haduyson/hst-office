# SPDX-License-Identifier: AGPL-3.0-only
"""Contact sheet for the owner gate: the mockup beside real screenshots, stacked, labelled, with a red frame where a
measured item is out of tolerance.

Usage: python3 tests/runtime/ribbon_mockup_contact.py --out SHEET.png --title "Writer Trang đầu 1485" \
           --panel "Hình mẫu=reference/mockup-writer-home-1485.png" --panel "Linux gtk3=linux.png" [--flag 1]
Each --panel is LABEL=PATH; --flag N puts a red frame around the N-th panel (1-based). Panels share one width (the
widest image, or --width) and keep their aspect ratio. Pillow only; no display.
"""
import argparse
import sys

from PIL import Image, ImageDraw, ImageFont

LABEL_H = 26
GAP = 10
RED = (200, 30, 30)
BG = (245, 245, 245)


def _font():
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, 15)
        except OSError:
            continue
    return ImageFont.load_default()


def make_sheet(panels, out, title="", width=None, flags=()):
    """panels: [(label, path)]; flags: 1-based indexes of the panels to frame in red. Returns the output path."""
    images = [(label, Image.open(path).convert("RGB")) for label, path in panels]
    width = width or max(img.width for _label, img in images)
    scaled = []
    for label, img in images:
        if img.width != width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        scaled.append((label, img))
    font = _font()
    top = LABEL_H + 6 if title else 0
    height = top + sum(LABEL_H + img.height + GAP for _label, img in scaled) + GAP
    sheet = Image.new("RGB", (width + 2 * GAP, height), BG)
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((GAP, 4), title, fill=(0, 0, 0), font=font)
    y = top
    for index, (label, img) in enumerate(scaled, start=1):
        draw.text((GAP, y + 4), label, fill=RED if index in flags else (0, 0, 0), font=font)
        y += LABEL_H
        sheet.paste(img, (GAP, y))
        if index in flags:
            draw.rectangle([GAP - 3, y - 3, GAP + img.width + 2, y + img.height + 2], outline=RED, width=3)
        y += img.height + GAP
    sheet.save(out)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--panel", action="append", required=True, help="LABEL=PATH")
    parser.add_argument("--flag", action="append", type=int, default=[], help="1-based panel to frame in red")
    parser.add_argument("--width", type=int)
    args = parser.parse_args()
    panels = []
    for item in args.panel:
        label, _sep, path = item.partition("=")
        if not path:
            parser.error(f"--panel needs LABEL=PATH, got {item!r}")
        panels.append((label, path))
    make_sheet(panels, args.out, args.title, args.width, tuple(args.flag))
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
