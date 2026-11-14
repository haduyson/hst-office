# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel-snap a 24-unit HST glyph master for one raster size.

The masters (icon-themes-src/hst/glyphs/) are drawn on a 24-unit grid with a 1.65-unit pen.
Scaled as they are, the pen becomes 1.10/1.65/2.20 px and most edges fall on fractions of a
pixel, which VCL renders as grey fringes. snap_svg() instead emits geometry in target pixels:

* every pen becomes a whole number of pixels: 1 px at 16, 24 and 32 for the 1.65-unit pen, the
  weight of Colibre at every size; pens 1.4 times heavier or more (bold B, colour bars) stay at
  least 2 px, never below 1 px;
* group transforms are flattened, so badge pens scaled by 0.75 and the like are snapped too;
* axis-aligned geometry lands on the pixel lattice of its pen: line centres of an odd pen on
  pixel centres, of an even pen on pixel edges; rectangle and circle edges on pixel edges.
  Curve control points follow their end points, so shapes keep their curvature;
* geometry under a rotation that is not a multiple of 90 degrees is only flattened.

The lattice is that of the SVG pixel convention (pixel k covers [k, k+1]); HST's VCL patch
rasterises icons in this convention at every scale, so the same file is sharp at 1x and 2x.
Pure standard library; deterministic output.
"""
import re
import xml.etree.ElementTree as ET
from html import escape

from hst_icon_emit import INHERITED, emit, emit_stroked, DRAFT_STYLE
from hst_icon_weight import embolden
from hst_icon_lattice import TARGET_PEN, lattice, snap_outline, snap_subpaths, snap_value, target_pen
from hst_svg_math import EPS, SnapError, apply, axis_aligned, is_similarity, linear_scale, multiply, parse_transform, round_half_up
from hst_svg_path import ellipse_subpaths, parse_path, rect_subpaths, transform_subpaths

SVG_NS = "http://www.w3.org/2000/svg"
GRID = 24.0


def float_attr(element, name, default=0.0):
    value = element.get(name)
    return default if value is None else float(value)


def snap_element(tag, element, style, m, size, native=False):
    """Return (shape, pen) for one element, flattened and snapped in target pixels.

    shape is ('rect', x0, y0, x1, y1, radius), ('ellipse', cx, cy, rx, ry) or ('path', subpaths);
    pen is the whole-pixel stroke width, or None for an unstroked element.
    native: a hand-tuned master drawn in target pixels; its geometry and pens are kept as drawn.
    """
    stroked = style.get("stroke", "none") != "none"
    pen = None
    if stroked and native:
        width = float(style.get("stroke-width", "1")) * linear_scale(m)
        pen = round_half_up(width)
        if abs(width - pen) > 1e-6 or pen < 1:
            raise SnapError(f"hand-tuned pens are whole pixels, not {width:g}")
    elif stroked:
        pen = target_pen(float(style.get("stroke-width", "1")) * linear_scale(m) / (size / GRID), size)
    offset = lattice(pen)
    straight = axis_aligned(m)
    snap = (lambda value, _offset: value) if native else snap_value
    similar = is_similarity(m)
    k = linear_scale(m)
    if tag == "rect" and straight:
        x, y = float_attr(element, "x"), float_attr(element, "y")
        w, h = float_attr(element, "width"), float_attr(element, "height")
        rx = float_attr(element, "rx", None) if element.get("rx") is not None else None
        ry = float_attr(element, "ry", None) if element.get("ry") is not None else None
        rx, ry = (rx if rx is not None else (ry or 0.0)), (ry if ry is not None else (rx or 0.0))
        corners = [apply(m, (x, y)), apply(m, (x + w, y + h))]
        x0, x1 = sorted(snap(q[0], offset) for q in corners)
        y0, y1 = sorted(snap(q[1], offset) for q in corners)
        radius = rx * k
        if radius > EPS and not native:
            # Small corner radii read as soft corners only; keep them a whole pixel at least.
            radius = max(1.0, round_half_up(radius * 2) / 2)
        return ("rect", x0, y0, x1, y1, radius if radius > EPS else 0.0), pen
    if tag in ("circle", "ellipse") and similar and straight:
        cx, cy = apply(m, (float_attr(element, "cx"), float_attr(element, "cy")))
        if tag == "circle":
            rx = ry = float_attr(element, "r") * k
        else:
            rx, ry = float_attr(element, "rx") * k, float_attr(element, "ry") * k
            if abs(m[1]) > 1e-9:  # a quarter turn swaps the axes
                rx, ry = ry, rx
        if not native:
            cx, rx = snap_outline(cx, rx, pen)
            cy, ry = snap_outline(cy, ry, pen)
        width, height = 2 * rx + (pen or 0), 2 * ry + (pen or 0)
        if width <= 3 and height <= 3:
            # A round dot of three pixels or less is only grey corners: paint it as a solid square.
            return ("dot", cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2, 0.0), None
        return ("ellipse", cx, cy, rx, ry), pen
    if tag == "rect":
        subpaths = rect_subpaths(float_attr(element, "x"), float_attr(element, "y"), float_attr(element, "width"),
                                 float_attr(element, "height"), float_attr(element, "rx"),
                                 float_attr(element, "ry", float_attr(element, "rx")))
    elif tag == "circle":
        r = float_attr(element, "r")
        subpaths = ellipse_subpaths(float_attr(element, "cx"), float_attr(element, "cy"), r, r)
    elif tag == "ellipse":
        subpaths = ellipse_subpaths(float_attr(element, "cx"), float_attr(element, "cy"),
                                    float_attr(element, "rx"), float_attr(element, "ry"))
    elif tag == "path":
        subpaths = parse_path(element.get("d", ""))
    else:
        raise SnapError(f"unsupported element: {tag}")
    subpaths = transform_subpaths(subpaths, m)
    if straight and not native:
        subpaths = snap_subpaths(subpaths, offset)
    return ("path", subpaths), pen


def snap_svg(source, size, outline=True, native=False, heavy=False):
    """SVG text of `source` for a `size` px raster.

    A 24-unit master is snapped; a native (hand-tuned) master, drawn on a viewBox of the raster
    size with whole-pixel pens, is kept as drawn. outline=True paints strokes as filled outlines (what the theme ships);
    False keeps them as editable strokes (the starting point of a hand-tuned master).
    heavy=True widens 1 px pens to 2 px at 16 px where the glyph has room (hst_icon_weight).
    """
    if size not in TARGET_PEN:
        raise SnapError(f"unsupported size: {size}")
    root = ET.fromstring(source)
    expected = f"0 0 {size} {size}" if native else "0 0 24 24"
    if root.get("viewBox") != expected:
        raise SnapError(f"unexpected viewBox {root.get('viewBox')!r}, expected {expected!r}")
    scale = 1.0 if native else size / GRID
    title = root.findtext(f"{{{SVG_NS}}}title") or ""
    desc = root.findtext(f"{{{SVG_NS}}}desc") or ""
    items = []

    def walk(node, style, m):
        for child in node:
            tag = child.tag.split("}")[-1]
            if tag in ("title", "desc"):
                continue
            own = dict(style)
            for name in INHERITED:
                if child.get(name) is not None:
                    own[name] = child.get(name)
            matrix = multiply(m, parse_transform(child.get("transform"))) if child.get("transform") else m
            if tag == "g":
                walk(child, own, matrix)
                continue
            shape, pen = snap_element(tag, child, own, matrix, size, native)
            items.append((shape, pen, own, child.get("data-state")))

    style = {"fill": "black", "stroke": "none", "stroke-width": "1"}
    walk(root, style, (scale, 0.0, 0.0, scale, 0.0, 0.0))
    if heavy and size == 16:
        items = embolden(items, size)
    if outline:
        shapes = [svg for item in items for svg in emit(*item)]
    else:
        shapes = [emit_stroked(*item) for item in items]
    if not shapes:
        raise SnapError("master has no shapes")
    comment = ""
    match = re.search(r"<!--.*?-->", source, re.S)
    if match:
        comment = match.group() + "\n"
    if not native:
        desc = f"{desc} Pixel-snapped for {size} px."
    head = (f'<?xml version="1.0" encoding="UTF-8"?>\n{comment}'
            f'<svg xmlns="{SVG_NS}" width="{size}" height="{size}" viewBox="0 0 {size} {size}">\n'
            f"  <title>{escape(title)}</title>\n  <desc>{escape(desc)}</desc>\n")
    if outline:
        return head + "  " + "\n  ".join(shapes) + "\n</svg>\n"
    group = " ".join(f'{k}="{v}"' for k, v in DRAFT_STYLE.items())
    return head + f"  <g {group}>\n    " + "\n    ".join(shapes) + "\n  </g>\n</svg>\n"
