#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render the offline 360×104 banners, manifest, review sheet and Writer placement from local assets only.

Build dependencies: playwright==1.64.1 (its Chromium), Pillow (requirements-templates.lock).
Run: .venv/bin/python scripts/brand/render-banners.py
No network, key access or generated logos. --check verifies byte-for-byte regeneration without modifying outputs.
"""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
from string import Template
import sys

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "extensions/hst-vietnamese-tools/banners"
DESIGN = ROOT / "docs/design"
FONT = ART / "fonts"
GENERATED_AT = "2026-11-04T00:00:00Z"


def luminance(color):
    values = [int(color[n:n + 2], 16) / 255 for n in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


def markup(solution, brand):
    values = {key: html.escape(solution[key], quote=True) for key in ("name", "tagline")}
    for color in (brand["ink"], "#25364a", "#526071"):
        assert min(contrast(color, bg) for bg in ("#ffffff", brand["tint"])) >= 4.5
    values.update(brand)
    values.update(font_regular=(FONT / "BeVietnamPro-Regular.ttf").as_uri(),
                  font_semibold=(FONT / "BeVietnamPro-SemiBold.ttf").as_uri(),
                  font_bold=(FONT / "BeVietnamPro-Bold.ttf").as_uri(), logo_width=brand["logoWidth"],
                  border="#" + "".join(f'{round(int(brand["accent"][n:n+2], 16)*.18+255*.82):02x}' for n in (1, 3, 5)))
    values["logo_html"] = ('<img class="logo" alt="" src="%s">' % (ART / "logos" / brand["logo"]).as_uri()
                           if brand["logo"] else "")
    return Template((ART / "template.html").read_text()).substitute(values)


def png_bytes(image):
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def preview(outputs, solutions):
    sheet = Image.new("RGB", (1200, 1592), "#f2f5f8")
    draw = ImageDraw.Draw(sheet)
    bold = ImageFont.truetype(str(FONT / "BeVietnamPro-Bold.ttf"), 24)
    regular = ImageFont.truetype(str(FONT / "BeVietnamPro-Regular.ttf"), 14)
    draw.text((32, 22), "HASON TECH · Banner giải pháp", font=bold, fill="#192d43")
    draw.text((32, 60), "360 × 104 px · Nội dung chuẩn từ solutions.json · Chu kỳ 10 giây", font=regular, fill="#526071")
    draw.text((32, 94), "1× · Kích thước trên ribbon", font=regular, fill="#526071")
    draw.text((440, 94), "2× · Xuất ảnh cho màn hình mật độ cao", font=regular, fill="#526071")
    for n, solution in enumerate(solutions):
        y = 130 + n * 240
        for scale, x in ((1, 32), (2, 440)):
            im = Image.open(io.BytesIO(outputs[ART / f'{solution["id"]}@{scale}x.png']))
            sheet.paste(im, (x, y), im)
    return png_bytes(sheet)


def render():
    solutions = json.loads((ROOT / "data/hst/solutions.json").read_text())["solutions"]
    brands = json.loads((ART / "brands.json").read_text())
    outputs, items = {}, []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--allow-file-access-from-files"])
        for solution in solutions:
            item = {k: solution[k] for k in ("id", "name", "tagline", "url")}
            item.update(order=len(items), image={})
            # Temporary HTML beside the template makes file:// fonts work without a web server.
            page_path = ART / ".render.html"
            try:
                page_path.write_text(markup(solution, brands[solution["id"]]), encoding="utf-8")
                for scale in (1, 2, 3):
                    page = browser.new_page(viewport={"width": 360, "height": 104}, device_scale_factor=scale)
                    page.route("http://**/*", lambda route: route.abort())
                    page.route("https://**/*", lambda route: route.abort())
                    page.goto(page_path.as_uri())
                    page.evaluate("document.fonts.ready")
                    assert page.evaluate("document.fonts.check('12.5px BeVietnam')")
                    assert page.evaluate("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
                    bounds = page.locator("p").bounding_box()
                    assert bounds["height"] <= 34 and bounds["y"] + bounds["height"] <= 76, solution["id"]
                    blob = page.screenshot(omit_background=True)
                    name = f'{solution["id"]}@{scale}x.png'
                    outputs[ART / name] = blob
                    assert len(blob) <= 300 * 1024
                    item["image"][f"{scale}x"] = {"url": "banners/" + name,
                                                  "sha256": hashlib.sha256(blob).hexdigest(), "size": len(blob)}
                    page.close()
            finally:
                page_path.unlink(missing_ok=True)
            items.append(item)
        browser.close()
    doc = {"schemaVersion": 1, "generatedAt": GENERATED_AT, "rotateSeconds": 10, "items": items}
    outputs[ROOT / "data/hst/banners.json"] = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    online = json.loads(json.dumps(doc))
    for item in online["items"]:
        for spec in item["image"].values():
            spec["url"] = "https://system.hasontech.vn/hst-office/" + spec["url"]
    outputs[ROOT / "assets/banners/banners-online.example.json"] = (json.dumps(online, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    outputs[DESIGN / "banners-preview.png"] = preview(outputs, solutions)
    # Placement mockup on the supplied REAL Writer screenshot; no claim that the native widget exists yet.
    writer = Image.open(ROOT / "website/office.hasontech.vn/assets/img/office-writer-1485.jpg").convert("RGB")
    # Reserve the right-hand slot; show one complete style tile and the existing overflow affordance.
    source = writer.copy()
    ImageDraw.Draw(writer).rectangle((899, 44, 1475, 154), fill="white")
    writer.paste(source.crop((905, 54, 1012, 115)), (905, 54))
    writer.paste(source.crop((1304, 88, 1327, 116)), (1071, 80))
    writer.paste(source.crop((1173, 134, 1244, 154)), (967, 134))
    banner = Image.open(io.BytesIO(outputs[ART / "aios@1x.png"]))
    writer.paste(banner, (1108, 48), banner)
    outputs[DESIGN / "banner-on-writer.png"] = png_bytes(writer)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = render()
    changed = []
    for path, data in outputs.items():
        if not path.exists() or path.read_bytes() != data:
            changed.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    if args.check and changed:
        print("Regeneration differs: " + ", ".join(changed))
        return 1
    print(f'{"Checked" if args.check else "Rendered"} {len(outputs)} outputs; contrast ≥4.5, taglines ≥12px, no clipping.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
