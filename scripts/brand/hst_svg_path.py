# SPDX-License-Identifier: AGPL-3.0-only
"""SVG path data as absolute subpaths: parse, transform, format, and rectangle/ellipse contours."""
import math
import re

from hst_svg_math import EPS, SnapError, apply, arc_to_cubics, fmt, is_similarity, linear_scale


class _Scanner:
    NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

    def __init__(self, text):
        self.text, self.pos = text, 0

    def skip(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n,":
            self.pos += 1

    def command(self):
        self.skip()
        if self.pos < len(self.text) and self.text[self.pos].isalpha():
            self.pos += 1
            return self.text[self.pos - 1]
        return None

    def has_number(self):
        self.skip()
        return bool(self.NUMBER.match(self.text, self.pos))

    def number(self):
        self.skip()
        match = self.NUMBER.match(self.text, self.pos)
        if not match:
            raise SnapError(f"number expected at {self.pos} in {self.text!r}")
        self.pos = match.end()
        return float(match.group())

    def flag(self):
        self.skip()
        if self.pos < len(self.text) and self.text[self.pos] in "01":
            self.pos += 1
            return int(self.text[self.pos - 1])
        raise SnapError(f"arc flag expected at {self.pos} in {self.text!r}")


def parse_path(text):
    """Absolute subpaths: [{'start': p, 'segs': [...], 'closed': bool}].

    Segments: ('L', p), ('C', c1, c2, p), ('Q', c, p), ('A', rx, ry, phi, large, sweep, p).
    """
    scanner = _Scanner(text)
    subpaths, current, point, start = [], None, (0.0, 0.0), (0.0, 0.0)
    last_cubic = last_quad = None
    command = scanner.command()
    if command not in ("M", "m"):
        raise SnapError(f"path must start with a moveto: {text!r}")
    while command:
        relative = command.islower()
        kind = command.upper()

        def pt():
            x, y = scanner.number(), scanner.number()
            return (point[0] + x, point[1] + y) if relative else (x, y)

        if kind == "Z":
            if current is not None:
                current["closed"] = True
            point = start
            last_cubic = last_quad = None
            command = scanner.command()
            continue
        first = True
        while first or scanner.has_number():
            if kind == "M":
                point = pt()
                if first:
                    current = {"start": point, "segs": [], "closed": False}
                    subpaths.append(current)
                    start = point
                else:
                    current["segs"].append(("L", point))
                last_cubic = last_quad = None
            elif current is None:
                raise SnapError(f"drawing before moveto: {text!r}")
            elif kind == "L":
                point = pt()
                current["segs"].append(("L", point))
                last_cubic = last_quad = None
            elif kind in "HV":
                value = scanner.number()
                if kind == "H":
                    point = (point[0] + value if relative else value, point[1])
                else:
                    point = (point[0], point[1] + value if relative else value)
                current["segs"].append(("L", point))
                last_cubic = last_quad = None
            elif kind in "CS":
                if kind == "C":
                    c1 = pt()
                else:
                    c1 = (2 * point[0] - last_cubic[0], 2 * point[1] - last_cubic[1]) if last_cubic else point
                c2, end = pt(), pt()
                current["segs"].append(("C", c1, c2, end))
                point, last_cubic, last_quad = end, c2, None
            elif kind in "QT":
                if kind == "Q":
                    control = pt()
                else:
                    control = (2 * point[0] - last_quad[0], 2 * point[1] - last_quad[1]) if last_quad else point
                end = pt()
                current["segs"].append(("Q", control, end))
                point, last_quad, last_cubic = end, control, None
            elif kind == "A":
                rx, ry, phi = scanner.number(), scanner.number(), scanner.number()
                large, sweep = scanner.flag(), scanner.flag()
                end = pt()
                current["segs"].append(("A", abs(rx), abs(ry), phi, large, sweep, end))
                point, last_cubic, last_quad = end, None, None
            else:
                raise SnapError(f"unsupported path command {command!r}")
            first = False
        command = scanner.command()
    return subpaths


def transform_subpaths(subpaths, m):
    similar = is_similarity(m)
    rotation = math.degrees(math.atan2(m[1], m[0]))
    flips = m[0] * m[3] - m[1] * m[2] < 0
    k = linear_scale(m)
    result = []
    for sub in subpaths:
        point = sub["start"]
        segs = []
        for seg in sub["segs"]:
            if seg[0] == "A":
                if similar:
                    _, rx, ry, phi, large, sweep, end = seg
                    segs.append(("A", rx * k, ry * k, phi + rotation, large, (1 - sweep) if flips else sweep,
                                 apply(m, end)))
                else:
                    for piece in arc_to_cubics(point, *seg[1:]):
                        segs.append((piece[0],) + tuple(apply(m, q) for q in piece[1:]))
            else:
                segs.append((seg[0],) + tuple(apply(m, q) for q in seg[1:]))
            point = seg[-1]
        result.append({"start": apply(m, sub["start"]), "segs": segs, "closed": sub["closed"]})
    return result


def format_subpaths(subpaths):
    parts = []
    for sub in subpaths:
        parts.append(f"M{fmt(sub['start'][0])} {fmt(sub['start'][1])}")
        point = sub["start"]
        for seg in sub["segs"]:
            kind, end = seg[0], seg[-1]
            if kind == "L":
                if abs(end[1] - point[1]) < EPS and abs(end[0] - point[0]) > EPS:
                    parts.append(f"H{fmt(end[0])}")
                elif abs(end[0] - point[0]) < EPS and abs(end[1] - point[1]) > EPS:
                    parts.append(f"V{fmt(end[1])}")
                else:
                    parts.append(f"L{fmt(end[0])} {fmt(end[1])}")
            elif kind == "C":
                parts.append("C" + " ".join(f"{fmt(q[0])} {fmt(q[1])}" for q in seg[1:]))
            elif kind == "Q":
                parts.append("Q" + " ".join(f"{fmt(q[0])} {fmt(q[1])}" for q in seg[1:]))
            else:
                _, rx, ry, phi, large, sweep, _ = seg
                parts.append(f"A{fmt(rx)} {fmt(ry)} {fmt(phi % 360)} {large} {sweep} {fmt(end[0])} {fmt(end[1])}")
            point = end
        if sub["closed"]:
            parts.append("Z")
    return "".join(parts)


def rect_subpaths(x, y, w, h, rx, ry):
    if rx <= EPS and ry <= EPS:
        return [{"start": (x, y), "segs": [("L", (x + w, y)), ("L", (x + w, y + h)), ("L", (x, y + h))],
                 "closed": True}]
    rx, ry = min(rx, w / 2), min(ry, h / 2)
    return [{"start": (x + rx, y), "segs": [
        ("L", (x + w - rx, y)), ("A", rx, ry, 0, 0, 1, (x + w, y + ry)),
        ("L", (x + w, y + h - ry)), ("A", rx, ry, 0, 0, 1, (x + w - rx, y + h)),
        ("L", (x + rx, y + h)), ("A", rx, ry, 0, 0, 1, (x, y + h - ry)),
        ("L", (x, y + ry)), ("A", rx, ry, 0, 0, 1, (x + rx, y))], "closed": True}]


def ellipse_subpaths(cx, cy, rx, ry):
    return [{"start": (cx - rx, cy), "segs": [("A", rx, ry, 0, 1, 0, (cx + rx, cy)),
                                              ("A", rx, ry, 0, 1, 0, (cx - rx, cy))], "closed": True}]
