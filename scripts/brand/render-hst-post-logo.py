#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Reproduce HST POST from the owner-supplied official HASON TECH artwork.

Offline: the same pinned Playwright/Pillow dependencies as render-banners.py.
Committed outlines extract the official mark and H/S/T/O; P reuses O and H strokes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "extensions/hst-vietnamese-tools/banners"
LOGOS = ART / "logos"
WORDMARK = "#322e2e"
SHAPES = json.loads(Path(__file__).with_name("hst-post-shapes.json").read_text())
MARK = f'<g id="company-mark" fill="#0072bb"><path d="{SHAPES["mark"]}"/></g>'
# Source glyphs keep their original 48px cap height and 44px advance (H→S and S→O).
# The original word gap is 24px. Centre the shorter wordmark under the unchanged mark.
LETTERS = (("H", 0), ("S", 44), ("T", 88), ("P", 148), ("O", 192), ("S", 236), ("T", 280))
WORDMARK_X = 68


def lettering():
    paths = ''.join(f'<path data-letter="{char}" transform="translate({x} 0)" '
                    f'd="{SHAPES["glyphs"][char]["path"]}"/>' for char, x in LETTERS)
    return (f'<g id="wordmark" fill="{WORDMARK}" '
            f'transform="translate({WORDMARK_X} 304)">{paths}</g>')


def svg(body, box, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{body}</svg>\n').encode()


def png(image):
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render():
    assert hashlib.sha256((LOGOS / "hasontech.png").read_bytes()).hexdigest() == SHAPES["sourceSha256"], \
        "Company source must be the official file supplied by the owner"
    outputs = {
        LOGOS / "hst-post.svg": svg(MARK + lettering(), "0 0 476 393", "HST POST"),
        LOGOS / "hst-post-icon.svg": svg('<g transform="translate(-68.5 5.5)">' + MARK + '</g>',
                                         "0 0 320 320", "HST Post — HS company mark"),
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for filename, widths, ratio in (("hst-post", (512, 1024), 393 / 476), ("hst-post-icon", (512,), 1)):
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
