# SPDX-License-Identifier: AGPL-3.0-only
"""Whole-pixel pens and the pixel lattice of the HST glyph snapper.

Pens: 1.65 units on the 24-unit grid become 1 px at 16, 2 px (bold) at 24 and 3 px at 32; heavier
pens keep their ratio. Line centres of odd pens sit on pixel centres, of even pens on pixel edges
(SVG convention: pixel k covers [k, k+1]); round shapes get their outer edges on pixel edges."""
from hst_svg_math import round_half_up

BASE_PEN = 1.65
TARGET_PEN = {16: 1, 24: 2, 32: 3}

def target_pen(width_units, size):
    """Whole-pixel pen for a pen of `width_units` on the 24-unit grid."""
    return max(1, round_half_up(width_units / BASE_PEN * TARGET_PEN[size]))


def lattice(pen):
    """Offset of the snapping lattice: line centres of odd pens on pixel centres."""
    return 0.5 if pen is not None and pen % 2 else 0.0


def snap_value(value, offset):
    return round_half_up(value - offset) + offset


def snap_point(point, offset):
    return (snap_value(point[0], offset), snap_value(point[1], offset))


def snap_subpaths(subpaths, offset):
    result = []
    for sub in subpaths:
        start = snap_point(sub["start"], offset)
        delta_prev = (start[0] - sub["start"][0], start[1] - sub["start"][1])
        segs = []
        for seg in sub["segs"]:
            end = snap_point(seg[-1], offset)
            delta = (end[0] - seg[-1][0], end[1] - seg[-1][1])
            if seg[0] == "C":
                c1 = (seg[1][0] + delta_prev[0], seg[1][1] + delta_prev[1])
                c2 = (seg[2][0] + delta[0], seg[2][1] + delta[1])
                segs.append(("C", c1, c2, end))
            elif seg[0] == "Q":
                c = (seg[1][0] + (delta_prev[0] + delta[0]) / 2, seg[1][1] + (delta_prev[1] + delta[1]) / 2)
                segs.append(("Q", c, end))
            else:
                segs.append(seg[:-1] + (end,))
            delta_prev = delta
        result.append({"start": start, "segs": segs, "closed": sub["closed"]})
    return result


def snap_outline(centre, radius, pen):
    """Centre and radius so that the outer edges of a round shape fall on pixel edges."""
    outer = max(round_half_up(2 * radius + (pen or 0)), (pen or 0) + 1)
    new_radius = (outer - (pen or 0)) / 2
    offset = (outer / 2) % 1
    return snap_value(centre, offset), new_radius
