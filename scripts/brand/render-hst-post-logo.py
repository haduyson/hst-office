#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Reproduce the owner's HST Post derivative: traced company mark and outlined bold italic lettering.

Offline: fontTools + the same pinned Playwright/Pillow dependencies as render-banners.py.
The paths trace the 2026 source at its original coordinates; no redesign of the HS mark.
"""
import argparse
import io
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "extensions/hst-vietnamese-tools/banners"
LOGOS = ART / "logos"
BLUE, GREY = "#0072bb", "#58595b"
# Straight-edge trace of the two original blue components. The negative spaces are part of the mark.
MARK = '''<g id="company-mark" fill="#0072bb">
<path d="M230.512 7.618 165.265 119.150 183.945 149.031 279.424 149.031 309.724 207.233 263.895 206.002 248.191 237.382 362.425 237.382 294.434 119.074 203.449 119.074 230.999 72.955 248.153 104.161 286.298 104.161Z"/>
<path d="M94.620 239.382 133.445 239.382 147.965 212.695 207.665 212.695 191.460 239.382 230.580 239.382 274.422 161.618 234.574 161.618 223.365 179.969 167.408 179.969 175.884 164.657 156.140 130.955Z"/>
</g>'''


def lettering():
    font = TTFont(ART / "fonts/exo2/Exo2-ExtraBoldItalic.ttf")
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    paths, x, bounds = [], 0, BoundsPen(glyphs)
    for word, color in (("HST ", BLUE), ("POST", GREY)):
        pen = SVGPathPen(glyphs)
        for char in word:
            glyph = glyphs[cmap[ord(char)]]
            transform = (1, 0, 0, -1, x, 0)
            glyph.draw(TransformPen(pen, transform))
            glyph.draw(TransformPen(bounds, transform))
            x += glyph.width
        paths.append(f'<path fill="{color}" d="{pen.getCommands()}"/>')
    left, top, right, bottom = bounds.bounds
    sx = sy = 54 / (bottom - top)
    left_edge = 228 - (right - left) * sx / 2
    return f'<g transform="translate({left_edge-left*sx:.6f} {269-top*sy:.6f}) scale({sx:.8f} {sy:.8f})">' + ''.join(paths) + '</g>'


def svg(body, box, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{body}</svg>\n').encode()


def png(image):
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render():
    outputs = {
        LOGOS / "hst-post.svg": svg(MARK + lettering(), "0 0 460 336", "HST POST"),
        LOGOS / "hst-post-icon.svg": svg('<g transform="translate(-68.5 36.5)">' + MARK + '</g>',
                                         "0 0 320 320", "HST Post — HS company mark"),
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for filename, widths, ratio in (("hst-post", (512, 1024), 336 / 460), ("hst-post-icon", (512,), 1)):
            data = outputs[LOGOS / (filename + ".svg")].decode()
            for width in widths:
                page = browser.new_page(viewport={"width": width, "height": round(width * ratio)})
                page.set_content('<style>html,body{margin:0}svg{display:block;width:100%;height:100vh}</style>' + data)
                outputs[LOGOS / f"{filename}-{width}.png"] = page.screenshot(omit_background=True)
                page.close()
        browser.close()
    sheet = Image.new("RGB", (1440, 500), "#f2f5f8")
    draw = ImageDraw.Draw(sheet)
    bold = ImageFont.truetype(str(ART / "fonts/BeVietnamPro-Bold.ttf"), 24)
    regular = ImageFont.truetype(str(ART / "fonts/BeVietnamPro-Regular.ttf"), 16)
    draw.text((32, 22), "HST Post · Nhận diện kế thừa HASON TECH", fill="#192d43", font=bold)
    for x, label, im in ((32, "HST POST · Logo", Image.open(io.BytesIO(outputs[LOGOS / "hst-post-1024.png"]))),
                         (504, "Biểu tượng vuông · Dấu HS", Image.open(io.BytesIO(outputs[LOGOS / "hst-post-icon-512.png"]))),
                         (976, "HASON TECH · Logo gốc", Image.open(LOGOS / "hasontech.png"))):
        draw.rounded_rectangle((x, 80, x + 432, 420), radius=12, fill="white")
        im.thumbnail((380, 290), Image.Resampling.LANCZOS)
        sheet.paste(im, (x + (432 - im.width) // 2, 92 + (310 - im.height) // 2), im)
        draw.text((x + 10, 438), label, fill="#25364a", font=regular)
    outputs[ROOT / "docs/design/hst-post-logo-preview.png"] = png(sheet)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = render()
    changed = [p for p, data in outputs.items() if not p.exists() or p.read_bytes() != data]
    if args.check and changed:
        print("Logo regeneration differs:", ", ".join(str(p.relative_to(ROOT)) for p in changed))
        return 1
    if not args.check:
        for path in changed:
            path.write_bytes(outputs[path])
    print(f'{"Checked" if args.check else "Rendered"} {len(outputs)} logo outputs.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
