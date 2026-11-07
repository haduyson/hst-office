# SPDX-License-Identifier: AGPL-3.0-only
"""Heavier 16 px ink of the colourful style: 1 px pens widen to 2 px only where the glyph has room."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_icon_snap as snap  # noqa: E402
import hst_icon_weight as weight  # noqa: E402


def native(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">'
            f'{body}</g></svg>')


def painted(svg):
    """Pixels covered by the shipped (outline) SVG, from the same pixel model as the rule."""
    from hst_svg_path import parse_path
    pixels = set()
    for data in re.findall(r' d="([^"]+)"', svg):
        pixels |= weight.fill_pixels(("path", parse_path(data)))
    return pixels


class WeightTest(unittest.TestCase):
    def test_a_free_standing_letter_gets_the_heavier_pen(self):
        u = native('<path d="M4.5 2.5V8.5A4 4 0 0 0 12.5 8.5V2.5" stroke-width="1"/>')
        light, heavy = snap.snap_svg(u, 16, native=True), snap.snap_svg(u, 16, native=True, heavy=True)
        self.assertGreater(len(painted(heavy)), len(painted(light)) * 1.6)

    def test_lines_one_pixel_apart_keep_their_gap(self):
        lines = native('<path d="M2.5 3.5H13.5M2.5 5.5H13.5M2.5 7.5H13.5" stroke-width="1"/>')
        self.assertEqual(snap.snap_svg(lines, 16, native=True, heavy=True), snap.snap_svg(lines, 16, native=True))

    def test_lines_two_pixels_apart_do_not_close_to_one(self):
        lines = native('<path d="M2.5 3.5H13.5M2.5 6.5H13.5" stroke-width="1"/>')
        rows = sorted({y for _, y in painted(snap.snap_svg(lines, 16, native=True, heavy=True))})
        gaps = [b - a - 1 for a, b in zip(rows, rows[1:]) if b - a > 1]
        self.assertTrue(all(gap >= 2 for gap in gaps), rows)

    def test_lines_drawn_as_separate_elements_keep_one_rhythm(self):
        # the outer line alone would have room to widen; the stack stays even instead
        lines = native('<path d="M2.5 2.5H14.5" stroke-width="1"/><path d="M4.5 6.5H12.5" stroke-width="1"/>'
                       '<path d="M2.5 9.5H14.5" stroke-width="1"/><path d="M4.5 12.5H12.5" stroke-width="1"/>')
        self.assertEqual(snap.snap_svg(lines, 16, native=True, heavy=True), snap.snap_svg(lines, 16, native=True))

    def test_a_small_counter_stays_open(self):
        box = native('<rect x="5.5" y="5.5" width="3" height="3" stroke-width="1"/>')
        self.assertIn((7, 7), set((x, y) for x in range(16) for y in range(16)) -
                      painted(snap.snap_svg(box, 16, native=True, heavy=True)))

    def test_widened_geometry_stays_on_the_pixel_grid(self):
        glyph = native('<path d="M3.5 2.5V13.5" stroke-width="1"/><rect x="6.5" y="3.5" width="6" height="6" stroke-width="1"/>')
        svg = snap.snap_svg(glyph, 16, native=True, heavy=True)
        self.assertGreater(len(painted(svg)), len(painted(snap.snap_svg(glyph, 16, native=True))))
        # straight edges (H/V/L to an axis-aligned neighbour) of the shipped outlines sit on whole pixels
        for data in re.findall(r' d="([^"]+)"', svg):
            points = [tuple(map(float, p)) for p in re.findall(r"[ML]([-\d.]+) ([-\d.]+)", data)]
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if x0 == x1 and abs(y1 - y0) >= 1:
                    self.assertEqual(x0 % 1, 0, data)
                if y0 == y1 and abs(x1 - x0) >= 1:
                    self.assertEqual(y0 % 1, 0, data)

    def test_colour_fills_stay_visible(self):
        swatch = native('<rect x="4" y="4" width="4" height="4" fill="#3478DA" stroke="none"/>'
                        '<rect x="3.5" y="3.5" width="5" height="5" stroke-width="1"/>')
        heavy = snap.snap_svg(swatch, 16, native=True, heavy=True)
        self.assertIn("#3478DA", heavy)
        fill = re.search(r'<path d="([^"]+)" fill="#3478DA"', heavy).group(1)
        from hst_svg_path import parse_path
        inside = weight.fill_pixels(("path", parse_path(fill)))
        ink = set()
        for data in re.findall(r'<path d="([^"]+)" fill="currentColor"', heavy):
            ink |= weight.fill_pixels(("path", parse_path(data)))
        self.assertGreaterEqual(len(inside - ink), len(inside) * 2 / 3 - 1e-9 if len(inside) > 9 else 1)

    def test_only_16_px_is_affected_and_output_is_deterministic(self):
        u = native('<path d="M4.5 2.5V12.5" stroke-width="1"/>')
        self.assertEqual(snap.snap_svg(u, 16, native=True, heavy=True), snap.snap_svg(u, 16, native=True, heavy=True))
        master = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
                  '<path d="M6 3v18" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" '
                  'stroke-linejoin="round"/></svg>')
        self.assertEqual(snap.snap_svg(master, 24, heavy=True), snap.snap_svg(master, 24))

    def test_a_straight_widened_line_is_a_solid_bar(self):
        line = native('<path d="M4.5 2.5V12.5" stroke-width="1"/>')
        heavy = snap.snap_svg(line, 16, native=True, heavy=True)
        cells = painted(heavy)
        self.assertEqual({x for x, _ in cells}, {4, 5})
        self.assertEqual({y for _, y in cells}, set(range(2, 14)))


if __name__ == "__main__":
    unittest.main()
