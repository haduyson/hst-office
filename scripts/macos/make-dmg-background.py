#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render the HST Office dmg window background (Vietnamese text, HST artwork).

Usage: python scripts/macos/make-dmg-background.py [--check]

Writes branding/macos/dmg-background.png (550x442, the size of upstream's
setup_native/source/packinfo/osxdndinstall.png) and dmg-background@2x.png for Retina.
scripts/macos/dmg-settings.py places the app and Applications icons on the marked
positions. Needs fonts-liberation (Liberation Sans covers Vietnamese); rendered text
only, the font file is not redistributed. --check fails when the committed files differ.
"""
import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "branding" / "macos"
LOGO = ROOT / "assets" / "brand" / "hst-office-logo.png"
FONTS = Path("/usr/share/fonts/truetype/liberation")
SIZE = (550, 442)
# Icon centres shared with dmg-settings.py (window coordinates, 1x).
APP_POS, APPLICATIONS_POS = (140, 205), (410, 205)
BLUE, INK, MUTED = (0, 114, 187), (50, 46, 46), (96, 104, 112)
LINES = [("Kéo HST Office vào thư mục Applications", "LiberationSans-Bold.ttf", 17, INK, 318),
         ("để cài đặt, sau đó mở HST Office từ Launchpad.", "LiberationSans-Regular.ttf", 14, MUTED, 344),
         ("HASON TECH", "LiberationSans-Bold.ttf", 11, BLUE, 412)]


def render(scale):
    width, height = SIZE[0] * scale, SIZE[1] * scale
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):  # white to a very light brand tint
        t = y / height
        draw.line([(0, y), (width, y)], fill=tuple(int(255 - (255 - c) * 0.10 * t) for c in BLUE))
    with Image.open(LOGO) as logo:
        logo = logo.convert("RGBA")
        logo_h = 64 * scale
        logo = logo.resize((int(logo.width * logo_h / logo.height), logo_h), Image.LANCZOS)
        image.paste(logo, ((width - logo.width) // 2, 28 * scale), logo)
    # Arrow from the app slot to the Applications slot.
    y = APP_POS[1] * scale
    x0, x1 = (APP_POS[0] + 70) * scale, (APPLICATIONS_POS[0] - 70) * scale
    draw.line([(x0, y), (x1 - 14 * scale, y)], fill=BLUE, width=5 * scale)
    draw.polygon([(x1, y), (x1 - 18 * scale, y - 12 * scale), (x1 - 18 * scale, y + 12 * scale)], fill=BLUE)
    for text, font_name, size, color, top in LINES:
        font = ImageFont.truetype(str(FONTS / font_name), size * scale)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) // 2, top * scale), text, font=font, fill=color)
    return image


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True, dpi=(72 * image.width // SIZE[0],) * 2)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for scale, name in ((1, "dmg-background.png"), (2, "dmg-background@2x.png")):
        data, target = png(render(scale)), OUT / name
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                stale.append(name)
        else:
            target.write_bytes(data)
            print(f"wrote {target.relative_to(ROOT)}")
    if stale:
        print(f"stale dmg background: {', '.join(stale)} (run scripts/macos/make-dmg-background.py)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
