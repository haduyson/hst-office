# SPDX-License-Identifier: AGPL-3.0-only
"""Desktop icons: product icon (mark only) and per-module icons (mark + glyph badge)."""
from PIL import Image, ImageDraw

from .common import png_bytes

SS = 4  # supersampling factor for the vector-drawn badge


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _glyph(draw, kind, box, white, fill):
    """Draw a white module glyph inside box=(x0,y0,x1,y1) on the badge disc."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if kind == "writer":  # text lines
        for i, frac in enumerate((1.0, 1.0, 1.0, 0.6)):
            ly = y0 + h * (0.04 + i * 0.3)
            draw.rounded_rectangle((x0, ly, x0 + w * frac, ly + h * 0.15), radius=h * 0.05, fill=white)
    elif kind == "sheets":  # 2x2 grid cells
        gap = w * 0.12
        cell = (w - gap) / 2
        for r in range(2):
            for c in range(2):
                cx, cy = x0 + c * (cell + gap), y0 + r * (cell + gap)
                draw.rectangle((cx, cy, cx + cell, cy + cell), fill=white)
    else:  # slides: screen with play triangle
        draw.rounded_rectangle((x0, y0 + h * 0.08, x1, y1 - h * 0.08), radius=h * 0.1, fill=white)
        tx, ty, tw, th = x0 + w * 0.36, y0 + h * 0.3, w * 0.3, h * 0.4
        draw.polygon([(tx, ty), (tx, ty + th), (tx + tw, ty + th / 2)], fill=fill)


def module_icon(square, size, module, geometry):
    """Mark top-left, round badge bottom-right with a white ring and glyph."""
    big = size * SS
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    mark_side = round(big * geometry["markScale"])
    off = round(big * geometry["markOffset"])
    canvas.alpha_composite(square.resize((mark_side, mark_side), Image.LANCZOS), (off, off))
    diameter = big * geometry["badgeScale"]
    ring = max(SS, diameter * geometry["ringWidth"])
    bx1 = by1 = big * (1 - geometry["badgeMargin"])
    bx0, by0 = bx1 - diameter, by1 - diameter
    draw = ImageDraw.Draw(canvas)
    color = _rgb(module["color"]) + (255,)
    draw.ellipse((bx0 - ring, by0 - ring, bx1 + ring, by1 + ring), fill=(255, 255, 255, 255))
    draw.ellipse((bx0, by0, bx1, by1), fill=color)
    inset = diameter * 0.27
    _glyph(draw, module["id"], (bx0 + inset, by0 + inset, bx1 - inset, by1 - inset),
           (255, 255, 255, 255), color)
    return canvas.resize((size, size), Image.LANCZOS)


def product_icon(square, size, padding):
    inner = max(1, round(size * (1 - 2 * padding)))
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(square.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2,) * 2)
    return icon


def build_app_icons(spec, square):
    cfg = spec["appIcons"]
    outputs = {}
    for size in cfg["sizes"]:
        product = product_icon(square, size, spec["outputs"]["iconPadding"])
        outputs[cfg["pattern"].format(name=cfg["productName"], size=size)] = png_bytes(product)
        for module in cfg["modules"]:
            icon = module_icon(square, size, module, cfg["geometry"])
            outputs[cfg["pattern"].format(name=module["name"], size=size)] = png_bytes(icon)
    return outputs
