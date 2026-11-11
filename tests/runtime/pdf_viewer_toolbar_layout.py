# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF toolbar layout, shared by the Linux and the Windows checks.

HSTPdfInfo reports ToolbarLayout ("id x y width height preferredWidth preferredHeight" of each visible toolbar
control, relative to the toolbar) and ToolbarScreen (the toolbar's screen x, y, width, height). evaluate() finds:
  overlap  two controls whose rectangles intersect;
  clipped  a control narrower or lower than it asks to be, or reaching past the toolbar's right edge;
  ghost    a gap between two neighbouring controls that is not plain background in the screenshot (luma rows from
           png_luma.read): stale copies of moved controls, as the Windows dark appearance left before the fix.
A separator line in a gap is one column and is allowed; the stale copies the dark appearance left measured 3-4.
"""
GHOST_COLUMNS = 2  # more columns than a separator line (one column) that differ from the gap's background
GHOST_LUMA = 24


def parse(layout):
    controls = []
    for item in layout:
        name, *numbers = item.split()
        x, y, w, h, pw, ph = (int(n) for n in numbers)
        controls.append({"id": name, "x": x, "y": y, "w": w, "h": h, "pw": pw, "ph": ph})
    return sorted(controls, key=lambda c: c["x"])


def _gap_ghost_columns(luma, left, right, top, bottom):
    """Columns in [left, right) x [top, bottom) whose pixels differ from the gap's median luma in 30% of the rows."""
    if right - left < 1 or bottom - top < 1:
        return 0
    values = sorted(luma[y][x] for y in range(top, bottom) for x in range(left, right))
    background = values[len(values) // 2]
    count = 0
    for x in range(left, right):
        off = sum(abs(luma[y][x] - background) > GHOST_LUMA for y in range(top, bottom))
        if off >= 0.3 * (bottom - top):
            count += 1
    return count


def evaluate(layout, screen, luma=None):
    """{"overlap": [...], "clipped": [...], "ghost": [...], "ok": bool} for the reported layout and a screenshot."""
    controls = parse(layout)
    sx, sy, sw, sh = screen
    overlap, clipped, ghost = [], [], []
    for i, a in enumerate(controls):
        for b in controls[i + 1:]:
            if a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]:
                overlap.append((a["id"], b["id"]))
        if a["w"] < a["pw"] - 1 or a["h"] < a["ph"] - 1 or a["x"] + a["w"] > sw or a["x"] < 0:
            clipped.append((a["id"], a["w"], a["pw"], a["h"], a["ph"]))
    if luma is not None:
        top, bottom = sy + sh // 4, sy + sh * 3 // 4
        for a, b in zip(controls, controls[1:]):
            left, right = sx + a["x"] + a["w"] + 2, sx + b["x"] - 2
            columns = _gap_ghost_columns(luma, max(0, left), min(len(luma[0]), right), max(0, top), min(len(luma), bottom))
            if columns > GHOST_COLUMNS:
                ghost.append((a["id"], b["id"], columns))
    return {"overlap": overlap, "clipped": clipped, "ghost": ghost, "controls": len(controls),
            "ok": bool(controls) and not overlap and not clipped and not ghost}
