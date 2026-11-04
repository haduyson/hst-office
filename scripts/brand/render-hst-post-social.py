#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render standalone HST Post social assets offline; --check compares every output byte for byte.

Requires Pillow==10.4.0 and playwright==1.64.1 with its Chromium, as used by render-banners.py.
"""
import argparse
import base64
import io
import json
from pathlib import Path
from string import Template

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "extensions/hst-vietnamese-tools/banners"
DEST = ROOT / "assets/hst-post"
FONT = ART / "fonts"
TEMPLATE = Path(__file__).with_name("hst-post-social.html")
BRAND = json.loads((ART / "brands.json").read_text())["hst-post"]


def data_url(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def encode(image, fmt="PNG", **options):
    stream = io.BytesIO()
    image.save(stream, format=fmt, optimize=True, **options)
    return stream.getvalue()


def contrast(a, b):
    def luminance(color):
        rgb = [int(color[n:n + 2], 16) / 255 for n in (1, 3, 5)]
        rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * weight for v, weight in zip(rgb, (.2126, .7152, .0722)))
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


def validate(page, height):
    margin_y = 32 if height == 630 else 60
    for element in page.locator(".safe").all():
        box = element.bounding_box()
        assert box and box["x"] >= 60 and box["y"] >= margin_y, box
        assert box["x"] + box["width"] <= 1140, box
        assert box["y"] + box["height"] <= height - margin_y, box
    texts = page.locator("span.safe, text.safe").evaluate_all(r"""nodes => nodes.map(el => {
        const s = getComputedStyle(el);
        const rgb = (el.tagName === 'text' ? s.fill : s.color).match(/\d+/g);
        return {color: '#' + rgb.slice(0, 3).map(v => (+v).toString(16).padStart(2, '0')).join(''),
                background: el.dataset.background || '#ffffff', family: s.fontFamily};
    })""")
    for item in texts:
        assert "BeVietnam" in item["family"], item
        assert contrast(item["color"], item["background"]) >= 4.5, item
    # The outlined wordmark also meets the requested text contrast on white.
    for color in ("#322e2e", BRAND["accent"]):
        assert contrast(color, "#ffffff") >= 4.5
    for weight in (400, 600, 700):
        assert page.evaluate("w => document.fonts.check(w + ' 23px BeVietnam', 'Đăng bài Sắp ra mắt')", weight)
    assert page.evaluate("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")


def preview(og):
    """Draw schematic feed and chat cards; no platform logos or UI screenshots."""
    sheet = Image.new("RGB", (1440, 810), "#eef2f6")
    draw = ImageDraw.Draw(sheet)
    def text(x, y, content, size=20, weight="Regular", color="#25364a"):
        font = ImageFont.truetype(str(FONT / f"BeVietnamPro-{weight}.ttf"), size)
        draw.text((x, y), content, fill=color, font=font)
    text(56, 34, "HST Post · Xem trước khi chia sẻ", 30, "Bold")
    text(56, 83, "Khung minh hoạ tự vẽ · Cách hiển thị thực tế có thể khác theo ứng dụng", 19)
    text(56, 144, "Facebook · Thẻ liên kết trong bảng tin", 21, "SemiBold")
    text(752, 144, "Zalo · Thẻ liên kết trong hội thoại", 21, "SemiBold")
    thumb = og.resize((632, 332), Image.Resampling.LANCZOS)
    draw.rounded_rectangle((56, 193, 688, 707), 18, fill="white", outline="#c4d0dc", width=1)
    draw.ellipse((76, 213, 108, 245), fill=BRAND["accent"])
    text(120, 215, "HASON TECH", 18, "SemiBold")
    sheet.paste(thumb, (56, 266))
    draw.rectangle((57, 598, 687, 686), fill="#f5f7f9")
    text(76, 611, "POST.HASONTECH.VN", 13, color="#526071")
    text(76, 637, "HST Post — Đăng bài đa nền tảng bằng AI", 21, "SemiBold")
    text(76, 672, "Sắp ra mắt · Công cụ của HASON TECH", 15)
    draw.rounded_rectangle((734, 193, 1400, 733), 24, fill=BRAND["tint"])
    draw.rounded_rectangle((752, 215, 1384, 709), 16, fill="white", outline="#c4d0dc", width=1)
    text(772, 231, "https://post.hasontech.vn", 20, color=BRAND["ink"])
    sheet.paste(thumb, (752, 279))
    text(772, 625, "HST Post — Đăng bài đa nền tảng bằng AI", 21, "SemiBold")
    text(772, 662, "Sắp ra mắt · post.hasontech.vn", 17)
    text(56, 761, "Ảnh ngang 1200 × 630 · Các biểu tượng trong ảnh là hình vẽ khái quát, không đại diện thương hiệu.", 17)
    return encode(sheet)


def render():
    outputs, images = {}, {}
    values = {name: data_url(FONT / f"BeVietnamPro-{weight}.ttf", "font/ttf")
              for name, weight in (("regular", "Regular"), ("semibold", "SemiBold"), ("bold", "Bold"))}
    values.update(BRAND)
    values["logo"] = data_url(ART / "logos/hst-post.svg", "image/svg+xml")
    icon = (ART / "logos/hst-post-icon.svg").read_text(encoding="utf-8")
    # Opaque violet tint carries the product palette while preserving the official blue mark.
    icon = icon.replace("</title>", f'</title><rect width="320" height="320" fill="{BRAND["tint"]}"/>', 1)
    outputs[DEST / "favicon.svg"] = icon.encode("utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, height, scale in (("og-hst-post", 630, 1), ("og-hst-post@2x", 630, 2),
                                    ("og-hst-post-square", 1200, 1)):
            # Render at twice the output density for smooth diagonals and Vietnamese accents.
            page = browser.new_page(viewport={"width": 1200, "height": height}, device_scale_factor=scale * 2)
            page.route("**/*", lambda route: route.abort())
            page.set_content(Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
                values, layout="square" if height == 1200 else "landscape"))
            page.evaluate("document.fonts.ready")
            validate(page, height)
            im = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            im = im.resize((1200 * scale, height * scale), Image.Resampling.LANCZOS)
            images[name] = im
            outputs[DEST / f"{name}.png"] = encode(im)
            page.close()
        for name, size in (("favicon-32", 32), ("apple-touch-icon", 180), ("icon-512", 512)):
            page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=4)
            page.route("**/*", lambda route: route.abort())
            page.set_content('<style>html,body{margin:0}svg{display:block;width:100%;height:100vh}</style>' + icon)
            im = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            outputs[DEST / f"{name}.png"] = encode(im.resize((size, size), Image.Resampling.LANCZOS))
            page.close()
        browser.close()
    jpg = encode(images["og-hst-post"], "JPEG", quality=90, subsampling=0, progressive=True)
    assert len(jpg) < 300_000, f"JPEG exceeds 300 KB: {len(jpg)} bytes"
    outputs[DEST / "og-hst-post.jpg"] = jpg
    outputs[ROOT / "docs/design/hst-post-social-preview.png"] = preview(images["og-hst-post"])
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without changing files")
    args = parser.parse_args()
    outputs = render()
    changed = [path for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
    if args.check and changed:
        print("Regeneration differs:", ", ".join(str(p.relative_to(ROOT)) for p in changed))
        return 1
    if not args.check:
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[path])
    print(f'{"Checked" if args.check else "Rendered"} {len(outputs)} outputs; safe areas and contrast ≥4.5:1 verified.')
    print(f'JPEG: {len(outputs[DEST / "og-hst-post.jpg"]):,} bytes (<300,000).')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
