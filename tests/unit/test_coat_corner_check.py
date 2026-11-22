# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The coat corner check (tests/runtime/coat_corner_check.py) on drawn corners: a smooth anti-aliased ring passes;
the three defects seen in Windows screenshots fail: a pale hairline arc with notches, a gap cut by an opaque inner
window, and a fill shifted past the border."""
import math
import os
import sys
import tempfile
import unittest

from PIL import Image

import _paths  # noqa: F401

sys.path.insert(0, os.path.join(_paths.ROOT, "tests", "runtime"))
import coat_corner_check as ccc  # noqa: E402

BORDER = (0x6E, 0x7A, 0x8B)
SURFACE = (0xF0, 0xF0, 0xF0)
FILL = (0xF5, 0xF8, 0xFC)
W, H, R = 90, 30, 6.0
LEFT, TOP = 10, 10


def inside(x, y, l, t, r, b, rad):
    if x < l or x > r or y < t or y > b:
        return False
    cx = min(max(x, l + rad), r - rad)
    cy = min(max(y, t + rad), b - rad)
    return math.hypot(x - cx, y - cy) <= rad


def mix(a, b, f):
    return tuple(round(p * (1 - f) + q * f) for p, q in zip(a, b))


def draw(ring_strength=1.0, gap=False, bleed=0.0):
    """A button of W x H at (LEFT, TOP): area coverage by 8 x 8 supersampling. ring_strength < 1 pales the arc
    (as a hairline does), gap paints an opaque fill rectangle one pixel inside the border, bleed moves the fill."""
    image = Image.new("RGB", (W + 2 * LEFT, H + 2 * TOP), SURFACE)
    px = image.load()
    n = 8
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            fill = ring = 0
            for sy in range(n):
                for sx in range(n):
                    fx, fy = x + (sx + 0.5) / n - LEFT, y + (sy + 0.5) / n - TOP
                    if inside(fx - bleed, fy - bleed, 0.5, 0.5, W - 0.5, H - 0.5, R - 0.5):
                        fill += 1
                    if inside(fx, fy, 0, 0, W, H, R) and not inside(fx, fy, 1, 1, W - 1, H - 1, R - 1):
                        ring += 1
            fill, ring = fill / n / n, ring / n / n
            straight = R <= x - LEFT < W - R or R <= y - TOP < H - R
            if not straight:
                ring *= ring_strength
            colour = mix(mix(SURFACE, FILL, fill), BORDER, ring)
            px[x, y] = colour
    if gap:
        for y in range(TOP + 1, TOP + H - 1):
            for x in range(LEFT + 1, LEFT + W - 1):
                px[x, y] = FILL
    return image


class CornerCheckTests(unittest.TestCase):
    def run_check(self, image):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shot.png")
            image.save(path)
            return ccc.check(path)

    def test_a_smooth_ring_passes(self):
        results = self.run_check(draw())
        self.assertEqual(len(results), 4)
        self.assertEqual([r for r in results if r[3]], [])

    def test_a_pale_arc_is_a_notch(self):
        results = self.run_check(draw(ring_strength=0.74))
        self.assertEqual(len(results), 4)
        self.assertTrue(all(any("notch" in d for d in r[3]) for r in results))

    def test_an_opaque_inner_window_cuts_a_gap(self):
        results = self.run_check(draw(gap=True))
        self.assertEqual(len(results), 4)
        self.assertTrue(all(any("gap" in d for d in r[3]) for r in results))

    def test_a_shifted_fill_shows_outside_the_arc(self):
        results = {r[2]: r[3] for r in self.run_check(draw(bleed=1.5))}
        self.assertTrue(any("outside the arc" in d for d in results["bottom right"]))


if __name__ == "__main__":
    unittest.main()
