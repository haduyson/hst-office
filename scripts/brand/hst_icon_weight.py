# SPDX-License-Identifier: AGPL-3.0-only
"""Heavier 16 px ink for the colourful HST style: 1 px pens become 2 px where the glyph has room.

At 16 px the snapped glyphs draw a 1 px pen and look lighter than the upstream sets (1.5-2 px). A
uniform 2 px pen would close the 1 px gaps of line art, so each stroked part widens on its own, only
when the pixel model (hst_icon_pixels) shows that the wider pen stays inside the canvas, creates or
closes no background region, consumes no 1 px gap pixel and creates none, touches no stroke it did
not touch (at most two more contact pixels at a joint), and leaves two thirds of every colour fill
visible.

Widening keeps the pixel lattice: a closed rectangle or ellipse grows inward; any other stroke moves
half a pixel diagonally so its 2 px pen sits on pixel edges, and a widened straight axis-aligned line
becomes a solid bar with half-pixel corner rounding (a 2 px round cap leaves grey corners at 1x). An
element is tried whole first, then subpath by subpath, except elements of straight lines only (text
lines, rules), which widen together or not at all. Fills and dots never change. Parts are tried in
paint order and the first passing placement wins, so the result is deterministic.
"""
import math

from hst_icon_pixels import background_regions, contact, fill_pixels, gap_pixels, polylines, stroke_pixels
from hst_svg_math import EPS
from hst_svg_path import transform_subpaths

SHIFTS = ((0.5, 0.5), (-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5))
FILL_KEPT = 2 / 3
EXTRA_CONTACT = 2
BAR_RADIUS = 0.5


def _extent(shape, pen):
    xs, ys = [], []
    for line in polylines(shape):
        xs += [p[0] for p in line]
        ys += [p[1] for p in line]
    half = pen / 2
    return min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half


def _candidates(shape):
    """Placements of a 2 px pen that keep the stroke on the pixel lattice."""
    kind = shape[0]
    if kind == "rect":
        _, x0, y0, x1, y1, radius = shape
        if x1 - x0 > 2 + EPS and y1 - y0 > 2 + EPS:
            yield ("rect", x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5, max(0.0, radius - 0.5) if radius else 0.0)
        return
    if kind == "ellipse":
        _, cx, cy, rx, ry = shape
        if rx > 1.5 and ry > 1.5:
            yield ("ellipse", cx, cy, rx - 0.5, ry - 0.5)
        return
    for dx, dy in SHIFTS:
        yield ("path", transform_subpaths(shape[1], (1.0, 0.0, 0.0, 1.0, dx, dy)))


def _parts(items):
    """Elements as separately painted parts (shape, pen, style, state, role): the fill and the
    stroke of an element are parts of their own, so a stroke can move without its fill."""
    parts = []
    for shape, pen, style, state in items:
        if shape[0] == "dot":
            parts.append((shape, None, style, state, "dot"))
            continue
        if style.get("fill", "black") != "none":
            parts.append((shape, None, dict(style, stroke="none"), state, "fill"))
        if pen is not None:
            parts.append((shape, pen, dict(style, fill="none"), state, "stroke"))
    return parts


def _pieces(part, shape=None, pen=None):
    """Pixel sets of a part, one per subpath of a stroked path (the units of the gap rule)."""
    shape, pen = shape or part[0], pen or part[1]
    if part[4] != "stroke":
        return [fill_pixels(shape)]
    if shape[0] == "path":
        return [stroke_pixels(("path", [sub]), pen) for sub in shape[1]]
    return [stroke_pixels(shape, pen)]


def _visible_fills(parts, pixels):
    """Visible pixel count of each fill part under the parts painted after it."""
    top = {}
    for index, part in enumerate(parts):
        for pixel in pixels[index]:
            top[pixel] = index
    counts = {index: 0 for index, part in enumerate(parts) if part[4] == "fill"}
    for index in top.values():
        if index in counts:
            counts[index] += 1
    return counts


def _contact_allowed(before, after):
    """A stroke may not newly touch another one, and may only slightly extend an existing joint."""
    new = after - before
    return not new or (bool(before) and len(new) <= EXTRA_CONTACT)


def _labelled(pieces, index=None, replacement=None):
    result = {}
    for i, sets in enumerate(pieces):
        for k, pixels in enumerate(replacement if i == index else sets):
            result[(i, k)] = pixels
    return result


def _union(sets):
    return set().union(*sets) if sets else set()


def _widen(parts, pieces, index, size, base_fills):
    """Placement of a 2 px pen for parts[index] (with its pixel sets) that passes every rule, or None."""
    shape = parts[index][0]
    pixels = [_union(sets) for sets in pieces]
    painted = _union([p for i, p in enumerate(pixels) if i != index])
    strokes = [i for i in range(len(parts)) if i != index and parts[i][4] != "fill"]
    before = pixels[index]
    regions = background_regions(painted | before, size)
    gaps = gap_pixels(_labelled(pieces), size)
    touched = {i: contact(before, pixels[i]) for i in strokes}
    for candidate in _candidates(shape):
        x0, y0, x1, y1 = _extent(candidate, 2)
        if x0 < -EPS or y0 < -EPS or x1 > size + EPS or y1 > size + EPS:
            continue
        sets = _pieces(parts[index], candidate, 2)
        after = _union(sets)
        if (after - before) & gaps or not gap_pixels(_labelled(pieces, index, sets), size) <= gaps:
            continue
        if background_regions(painted | after, size) != regions:
            continue
        if not all(_contact_allowed(touched[i], contact(after, pixels[i])) for i in strokes):
            continue
        trial = pixels[:index] + [after] + pixels[index + 1:]
        fills = _visible_fills(parts, trial)
        if any(fills[i] < math.ceil(FILL_KEPT * count) for i, count in base_fills.items()):
            continue
        return candidate, sets
    return None


def embolden(items, size):
    """Items (shape, pen, style, state) with 1 px strokes widened to 2 px where the glyph has room.

    A stroked element is first widened as a whole (letterforms keep their joints); when that
    fails, each of its subpaths is tried on its own."""
    parts = _parts(items)
    pieces = [_pieces(part) for part in parts]
    # visible pixels per fill part, keyed by the part itself: splitting a stroke shifts indices
    base = {id(parts[i]): count for i, count in _visible_fills(parts, [_union(p) for p in pieces]).items()}
    index = 0
    while index < len(parts):
        shape, pen, style, state, role = parts[index]
        if role == "stroke" and pen == 1:
            base_fills = {i: base[id(part)] for i, part in enumerate(parts) if part[4] == "fill"}
            found = _widen(parts, pieces, index, size, base_fills)
            if found is not None:
                parts[index] = (found[0], 2, style, state, role)
                pieces[index] = found[1]
            elif shape[0] == "path" and len(shape[1]) > 1 and not all(_straight(sub) for sub in shape[1]):
                # text lines and rules widen together or not at all, so their rhythm stays even
                split = [(("path", [sub]), pen, style, state, role) for sub in shape[1]]
                parts[index:index + 1] = split
                pieces[index:index + 1] = [_pieces(part) for part in split]
                continue
        index += 1
    result = []
    for shape, pen, style, state, role in parts:
        if role == "stroke" and pen == 2 and shape[0] == "path":
            result += [_bar(sub, style, state) or (("path", [sub]), pen, style, state) for sub in shape[1]]
        else:
            result.append((shape, pen, style, state))
    return result


def _straight(sub):
    """End points of a single straight axis-aligned segment, or None."""
    if sub["closed"] or len(sub["segs"]) != 1 or sub["segs"][0][0] != "L":
        return None
    (x0, y0), (x1, y1) = sub["start"], sub["segs"][0][1]
    if abs(x0 - x1) > EPS and abs(y0 - y1) > EPS:
        return None
    return (x0, y0), (x1, y1)


def _bar(sub, style, state):
    """A widened straight axis-aligned line as a filled bar of the cap's length (solid at 1x)."""
    ends = _straight(sub)
    if ends is None:
        return None
    (x0, y0), (x1, y1) = ends
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    fill = dict(style, fill=style["stroke"], stroke="none")
    if "stroke-opacity" in style:
        fill["fill-opacity"] = style["stroke-opacity"]
    return ("rect", x0 - 1, y0 - 1, x1 + 1, y1 + 1, BAR_RADIUS), None, fill, state
