# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers for check-ribbon-banner.py: expected items, banner recognition, ribbon geometry.

The banner is recognised in screenshots by comparing the drawn slot with every bundled artwork,
fitted exactly as sfx2 HstBannerGeometry.hxx fits it (3 px inset per DPI step, aspect-fit, centred).
"""
import json
import os
import re
import subprocess
import time

from PIL import Image
import numpy

EXT = "share/extensions/hst-vietnamese-tools"
MATCH = 18.0  # mean absolute RGB difference of a matching artwork (fitted, anti-aliased)
MARGIN = 5.0  # the best artwork must beat the second best by this much


def items(instdir):
    """[{id, name, tagline, url (click URL with UTM), art: {1: path, 2: path, 3: path}}] in rotation order."""
    root = os.path.join(instdir, EXT)
    with open(os.path.join(root, "data/banners.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    with open(os.path.join(root, "data/solutions.json"), encoding="utf-8") as handle:
        utm = json.load(handle)["utm"]
    query = f"utm_source={utm['source']}&utm_medium=banner&utm_campaign={utm['campaign']}"
    result = []
    for item in sorted(manifest["items"], key=lambda i: (i["order"], i["id"])):
        base = re.split(r"[?#]", item["url"])[0]
        result.append({"id": item["id"], "name": item["name"], "tagline": item["tagline"],
                       "url": f"{base}?{query}", "home": f"https://hasontech.vn?{query}", "label": f"{item['name']} — {item['tagline']}",
                       "art": {int(k[0]): os.path.join(root, v["url"]) for k, v in item["image"].items()}})
    return result, manifest.get("rotateSeconds", 10)


def fitted(box, image_w, image_h, scale):
    """Inner rectangle the control draws the image into (screen coordinates)."""
    inset = round(3 * scale)
    x, y, w, h = box[0] + inset, box[1] + inset, box[2] - 2 * inset, box[3] - 2 * inset
    if w * image_h > image_w * h:
        fw, fh = max(1, h * image_w // image_h), h
    else:
        fw, fh = w, max(1, w * image_h // image_w)
    return x + (w - fw) // 2, y + (h - fh) // 2, fw, fh


def score(shot, box, art_path, scale):
    """Mean absolute difference between the drawn slot and one artwork fitted into it."""
    art = Image.open(art_path).convert("RGBA")
    x, y, w, h = fitted(box, art.width, art.height, scale)
    crop = shot.crop((x, y, x + w, y + h)).convert("RGB")
    background = Image.new("RGBA", (w, h), shot.getpixel((box[0] + 1, box[1] + box[3] // 2))[:3] + (255,))
    expected = Image.alpha_composite(background, art.resize((w, h), Image.LANCZOS)).convert("RGB")
    return float(numpy.abs(numpy.asarray(crop, dtype=float) - numpy.asarray(expected, dtype=float)).mean())


def recognise(shot_path, box, catalogue, scale, extra=()):
    """(id of the artwork drawn in box or None, best score, second score). extra: [(id, path)]."""
    shot = Image.open(shot_path).convert("RGB")
    variant = min(3, max(1, round(scale)))
    candidates = [(i["id"], i["art"][variant]) for i in catalogue] + list(extra)
    scores = sorted((score(shot, box, path, scale), ident) for ident, path in candidates)
    best, second = scores[0], scores[1] if len(scores) > 1 else (999.0, None)
    ok = best[0] <= MATCH and second[0] - best[0] >= MARGIN
    return (best[1] if ok else None), round(best[0], 1), round(second[0], 1)


def doc_tabs_top(display, timeout=20):
    """(frame y, top of the document tab bar) from AT-SPI: the ribbon ends where the tab bar starts."""
    import pyatspi
    deadline = time.time() + timeout
    while time.time() < deadline:
        desktop = pyatspi.Registry.getDesktop(0)
        for index in range(desktop.childCount):
            app = desktop.getChildAtIndex(index)
            if "office" not in (app.name or "").lower():
                continue
            for frame in (app.getChildAtIndex(i) for i in range(app.childCount)):
                found = _find(frame, "Thẻ tài liệu", 0)
                if found is not None:
                    top = frame.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).y
                    return top, found.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).y
        time.sleep(1)
    return None, None


def _find(node, name, depth):
    try:
        if node.name == name and node.getRoleName() == "panel":
            return node
        if depth < 7:
            for index in range(node.childCount):
                hit = _find(node.getChildAtIndex(index), name, depth + 1)
                if hit is not None:
                    return hit
    except Exception:  # noqa: BLE001 - widgets come and go
        pass
    return None


SKIP = ("document text", "document spreadsheet", "document presentation", "menu bar", "status bar", "ruler")


def _walk(node, depth, out):
    try:
        role = node.getRoleName()
        if role == "link":
            out.append(node)
        if depth < 14 and role not in SKIP:
            for index in range(node.childCount):
                _walk(node.getChildAtIndex(index), depth + 1, out)
    except Exception:  # noqa: BLE001 - widgets come and go
        pass
    return out


def banner_nodes():
    """Visible accessible links of the office: the ribbon banner, reached through the tree as a screen reader does."""
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    found = []
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            found += _walk(app, 0, [])
    return [n for n in found if n.getState().contains(pyatspi.STATE_SHOWING)]


def describe(node):
    import pyatspi
    ext = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    return {"role": node.getRoleName(), "name": node.name, "box": [ext.x, ext.y, ext.width, ext.height]}


def make_oversized(path):
    """2000x600 test image with a distinctive layout (not one of the bundled artworks)."""
    image = Image.new("RGB", (2000, 600), (250, 250, 250))
    pixels = image.load()
    for x in range(2000):
        for y in range(0, 600, 6):
            if (x // 125) % 2 == 0:
                pixels[x, y] = (200, 30, 30)
    for x in range(600, 1400):
        for y in range(150, 450):
            pixels[x, y] = (20, 60, 160)
    image.save(path)
    return path
