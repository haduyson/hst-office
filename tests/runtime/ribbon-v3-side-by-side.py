#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Side-by-side images of the real ribbon and the locked v3 mockup, one per main tab at one width.

Usage: python3 tests/runtime/ribbon-v3-side-by-side.py --mockup mockup-chot-v3.html --run DIR [--width 1920] --out DIR
DIR is the output of collect-ribbon-v3-dumps.py (collected.json and shots/<app>-w<width>-<index>.png). The mockup is
rendered in headless Chromium (playwright; PLAYWRIGHT_CHROMIUM names another Chromium binary) and every tab's window (.win[data-app][data-tab]) saved; each pair is put one
above the other (mockup first) in <out>/<app>-<tab id>-w<width>.png with a caption line. Needs playwright and Pillow.
"""
import argparse
import json
import os
import sys

APPS = {"writer": "writer", "calc": "sheets", "impress": "slides", "draw": "draw"}  # collector app -> mockup app


def mockup_shots(path, width, out):
    """{(mockup app, tab name): png path} of every main tab of the mockup at its default width."""
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as play:
        # a Chromium already on the machine when playwright's own revision is not installed (PLAYWRIGHT_CHROMIUM)
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM") or None
        browser = play.chromium.launch(executable_path=executable)
        page = browser.new_page(viewport={"width": width + 200, "height": 1200})
        page.goto("file://" + os.path.abspath(path))
        page.wait_for_timeout(4000)
        data = page.evaluate("() => DATA.apps.map(a => [a.id, a.tabs.filter(t => !t.ctx).map(t => [t.id, t.name])])")
        for app, tabs in data:
            for tab_id, name in tabs:
                node = page.query_selector(f'.win[data-app="{app}"][data-tab="{tab_id}"]')
                if node is None:
                    continue
                target = os.path.join(out, "mockup", f"{app}-{tab_id}.png")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                node.screenshot(path=target)
                found[(app, name)] = (tab_id, target)
        browser.close()
    return found


def stack(top, bottom, caption, target):
    from PIL import Image, ImageDraw
    images = [Image.open(top).convert("RGB"), Image.open(bottom).convert("RGB")]
    width = max(i.width for i in images)
    band = 22
    canvas = Image.new("RGB", (width, sum(i.height for i in images) + 2 * band), "white")
    draw = ImageDraw.Draw(canvas)
    y = 0
    for label, image in zip((f"Mockup v3 · {caption}", f"HST Office (build) · {caption}"), images):
        draw.text((6, y + 4), label, fill=(0, 0, 0))
        canvas.paste(image, (0, y + band))
        y += band + image.height
    canvas.save(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mockup", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(os.path.join(args.run, "collected.json"), encoding="utf-8") as handle:
        collected = json.load(handle)
    mock = mockup_shots(args.mockup, args.width, args.out)
    made, missing = 0, []
    for app, passes in collected.items():
        if not isinstance(passes, list):
            continue
        for width, names in passes:
            if width != args.width:
                continue
            for index, name in enumerate(names):
                shot = os.path.join(args.run, "shots", f"{app}-w{width}-{index:02d}.png")
                key = (APPS.get(app, app), name)
                if key not in mock or not os.path.exists(shot):
                    missing.append(f"{app} {name}")
                    continue
                tab_id, mock_png = mock[key]
                stack(mock_png, shot, f"{key[0]} › {name} · {width} px",
                      os.path.join(args.out, f"{key[0]}-{tab_id}-w{width}.png"))
                made += 1
    print(f"{made} side-by-side images in {args.out}; missing: {missing}")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
