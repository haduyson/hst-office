# SPDX-License-Identifier: AGPL-3.0-only
"""Paint the round-capped, round-joined strokes of a snapped HST glyph as filled outlines.

VCL draws stroked lines with a half-device-pixel offset but fills polygons without one, so only
a filled outline in SVG's own convention is sharp at every whole scale. A stroke becomes one
ribbon polygon per smooth run plus a disc per join and cap. VCL fills multi-contour paths
even-odd in practice (also with fill-rule="nonzero", tested through its rasteriser), so
overlapping parts are separate <path> elements; only hole-making contour pairs share one.
"""
import math

from hst_svg_math import EPS, arc_to_cubics, fmt
from hst_svg_path import rect_subpaths

FLATTEN_STEP = 0.35  # px of control-polygon length per flattened piece


def _bezier(points, t):
    while len(points) > 1:
        points = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(points, points[1:])]
    return points[0]


def _flatten_curve(control):
    length = sum(math.dist(a, b) for a, b in zip(control, control[1:]))
    pieces = max(2, math.ceil(length / FLATTEN_STEP))
    return [_bezier(control, i / pieces) for i in range(1, pieces + 1)]


def flatten(sub):
    """Polyline of one subpath: (points, closed, corner flags)."""
    points, corners = [sub["start"]], [True]
    point = sub["start"]
    for seg in sub["segs"]:
        kind = seg[0]
        if kind == "L":
            new = [seg[1]]
        elif kind == "C":
            new = _flatten_curve([point, seg[1], seg[2], seg[3]])
        elif kind == "Q":
            new = _flatten_curve([point, seg[1], seg[2]])
        else:
            new = []
            start = point
            for piece in arc_to_cubics(point, *seg[1:]):
                new += [piece[1]] if piece[0] == "L" else _flatten_curve([start, piece[1], piece[2], piece[3]])
                start = piece[-1]
        points += new
        corners += [False] * (len(new) - 1) + [True]
        point = seg[-1]
    if sub["closed"] and math.dist(points[0], points[-1]) < EPS and len(points) > 1:
        points.pop()
        corners.pop()
    return points, sub["closed"], corners


def signed_area(points):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2


def polygon(points, positive=True):
    """Closed polygon path data with the requested winding (positive: clockwise on screen)."""
    if (signed_area(points) > 0) != positive:
        points = points[::-1]
    return f"M{fmt(points[0][0])} {fmt(points[0][1])}" + "".join(
        f"L{fmt(x)} {fmt(y)}" for x, y in points[1:]) + "Z"


def disc(centre, radius):
    """Positive (clockwise on screen) circle as two arcs."""
    x, y = centre
    r = fmt(radius)
    return f"M{fmt(x - radius)} {fmt(y)}A{r} {r} 0 1 1 {fmt(x + radius)} {fmt(y)}A{r} {r} 0 1 1 {fmt(x - radius)} {fmt(y)}Z"


def ellipse(cx, cy, rx, ry, positive=True):
    sweep = 1 if positive else 0
    return (f"M{fmt(cx - rx)} {fmt(cy)}A{fmt(rx)} {fmt(ry)} 0 1 {sweep} {fmt(cx + rx)} {fmt(cy)}"
            f"A{fmt(rx)} {fmt(ry)} 0 1 {sweep} {fmt(cx - rx)} {fmt(cy)}Z")


CORNER_DEGREES = 25.0  # a turn sharper than this is a join (disc); gentler turns stay in one ribbon


def _turn(a, b, c):
    """Absolute turn in degrees at b between the directions a->b and b->c."""
    u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    return abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))


def _dedupe(points, closed):
    result = []
    for point in points:
        if not result or math.dist(result[-1], point) > EPS:
            result.append(point)
    if closed and len(result) > 1 and math.dist(result[0], result[-1]) < EPS:
        result.pop()
    return result


def _offsets(run, half):
    """Left and right offset polylines of an open polyline with mitred (bounded) interior normals."""
    normals = []
    for a, b in zip(run, run[1:]):
        length = math.dist(a, b)
        normals.append((-(b[1] - a[1]) / length, (b[0] - a[0]) / length))
    left, right = [], []
    for index, point in enumerate(run):
        if index == 0:
            nx, ny = normals[0]
        elif index == len(run) - 1:
            nx, ny = normals[-1]
        else:
            (ax, ay), (bx, by) = normals[index - 1], normals[index]
            mx, my = ax + bx, ay + by
            norm = math.hypot(mx, my)
            cos_half = max(norm / 2, 0.5)  # bounded miter; sharper turns are split into joins
            nx, ny = mx / norm / cos_half, my / norm / cos_half
        left.append((point[0] + nx * half, point[1] + ny * half))
        right.append((point[0] - nx * half, point[1] - ny * half))
    return left, right


def stroke_path(subpaths, pen):  # -> list of path data, one per separately painted part
    """Filled outline of round-capped, round-joined strokes of width `pen`.

    Each smooth run between joins becomes one ribbon polygon; joins and open ends get a disc.
    """
    half = pen / 2
    parts, centres = [], set()

    def join(point):
        # Coincident contours (an arrow shaft ending in its head) confuse the nonzero solver:
        # one disc per point and element.
        key = (round(point[0], 3), round(point[1], 3))
        if key not in centres:
            centres.add(key)
            parts.append(disc(point, half))

    for sub in subpaths:
        points, closed, _ = flatten(sub)
        points = _dedupe(points, closed)
        if len(points) == 1:
            join(points[0])
            continue
        count = len(points)
        corners = [index for index in range(count)
                   if (closed or 0 < index < count - 1)
                   and _turn(points[index - 1], points[index], points[(index + 1) % count]) > CORNER_DEGREES]
        if closed and not corners:
            # A smooth closed loop: outer and inner contour of opposite winding.
            left, right = _offsets(points + points[:2], half)
            left, right = left[1:-1], right[1:-1]
            big, small = sorted((left, right), key=lambda q: abs(signed_area(q)), reverse=True)
            parts.append(polygon(big, True) + polygon(small, False))
            continue
        if closed:
            first = corners[0]
            points = points[first:] + points[:first + 1]
            corners = [index - first if index >= first else index - first + count for index in corners] + [count]
        else:
            corners = [0] + corners + [count - 1]
        for begin, finish in zip(corners, corners[1:]):
            run = points[begin:finish + 1]
            if len(run) < 2:
                continue
            left, right = _offsets(run, half)
            parts.append(polygon(left + right[::-1], True))
        for index in sorted({index % len(points) for index in corners}):
            join(points[index])
    return parts


def stroke_rect(x0, y0, x1, y1, radius, pen):
    """Outline of a stroked (optionally rounded) rectangle with round joins."""
    half = pen / 2
    outer = rect_subpaths(x0 - half, y0 - half, x1 - x0 + pen, y1 - y0 + pen, radius + half, radius + half)
    data = polygon(flatten(outer[0])[0], True)
    w, h = x1 - x0 - pen, y1 - y0 - pen
    if w > EPS and h > EPS:
        inner_radius = max(0.0, radius - half)
        inner = rect_subpaths(x0 + half, y0 + half, w, h, inner_radius, inner_radius)
        data += polygon(flatten(inner[0])[0], False)
    return data


def stroke_ellipse(cx, cy, rx, ry, pen):
    half = pen / 2
    data = ellipse(cx, cy, rx + half, ry + half, True)
    if rx - half > EPS and ry - half > EPS:
        data += ellipse(cx, cy, rx - half, ry - half, False)
    return data
