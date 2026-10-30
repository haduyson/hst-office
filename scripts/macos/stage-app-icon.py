#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Replace the LibreOffice app icon set in a source tree with the HST Office icon.

Usage: python -I scripts/macos/stage-app-icon.py --tree <libreoffice source>

sysui/Package_osxicons.mk builds Contents/Resources/main.icns (the Dock/Finder icon,
CFBundleIconFile) with iconutil from sysui/desktop/icons/macos/app-launcher/main.iconset.
That directory holds PNGs, which a text patch cannot carry, so the HST icons from
assets/brand/icons are resized into it here. Idempotent; fails if the iconset is missing.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "assets" / "brand" / "icons"
# iconset member -> pixel size (Apple iconset naming).
MEMBERS = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32, "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256, "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512, "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}


def source_for(size):
    """Smallest HST master icon at least `size` pixels wide (largest one otherwise)."""
    masters = sorted((int(p.stem.rsplit("-", 1)[1]), p) for p in ICONS.glob("hst-office-[0-9]*.png"))
    if not masters:
        sys.exit(f"no HST icons in {ICONS}")
    return next((path for px, path in masters if px >= size), masters[-1][1])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", type=Path, required=True)
    args = parser.parse_args()
    iconset = args.tree / "sysui" / "desktop" / "icons" / "macos" / "app-launcher" / "main.iconset"
    if not iconset.is_dir():
        print(f"missing {iconset}", file=sys.stderr)
        return 1
    for name, size in MEMBERS.items():
        target = iconset / name
        if not target.is_file():
            print(f"unexpected iconset layout, missing {target}", file=sys.stderr)
            return 1
        with Image.open(source_for(size)) as image:
            image.convert("RGBA").resize((size, size), Image.LANCZOS).save(target, format="PNG")
        print(f"icon {name} {size}px <- {source_for(size).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
