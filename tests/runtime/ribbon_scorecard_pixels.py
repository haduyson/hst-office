# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel analysis of the ribbon scorecard (painting and gallery probes). Pure functions on PIL images and boxes.

A box is (x, y, width, height) in image coordinates. Thresholds are chosen so that anti-aliasing noise (a few levels)
never counts as a change and a theme fill (tens of levels) always does.
"""

DELTA = 24  # summed |ΔR|+|ΔG|+|ΔB| above which a pixel counts as changed


def _rgb(image):
    return image if image.mode == "RGB" else image.convert("RGB")


def clip(box, image):
    x, y, w, h = box
    x0, y0 = max(int(x), 0), max(int(y), 0)
    x1, y1 = min(int(x + w), image.width), min(int(y + h), image.height)
    return x0, y0, max(x1 - x0, 0), max(y1 - y0, 0)


def pixels(image, box):
    """[(x, y, (r, g, b))] inside the box."""
    image = _rgb(image)
    x0, y0, w, h = clip(box, image)
    px = image.load()
    return [(x, y, px[x, y]) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]


def changed(before, after, box):
    """Pixels of `after` that differ from `before` inside the box: [(x, y, colour)]."""
    before, after = _rgb(before), _rgb(after)
    pb = before.load()
    return [(x, y, c) for x, y, c in pixels(after, box) if sum(abs(a - b) for a, b in zip(c, pb[x, y])) > DELTA]


def dominant_share(colours, tolerance=12):
    """Share of the colours within `tolerance` (summed channel distance) of the most frequent one."""
    if not colours:
        return 0.0
    counts = {}
    for colour in colours:
        counts[colour] = counts.get(colour, 0) + 1
    mode = max(counts, key=counts.get)
    near = sum(n for colour, n in counts.items() if sum(abs(a - b) for a, b in zip(colour, mode)) <= tolerance)
    return near / len(colours)


def flat_fill(before, after, box, min_share=0.3, min_flat=0.5):
    """(ok, detail): a state fill appears in the box: enough pixels change and most changed pixels share one colour."""
    area = max(box[2] * box[3], 1)
    diff = changed(before, after, box)
    share = len(diff) / area
    flat = dominant_share([c for _x, _y, c in diff])
    return share >= min_share and flat >= min_flat, {"changed": round(share, 3), "flat": round(flat, 3)}


def ring(before, after, box, band=2):
    """(ok, detail): a focus ring: the border band of the box changes much more than its interior."""
    x, y, w, h = box
    diff = changed(before, after, box)
    if w <= 2 * band + 2 or h <= 2 * band + 2:
        return False, {"reason": "box too small"}
    border = [(px, py) for px, py, _c in diff if px < x + band or px >= x + w - band or py < y + band or py >= y + h - band]
    border_area = 2 * band * (w + h) - 4 * band * band
    inner_area = (w - 2 * band) * (h - 2 * band)
    border_share = len(border) / border_area
    inner_share = (len(diff) - len(border)) / inner_area
    return border_share >= 0.5 and inner_share < border_share / 2, {"border": round(border_share, 3), "inner": round(inner_share, 3)}


def background(image, box):
    """Most frequent colour in the box (the panel background)."""
    counts = {}
    for _x, _y, colour in pixels(image, box):
        counts[colour] = counts.get(colour, 0) + 1
    return max(counts, key=counts.get) if counts else (255, 255, 255)


def thin_separator(image, gap_box, min_cover=0.5):
    """(ok, detail): a vertical line at most 2 px thick in the gap between two groups, covering `min_cover` of its height.

    A thick one-sided border or no line at all fails."""
    image = _rgb(image)
    x0, y0, w, h = clip(gap_box, image)
    if w <= 0 or h <= 0:
        return False, {"reason": "empty gap"}
    bg = background(image, (x0, y0, w, h))
    px = image.load()
    lines = []
    for x in range(x0, x0 + w):
        cover = sum(sum(abs(a - b) for a, b in zip(px[x, y], bg)) > DELTA for y in range(y0, y0 + h)) / h
        lines.append(cover >= min_cover)
    runs, run = [], 0
    for is_line in lines + [False]:
        if is_line:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    return len(runs) == 1 and runs[0] <= 2, {"runs": runs}


def ink_box(image, box, bg=None):
    """Bounding box (x, y, w, h) of the pixels that differ from the background inside `box`, or None."""
    bg = bg or background(image, box)
    ink = [(x, y) for x, y, c in pixels(image, box) if sum(abs(a - b) for a, b in zip(c, bg)) > 3 * DELTA]
    if not ink:
        return None
    xs, ys = [p[0] for p in ink], [p[1] for p in ink]
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def centred(image, caption_box, group_box, tolerance=3):
    """(ok, detail): the caption text is centred under its group."""
    ink = ink_box(image, caption_box)
    if ink is None:
        return False, {"reason": "no caption ink"}
    offset = (ink[0] + ink[2] / 2) - (group_box[0] + group_box[2] / 2)
    return abs(offset) <= tolerance, {"offset": round(offset, 1)}


def underline(image, tab_box, below=6, min_cover=0.5, max_rows=4):
    """(ok, detail): an accent underline (saturated rows, at most `max_rows` thick: a line, not a block) at the bottom of the selected tab."""
    image = _rgb(image)
    x, y, w, h = tab_box
    px = image.load()
    rows = []
    for row in range(int(y + h - below), int(y + h + below)):
        if not 0 <= row < image.height:
            continue
        cols = [px[c, row] for c in range(max(int(x), 0), min(int(x + w), image.width))]
        cover = sum(max(c) - min(c) > 60 for c in cols) / max(len(cols), 1)
        if cover >= min_cover:
            rows.append(row)
    return 0 < len(rows) <= max_rows, {"rows": len(rows)}


def ink_runs(image, box, axis="y", gap=1, neutral=False):
    """Contiguous runs of rows (axis y) or columns (axis x) that hold ink, as (start, length).

    neutral=True counts only dark grey/black ink (text), not coloured borders."""
    image = _rgb(image)
    x0, y0, w, h = clip(box, image)
    bg = background(image, (x0, y0, w, h))
    px = image.load()

    def is_ink(colour):
        if neutral:
            return max(colour) - min(colour) < 40 and sum(colour) < 3 * 140
        return sum(abs(a - b) for a, b in zip(colour, bg)) > 3 * DELTA

    outer = range(y0, y0 + h) if axis == "y" else range(x0, x0 + w)
    inner = range(x0, x0 + w) if axis == "y" else range(y0, y0 + h)
    flags = [any(is_ink(px[i, o] if axis == "y" else px[o, i]) for i in inner) for o in outer]
    runs, start, blank = [], None, 0
    for index, flag in enumerate(flags + [False] * (gap + 1)):
        if flag:
            if start is None:
                start = index
            blank = 0
        elif start is not None:
            blank += 1
            if blank > gap:
                runs.append((outer.start + start, index - blank - start + 1))
                start, blank = None, 0
    return runs


def large_icon_with_label(image, button_box, min_icon=26):
    """(ok, detail): the button shows an icon at least `min_icon` px tall with a text label under it.

    Only the middle 60 % of the button is read, so a drop-down arrow at its side does not add to the icon."""
    x, y, w, h = button_box
    runs = ink_runs(image, (x + w // 5, y, w * 3 // 5, h), "y", gap=2)
    if not runs:
        return False, {"reason": "no ink"}
    icon = max(runs, key=lambda r: r[1])
    label = [r for r in runs if r[0] > icon[0] + icon[1]]
    return icon[1] >= min_icon and bool(label), {"icon_px": icon[1], "label": bool(label)}


def gallery_tiles(image, gallery_box):
    """Number of style previews side by side in the gallery: columns of text ink separated by 10 px or more."""
    return len(ink_runs(image, gallery_box, "x", gap=9, neutral=True))
