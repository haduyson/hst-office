# SPDX-License-Identifier: AGPL-3.0-only
"""Numbers, affine transforms and arcs for the HST glyph snapper (standard library only)."""
import math
import re

EPS = 1e-9

class SnapError(ValueError):
    pass


def round_half_up(value):
    return math.floor(value + 0.5)


def fmt(value):
    """Compact, deterministic number formatting (3 decimals at most)."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def multiply(m, n):
    """m applied after n; matrices are (a, b, c, d, e, f) as in SVG."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def apply(m, point):
    a, b, c, d, e, f = m
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(text):
    result = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        values = [float(v) for v in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)]
        if name == "translate":
            m = (1, 0, 0, 1, values[0], values[1] if len(values) > 1 else 0.0)
        elif name == "scale":
            sx = values[0]
            m = (sx, 0, 0, values[1] if len(values) > 1 else sx, 0, 0)
        elif name == "rotate":
            angle = math.radians(values[0])
            cos, sin = math.cos(angle), math.sin(angle)
            m = (cos, sin, -sin, cos, 0, 0)
            if len(values) == 3:
                cx, cy = values[1], values[2]
                m = multiply((1, 0, 0, 1, cx, cy), multiply(m, (1, 0, 0, 1, -cx, -cy)))
        elif name == "matrix" and len(values) == 6:
            m = tuple(values)
        else:
            raise SnapError(f"unsupported transform: {name}")
        result = multiply(result, m)
    return result


def is_similarity(m):
    a, b, c, d = m[:4]
    return abs(a * a + b * b - c * c - d * d) < 1e-6 and abs(a * c + b * d) < 1e-6


def axis_aligned(m):
    """True for transforms that keep horizontal and vertical lines so (multiples of 90 degrees)."""
    a, b, c, d = m[:4]
    return (abs(b) < 1e-9 and abs(c) < 1e-9) or (abs(a) < 1e-9 and abs(d) < 1e-9)


def linear_scale(m):
    a, b, c, d = m[:4]
    return math.sqrt(abs(a * d - b * c))


def arc_to_cubics(p0, rx, ry, phi, large, sweep, p1):
    """SVG arc as cubic segments (endpoint parameterisation, SVG 1.1 F.6)."""
    if rx < EPS or ry < EPS or (abs(p0[0] - p1[0]) < EPS and abs(p0[1] - p1[1]) < EPS):
        return [("L", p1)]
    angle = math.radians(phi)
    cos, sin = math.cos(angle), math.sin(angle)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cos * dx + sin * dy, -sin * dx + cos * dy
    scale = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    factor = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx1, cy1 = factor * rx * y1 / ry, -factor * ry * x1 / rx
    cx = cos * cx1 - sin * cy1 + (p0[0] + p1[0]) / 2
    cy = sin * cx1 + cos * cy1 + (p0[1] + p1[1]) / 2

    def vector_angle(ux, uy, vx, vy):
        value = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return value

    theta = vector_angle(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    delta = vector_angle((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    pieces = max(1, math.ceil(abs(delta) / (math.pi / 2) - 1e-9))
    step = delta / pieces
    k = 4 / 3 * math.tan(step / 4)
    segs = []

    def at(t):
        return (cx + rx * math.cos(t) * cos - ry * math.sin(t) * sin,
                cy + rx * math.cos(t) * sin + ry * math.sin(t) * cos)

    def derivative(t):
        return (-rx * math.sin(t) * cos - ry * math.cos(t) * sin,
                -rx * math.sin(t) * sin + ry * math.cos(t) * cos)

    t = theta
    for index in range(pieces):
        start, end = at(t), at(t + step)
        d0, d1 = derivative(t), derivative(t + step)
        c1 = (start[0] + k * d0[0], start[1] + k * d0[1])
        c2 = (end[0] - k * d1[0], end[1] - k * d1[1])
        segs.append(("C", c1, c2, p1 if index == pieces - 1 else end))
        t += step
    return segs
