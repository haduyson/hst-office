# SPDX-License-Identifier: AGPL-3.0-only
"""The optical weight and sharpness check of the shipped HST icons (scripts/brand/check-hst-icon-weight.py)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_weight", ROOT / "scripts/brand/check-hst-icon-weight.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def svg(size, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">{body}</svg>'


def icon(size, stem, stroke, ink=None, fringe=0.1, overflow=0.0):
    ink = check.COLIBRE[size]["ink"] if ink is None else ink
    return {"size": size, "stem": stem, "stroke": stroke, "ink": ink, "fringe": fringe, "overflow": overflow}


def theme(large_stroke=1.0, extra=None):
    icons = {f"cmd/{size}/{n}.svg": icon(size, f"i{n}", 1.0 if size == 16 else large_stroke)
             for size in (16, 24, 32) for n in range(5)}
    icons.update(extra or {})
    return icons


class WeightCheckTest(unittest.TestCase):
    def test_a_pixel_aligned_1_px_line_measures_one_pixel_and_no_fringe(self):
        result = check.measure(svg(16, '<path d="M2 7H14V8H2Z" fill="#000000"/>'), 16, "#000000")
        self.assertAlmostEqual(result["stroke"], 12 / 13, places=2)
        self.assertEqual(result["fringe"], 0.0)
        self.assertEqual(result["overflow"], 0.0)

    def test_a_half_pixel_offset_line_is_all_fringe(self):
        result = check.measure(svg(16, '<path d="M2 7.5H14V8.5H2Z" fill="#000000"/>'), 16, "#000000")
        self.assertEqual(result["fringe"], 1.0)

    def test_holes_are_even_odd_and_other_colours_are_not_ink(self):
        ring = '<path d="M2 2H14V14H2ZM3 3V13H13V3Z" fill="#000000"/><path d="M5 5H11V11H5Z" fill="#FF0000"/>'
        result = check.measure(svg(16, ring), 16, "#000000")
        self.assertAlmostEqual(result["ink"], (144 - 100) / 256, places=3)

    def test_geometry_outside_the_canvas_is_reported(self):
        self.assertAlmostEqual(check.measure(svg(16, '<path d="M-1 7H14V8H-1Z" fill="#000000"/>'), 16,
                                             "#000000")["overflow"], 1.0)

    def test_large_icons_heavier_than_small_ones_fail(self):
        failures, _ = check.judge("t", theme(large_stroke=2.0))
        self.assertTrue(any("24 px: median stroke" in line for line in failures))
        self.assertEqual(check.judge("t", theme())[0], [])

    def test_a_set_much_lighter_or_darker_than_colibre_fails(self):
        icons = {name: dict(item, ink=item["ink"] * 1.6) for name, item in theme().items()}
        self.assertTrue(any("median ink" in line for line in check.judge("t", icons)[0]))

    def test_single_outliers_fail_and_heavy_on_purpose_icons_do_not(self):
        heavy = {"cmd/24/x.svg": icon(24, "x", 2.0), "cmd/24/bold.svg": icon(24, "bold", 3.0),
                 "cmd/32/dense.svg": icon(32, "dense", 1.0, ink=0.9), "cmd/16/blur.svg": icon(16, "blur", 1.0, fringe=0.9),
                 "cmd/16/clip.svg": icon(16, "clip", 1.0, overflow=0.5)}
        failures = check.judge("t", theme(extra=heavy))[0]
        for name in ("x.svg", "dense.svg", "blur.svg", "clip.svg"):
            self.assertTrue(any(name in line for line in failures), name)
        self.assertFalse(any("bold.svg" in line for line in failures))

    def test_the_shipped_hst_theme_passes(self):
        builder = check.load_builder()
        icons = check.measure_theme(builder.resources("hst"), builder.PALETTES["hst"])
        failures, medians = check.judge("hst", icons)
        self.assertEqual(failures, [])
        for size in (24, 32):
            self.assertLess(medians[size]["stroke"], 1.25)


if __name__ == "__main__":
    unittest.main()
