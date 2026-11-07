#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Render the offline 360×104 banners, their 160×104 compact art (windows under 1280 px), manifest, review sheet
and Writer placement from local assets only.

Build dependencies: playwright==1.64.1 (its Chromium), Pillow (requirements-templates.lock).
Run: .venv/bin/python scripts/brand/render-banners.py
No network or key access; the HST Post derivative is built by render-hst-post-logo.py. --check verifies byte-for-byte regeneration without modifying outputs.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brand.banner_preview import ART, FONT, ROOT, png_bytes, preview  # noqa: E402

DESIGN = ROOT / "docs/design"
GENERATED_AT = "2026-11-07T12:45:00Z"


def luminance(color):
    values = [int(color[n:n + 2], 16) / 255 for n in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


COMPACT = (160, 104)
# Be Vietnam Pro has no U+2192; a system fallback font rasterises it differently from run to run, so the
# arrow is drawn in the text colour instead.
ARROW = ('<svg class="arrow" viewBox="0 0 12 8" aria-hidden="true"><path d="M0.5 4H10.5M7.5 1L10.5 4L7.5 7" '
         'fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def markup(solution, brand, template="template.html"):
    values = dict(text="#25364a", muted="#526071")
    company = solution["id"] == "hasontech"
    for color in (brand["ink"], brand["text"] if company else "#25364a", brand["muted"] if company else "#526071"):
        assert min(contrast(color, bg) for bg in ("#ffffff", brand["tint"])) >= 4.5
    values.update(brand)
    values.update({key: html.escape(solution[key], quote=True) for key in ("name", "tagline")})
    values.update(card_class="company" if company else "", owner="hasontech.vn" if company else "HASON TECH",
                  cta=html.escape(brand.get("cta", "Tìm hiểu thêm →")).replace("→", ARROW),
                  detail_html=('<br><span class="ecosystem">' + html.escape(brand["detail"]) + '</span>') if company else "")
    values.update(font_regular=(FONT / "BeVietnamPro-Regular.ttf").as_uri(),
                  font_semibold=(FONT / "BeVietnamPro-SemiBold.ttf").as_uri(),
                  font_bold=(FONT / "BeVietnamPro-Bold.ttf").as_uri(), logo_width=brand["logoWidth"],
                  border="#" + "".join(f'{round(int(brand["accent"][n:n+2], 16)*.18+255*.82):02x}' for n in (1, 3, 5)))
    values["logo_html"] = ('<img class="logo" alt="" src="%s">' % (ART / "logos" / brand["logo"]).as_uri()
                           if brand["logo"] else "")
    values["illustration_html"] = ""
    if template == "template.html" and brand.get("illustration"):
        values["card_class"] = (values["card_class"] + " illustrated").strip()
        values["illustration_html"] = ('<img class="illustration" alt="" aria-hidden="true" src="%s">'
                                       % (ART / "logos" / brand["illustration"]).as_uri())
    return Template((ART / template).read_text()).substitute(values)


def render():
    from playwright.sync_api import sync_playwright

    solutions = json.loads((ROOT / "data/hst/solutions.json").read_text())["solutions"]
    brands = json.loads((ART / "brands.json").read_text())
    # Company copy belongs to banner artwork, not the product-only welcome catalogue; it leads the rotation.
    solutions.insert(0, dict(id="hasontech", **{k: brands["hasontech"][k] for k in ("name", "tagline")}))
    outputs, items = {}, []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--allow-file-access-from-files"])
        for solution in solutions:
            item = {k: solution[k] for k in ("id", "name", "tagline")}
            # Clicks go through the server-side counter, which redirects to the solution's page.
            item["url"] = "https://system.hasontech.vn/hst-office/go/" + solution["id"]
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
                    if brands[solution["id"]].get("illustration"):
                        art = page.locator(".illustration").bounding_box()
                        for selector in ("header", "p", ".cta", ".owner"):
                            box = page.locator(selector).bounding_box()
                            assert box["x"] + box["width"] <= art["x"] - 10, (solution["id"], selector)
                        cta = page.locator(".cta").bounding_box()
                        owner = page.locator(".owner").bounding_box()
                        assert cta["x"] + cta["width"] + 8 <= owner["x"], solution["id"]
                    blob = page.screenshot(omit_background=True)
                    name = f'{solution["id"]}@{scale}x.png'
                    outputs[ART / name] = blob
                    assert len(blob) <= 300 * 1024
                    item["image"][f"{scale}x"] = {"url": "banners/" + name,
                                                  "sha256": hashlib.sha256(blob).hexdigest(), "size": len(blob)}
                    page.close()
                # Compact art: logo and short name, legible at 160 px; the wide art is never cropped.
                item["imageCompact"] = {}
                page_path.write_text(markup(solution, brands[solution["id"]], "template-compact.html"), encoding="utf-8")
                for scale in (1, 2, 3):
                    page = browser.new_page(viewport={"width": COMPACT[0], "height": COMPACT[1]}, device_scale_factor=scale)
                    page.route("http://**/*", lambda route: route.abort())
                    page.route("https://**/*", lambda route: route.abort())
                    page.goto(page_path.as_uri())
                    page.evaluate("document.fonts.ready")
                    assert page.evaluate("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
                    for selector in ("h1", ".owner"):
                        box = page.locator(selector).bounding_box()
                        assert box["x"] >= 8 and box["x"] + box["width"] <= COMPACT[0] - 8, (solution["id"], selector)
                        assert page.evaluate(f"(e => e.scrollWidth <= e.clientWidth)(document.querySelector('{selector}'))")
                    assert page.locator(".owner").bounding_box()["y"] + 16 <= COMPACT[1] - 6, solution["id"]
                    blob = page.screenshot(omit_background=True)
                    name = f'{solution["id"]}-compact@{scale}x.png'
                    outputs[ART / name] = blob
                    assert len(blob) <= 300 * 1024
                    item["imageCompact"][f"{scale}x"] = {"url": "banners/" + name,
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
        for spec in list(item["image"].values()) + list(item["imageCompact"].values()):
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
    banner = Image.open(io.BytesIO(outputs[ART / "hst-post@1x.png"]))
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
