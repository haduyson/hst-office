#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render the 1024 px PNG masters of the HST application icons from their SVG masters.

  python3 scripts/brand/render-app-icon-masters.py [--check]

branding/icons/app/<name>.svg is the design source; <name>.png (1024x1024 RGBA) is rendered from
it with rsvg-convert and committed. scripts/generate-brand-assets.py derives every platform size
from the PNG masters with Pillow only, so the CI drift check does not depend on a librsvg version.
Run this after editing an SVG, then run the generator. --check reports masters whose PNG is
missing or differs visibly (max channel delta > 8) from a fresh render.
"""
import argparse
import io
import os
import subprocess
import sys

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brand.common import ROOT, png_bytes  # noqa: E402

MASTER_DIR = os.path.join(ROOT, "branding", "icons", "app")
SIZE = 1024


def render(svg_path):
    png = subprocess.run(["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE), svg_path],
                         check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare committed PNG masters with a fresh render")
    args = parser.parse_args()
    names = sorted(n[:-4] for n in os.listdir(MASTER_DIR) if n.endswith(".svg"))
    stale = []
    for name in names:
        image = render(os.path.join(MASTER_DIR, f"{name}.svg"))
        target = os.path.join(MASTER_DIR, f"{name}.png")
        if args.check:
            if not os.path.isfile(target):
                stale.append(name)
                continue
            with Image.open(target) as current:
                diff = ImageChops.difference(current.convert("RGBA"), image).getextrema()
            if max(high for _low, high in diff) > 8:
                stale.append(name)
            continue
        with open(target, "wb") as handle:
            handle.write(png_bytes(image))
        print(f"wrote {os.path.relpath(target, ROOT)}")
    if stale:
        print("PNG masters out of date:", ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print(f"app icon masters up to date ({len(names)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
