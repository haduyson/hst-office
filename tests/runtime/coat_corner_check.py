# SPDX-License-Identifier: AGPL-3.0-only
"""Checks the rounded corners of the HST coat in a screenshot, as the eye sees them.

Every control outlined in a coat border colour (light #6E7A8B, dark #8691A5) is found by its straight edges:
runs of that exact colour. Each corner between a horizontal and a vertical edge (all four corners, by turning the
image) is measured in "coverage": how much of the border colour a pixel holds over the light or dark surface
around it (0: none, 1: all). A smooth, solid corner has

- no notch: the pixel just before each straight edge begins carries the border nearly fully (a hairline arc, as
  Skia draws a one-pixel stroke, leaves it pale, and the corner reads as chipped);
- no gap: every row and every column of the corner holds some border (an opaque inner window painted over the
  arc cuts it);
- no bleed: nothing lighter or darker than the surface outside the arc (a fill shifted past the border).

    python3 coat_corner_check.py shot.png [shot2.png ...]      # prints each failing corner, exit 1 on any
"""
import re
import sys

from PIL import Image, ImageChops

BORDERS = ((0x6E, 0x7A, 0x8B), (0x86, 0x91, 0xA5))
MIN_EDGE = 12  # straight edge pixels, so text and glyphs are not taken for controls
MAX_RADIUS = 14  # corner box searched beyond the straight edge's end
NOTCH = 0.80
GAP = 0.45
BLEED = -0.03  # coverage below the bare surface: something other than the border was painted there


def luminance(rgb):
    r, g, b = rgb[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class View:
    """The image turned so that one of its corners is the top left one: (x, y) of the view -> pixel colour."""

    def __init__(self, image, flip_x, flip_y):
        self.flip_x, self.flip_y = flip_x, flip_y
        if flip_x:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if flip_y:
            image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.image = image
        self.px = image.load()
        self.w, self.h = image.size

    def __call__(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return None
        return self.px[x, y][:3]

    def image_xy(self, x, y):
        return (self.w - 1 - x if self.flip_x else x, self.h - 1 - y if self.flip_y else y)


def runs(view, border, horizontal):
    """Maximal straight runs of exactly the border colour, at least MIN_EDGE long: (fixed, start, end), end
    exclusive. A mask of the colour (0 where it matches) is searched row by row as bytes."""
    diff = ImageChops.difference(view.image, Image.new("RGB", view.image.size, border))
    r, g, b = diff.split()
    mask = ImageChops.add(ImageChops.add(r, g), b)
    if not horizontal:
        mask = mask.transpose(Image.Transpose.TRANSPOSE)
    width, height = mask.size
    data = mask.tobytes()
    pattern = re.compile(rb"\x00{%d,}" % MIN_EDGE)
    found = []
    for a in range(height):
        for m in pattern.finditer(data, a * width, (a + 1) * width):
            found.append((a, m.start() - a * width, m.end() - a * width))
    return found


def corners(view, border):
    """Top left corners of the view: (edge row y0, edge column x0, top edge start xs, left edge start ys)."""
    tops = [r for r in runs(view, border, True) if view(r[1] + MIN_EDGE // 2, r[0] - 1) != border]
    lefts = {}
    for x, start, end in runs(view, border, False):
        if view(x - 1, start + MIN_EDGE // 2) != border:
            lefts.setdefault(x, []).append(start)
    out = []
    for y0, xs, _ in tops:
        for x0 in range(max(0, xs - MAX_RADIUS), xs):
            for ys in lefts.get(x0, ()):
                # a round corner is as tall as it is wide
                if y0 < ys <= y0 + MAX_RADIUS and abs((ys - y0) - (xs - x0)) <= 1:
                    out.append((y0, x0, xs, ys))
    return out


def measure(view, border, corner):
    """The defects of one corner: a list of strings, empty when the corner is smooth and solid; None when this
    is not a rounded corner that can be measured."""
    y0, x0, xs, ys = corner
    surface = view(x0 - 2, ys + 2)  # outside the left edge, below the corner
    fill = view(x0 + 3, ys + 2)  # inside the left edge
    if surface is None or fill is None:
        return None
    if view(x0 - 2, y0) == border or view(x0, y0 - 2) == border:
        return None  # an edge runs on past the corner: the gap between two controls, not a corner
    if abs(luminance(fill) - luminance(surface)) > abs(luminance(surface) - luminance(border)) / 2:
        return None  # the inside is not a plain fill (a selection, an image): no reference to measure against
    ref = (luminance(surface) + luminance(fill)) / 2
    span = ref - luminance(border)
    if abs(span) < 20:
        return None

    def cover(x, y):
        rgb = view(x, y)
        return (ref - luminance(rgb)) / span if rgb else 0.0

    if cover(x0, y0) > 0.5:
        return None  # the corner pixel itself is border: two controls' edges meeting, not a rounded corner
    defects = []
    for name, value in (("top", cover(xs - 1, y0)), ("left", cover(x0, ys - 1))):
        if value < NOTCH:
            defects.append("notch at the %s edge's end (%.2f)" % (name, value))
    for j in range(y0, ys):
        if max(cover(x, j) for x in range(x0, xs)) < GAP:
            defects.append("gap in row %d" % (j - y0))
            break
    for i in range(x0, xs):
        if max(cover(i, y) for y in range(y0, ys)) < GAP:
            defects.append("gap in column %d" % (i - x0))
            break
    # outside the arc: from the corner's outer pixel inwards, until the border begins
    for j in range(y0, ys):
        for x in range(x0, xs):
            if cover(x, j) >= 0.25:
                break
            rgb = view(x, j)
            # anti-aliasing mixes the border into the surface; a fill mixes in from the other side
            if (luminance(surface) - luminance(rgb)) / (luminance(surface) - luminance(border)) < BLEED:
                defects.append("paint outside the arc at %d,%d #%02X%02X%02X" % ((x - x0, j - y0) + rgb))
                break
        else:
            continue
        break
    return defects


def check(path):
    """[(image x, image y, corner name, defects)] of every coat corner in the image at path."""
    image = Image.open(path).convert("RGB")
    results = []
    for flip_x, flip_y, name in ((False, False, "top left"), (True, False, "top right"),
                                 (False, True, "bottom left"), (True, True, "bottom right")):
        view = View(image, flip_x, flip_y)
        for border in BORDERS:
            for corner in corners(view, border):
                defects = measure(view, border, corner)
                if defects is not None:
                    x, y = view.image_xy(corner[1], corner[0])
                    results.append((x, y, name, defects))
    return results


def main(paths):
    failed = 0
    for path in paths:
        results = check(path)
        bad = [r for r in results if r[3]]
        print("%s: %d corners, %d defective" % (path, len(results), len(bad)))
        for x, y, name, defects in bad:
            print("  %s corner at %d,%d: %s" % (name, x, y, "; ".join(defects)))
        failed += len(bad)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
