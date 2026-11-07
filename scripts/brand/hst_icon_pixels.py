# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel model of a snapped HST glyph at its target size, for the 16 px weight rule.

A pixel belongs to a stroke when its centre lies within half the pen of the centre line, to a
fill when its centre lies inside the shape (even-odd, as VCL fills these paths). On top of that:
background regions, 1 px gaps between strokes that do not touch, and contact between strokes.
Standard library only."""
import math

from hst_icon_outline import flatten
from hst_svg_math import EPS
from hst_svg_path import ellipse_subpaths, rect_subpaths

NEIGHBOURS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def _subpaths(shape):
    kind = shape[0]
    if kind in ("rect", "dot"):
        _, x0, y0, x1, y1, radius = shape
        return rect_subpaths(x0, y0, x1 - x0, y1 - y0, radius, radius)
    if kind == "ellipse":
        _, cx, cy, rx, ry = shape
        return ellipse_subpaths(cx, cy, rx, ry)
    return shape[1]


def polylines(shape):
    result = []
    for sub in _subpaths(shape):
        points, closed, _ = flatten(sub)
        result.append((points + points[:1]) if closed and len(points) > 1 else points)
    return result


def _segment_distance(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0.0 if length < EPS else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / length))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def stroke_pixels(shape, pen):
    """Pixels whose centre lies within pen/2 of the stroke's centre line."""
    half = pen / 2 + 1e-6
    pixels = set()
    for line in polylines(shape):
        pairs = list(zip(line, line[1:])) or [(line[0], line[0])]
        for a, b in pairs:
            for x in range(math.floor(min(a[0], b[0]) - half), math.ceil(max(a[0], b[0]) + half) + 1):
                for y in range(math.floor(min(a[1], b[1]) - half), math.ceil(max(a[1], b[1]) + half) + 1):
                    if (x, y) not in pixels and _segment_distance(x + 0.5, y + 0.5, a, b) <= half:
                        pixels.add((x, y))
    return pixels


def fill_pixels(shape):
    """Pixels whose centre lies inside the shape (even-odd, as VCL fills these paths)."""
    polygons = [line for line in polylines(shape) if len(line) > 2]
    if not polygons:
        return set()
    xs = [p[0] for line in polygons for p in line]
    ys = [p[1] for line in polygons for p in line]
    pixels = set()
    for y in range(math.floor(min(ys)), math.ceil(max(ys)) + 1):
        cy = y + 0.5
        for x in range(math.floor(min(xs)), math.ceil(max(xs)) + 1):
            cx, inside = x + 0.5, False
            for line in polygons:
                for a, b in zip(line, line[1:] + line[:1]):
                    if (a[1] > cy) != (b[1] > cy) and cx < a[0] + (cy - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                        inside = not inside
            if inside:
                pixels.add((x, y))
    return pixels


def background_regions(painted, size):
    seen, regions = set(), 0
    for start in ((x, y) for x in range(size) for y in range(size)):
        if start in painted or start in seen:
            continue
        regions += 1
        stack = [start]
        seen.add(start)
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < size and 0 <= ny < size and (nx, ny) not in painted and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    return regions


def gap_pixels(pieces, size):
    """1 px gaps: background pixels between two painted pixels on a straight or diagonal line,
    painted by two different subpaths that do not touch. Gaps inside one subpath (the apex of
    an A) and at an existing joint or crossing are left to the region and contact rules.
    pieces: {label: pixel set}."""
    owners = {}
    for label, pixels in pieces.items():
        for pixel in pixels:
            owners.setdefault(pixel, set()).add(label)
    touching = set()
    for (x, y), labels in owners.items():
        for dx, dy in NEIGHBOURS + [(0, 0)]:
            for other in owners.get((x + dx, y + dy), ()):
                touching.update((label, other) for label in labels)
    gaps = set()
    for x in range(size):
        for y in range(size):
            if (x, y) in owners:
                continue
            for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                left, right = owners.get((x - dx, y - dy), ()), owners.get((x + dx, y + dy), ())
                if any(a != b and (a, b) not in touching for a in left for b in right):
                    gaps.add((x, y))
                    break
    return gaps


def contact(pixels, others):
    return {q for x, y in pixels for dx, dy in NEIGHBOURS if (q := (x + dx, y + dy)) in others}


def extent(shape, pen):
    xs, ys = [], []
    for line in polylines(shape):
        xs += [p[0] for p in line]
        ys += [p[1] for p in line]
    half = pen / 2
    return min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half


def straight_segment(sub):
    """End points of a single straight axis-aligned segment, or None."""
    if sub["closed"] or len(sub["segs"]) != 1 or sub["segs"][0][0] != "L":
        return None
    (x0, y0), (x1, y1) = sub["start"], sub["segs"][0][1]
    if abs(x0 - x1) > EPS and abs(y0 - y1) > EPS:
        return None
    return (x0, y0), (x1, y1)
