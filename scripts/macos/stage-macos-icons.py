#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Replace the LibreOffice macOS app and document icon sets in a source tree with HST icons.

Usage: python -I scripts/macos/stage-macos-icons.py --tree <libreoffice source> [--preview out.png]

sysui/Package_osxicons.mk builds Contents/Resources/main.icns (Dock/Finder icon,
CFBundleIconFile) and generic-*.icns / oasis-*.icns (document icons named in Info.plist)
with iconutil from sysui/desktop/icons/macos/{app-launcher,mime-generic,mime-oasis}/*.iconset.
Those hold PNGs, which a text patch cannot carry, so they are rendered here from the HST
artwork in assets/brand/icons: the app icon as is, document icons as a white page with the
matching HST module icon (Writer, Sheets, Slides; HST Office for the other kinds).
Idempotent; fails if the upstream iconset layout changed.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "assets" / "brand" / "icons"
MACOS = Path("sysui") / "desktop" / "icons" / "macos"
# iconset member -> pixel size (Apple iconset naming).
MEMBERS = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32, "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256, "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512, "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}
# Document kind (iconset name without -template) -> HST icon family.
DOCUMENT_FAMILY = {"text": "hst-writer", "master-document": "hst-writer", "spreadsheet": "hst-sheets",
                   "presentation": "hst-slides", "drawing": "hst-office", "formula": "hst-office",
                   "database": "hst-office", "extension": "hst-office"}


def master(family, size):
    """Smallest HST icon of `family` at least `size` pixels wide (largest one otherwise)."""
    masters = sorted((int(p.stem.rsplit("-", 1)[1]), p) for p in ICONS.glob(f"{family}-[0-9]*.png"))
    if not masters:
        sys.exit(f"no {family} icons in {ICONS}")
    path = next((path for px, path in masters if px >= size), masters[-1][1])
    with Image.open(path) as image:
        return image.convert("RGBA").resize((size, size), Image.LANCZOS)


def document(family, size):
    """White page with a folded corner and the HST module icon, rendered at 4x then reduced."""
    big = size * 4
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    left, right, top, bottom = big * 0.16, big * 0.84, big * 0.06, big * 0.94
    fold = big * 0.18
    page = [(left, top), (right - fold, top), (right, top + fold), (right, bottom), (left, bottom)]
    draw.polygon(page, fill=(255, 255, 255, 255), outline=(176, 184, 192, 255), width=max(4, big // 128))
    draw.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)],
                 fill=(222, 228, 234, 255), outline=(176, 184, 192, 255), width=max(4, big // 128))
    badge = int(big * 0.5)
    canvas.alpha_composite(master(family, badge), (int((left + right - badge) / 2), int(big * 0.36)))
    return canvas.resize((size, size), Image.LANCZOS)


def iconsets(tree):
    """(iconset dir, renderer) for the app icon and every document icon set."""
    yield tree / MACOS / "app-launcher" / "main.iconset", lambda size: master("hst-office", size)
    for kind in ("mime-generic", "mime-oasis"):
        for iconset in sorted((tree / MACOS / kind).glob("*.iconset")):
            name = iconset.name[: -len(".iconset")].removesuffix("-template")
            if name not in DOCUMENT_FAMILY:
                sys.exit(f"unknown document icon set {iconset}")
            yield iconset, lambda size, family=DOCUMENT_FAMILY[name]: document(family, size)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--preview", type=Path, help="also write a contact sheet of the 256px icons")
    args = parser.parse_args()
    if not (args.tree / MACOS / "app-launcher" / "main.iconset").is_dir():
        print(f"missing {args.tree / MACOS / 'app-launcher' / 'main.iconset'}", file=sys.stderr)
        return 1
    previews, count = [], 0
    for iconset, render in iconsets(args.tree):
        for name, size in MEMBERS.items():
            target = iconset / name
            if not target.is_file():
                print(f"unexpected iconset layout, missing {target}", file=sys.stderr)
                return 1
            image = render(size)
            image.save(target, format="PNG")
            count += 1
            if size == 256 and name == "icon_256x256.png":
                previews.append(image)
        print(f"icons {iconset.relative_to(args.tree)}")
    print(f"replaced {count} icon images")
    if args.preview:
        sheet = Image.new("RGBA", (256 * min(len(previews), 9), 256 * ((len(previews) + 8) // 9)), "white")
        for index, image in enumerate(previews):
            sheet.alpha_composite(image, (256 * (index % 9), 256 * (index // 9)))
        sheet.save(args.preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
