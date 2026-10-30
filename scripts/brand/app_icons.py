# SPDX-License-Identifier: AGPL-3.0-only
"""Desktop application icons derived from the committed HST tile masters (branding/icons/app).

Each master is a 1024 px RGBA PNG rendered from its SVG (scripts/brand/render-app-icon-masters.py).
Sizes up to `smallMaxSize` are cut to `smallCropBox` first: the macOS-style 1024 grid leaves ~10%
margin around the tile, which would waste two of sixteen pixels; the crop lets the tile fill small
icons. Larger sizes keep the full grid (shadow included). Pillow only, so output is deterministic.
"""
import os

from PIL import Image

from .common import ROOT, png_bytes


def load_masters(spec):
    """{icon name: 1024 px RGBA master} for the product and every module."""
    cfg = spec["appIcons"]
    masters = {}
    for name in [cfg["productName"]] + [m["name"] for m in cfg["modules"]]:
        path = os.path.join(ROOT, cfg["masters"]["dir"], f"{name}.png")
        with Image.open(path) as image:
            master = image.convert("RGBA")
        side = cfg["masters"]["size"]
        if master.size != (side, side):
            raise SystemExit(f"{path}: expected {side}x{side}, got {master.size[0]}x{master.size[1]}")
        masters[name] = master
    return masters


def master_svg(spec, name):
    with open(os.path.join(ROOT, spec["appIcons"]["masters"]["dir"], f"{name}.svg"), "rb") as handle:
        return handle.read()


def render_icon(spec, master, size):
    """The icon at `size` px: tight crop for small sizes, full grid otherwise."""
    cfg = spec["appIcons"]
    if size <= cfg["smallMaxSize"]:
        master = master.crop(tuple(cfg["smallCropBox"]))
    if master.size == (size, size):
        return master.copy()
    return master.resize((size, size), Image.LANCZOS)


def module_names(spec):
    """{module id or "product": icon name}."""
    cfg = spec["appIcons"]
    names = {m["id"]: m["name"] for m in cfg["modules"]}
    names["product"] = cfg["productName"]
    return names


def build_app_icons(spec, masters):
    """Linux hicolor sources: <name>-<size>.png for every size and <name>.svg (scalable)."""
    cfg = spec["appIcons"]
    outputs = {}
    for name, master in sorted(masters.items()):
        for size in cfg["sizes"]:
            outputs[cfg["pattern"].format(name=name, size=size)] = png_bytes(render_icon(spec, master, size))
        outputs[cfg["scalablePattern"].format(name=name)] = master_svg(spec, name)
    return outputs
