# SPDX-License-Identifier: AGPL-3.0-only
"""The colourful HST style: delivery contract, recolouring and classic substitution."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_modern_icons as modern  # noqa: E402

spec = importlib.util.spec_from_file_location("hst_theme", ROOT / "scripts/brand/build-hst-icon-theme.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

COLOURS = {"#3478DA": "#75A7FF", "#D85650": "#FF8E80"}
GOOD = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SPDX-License-Identifier: CC-BY-4.0; Copyright 2026 HASON TECH -->
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <title>HST paste</title><desc>Clipboard.</desc>
  <path d="M5 5h14v16H5z" fill="#3478DA" stroke="none"/>
  <g fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">
    <path d="M8 5H5v16h14V5h-3"/>
  </g>
</svg>
"""


class ModernIconsTest(unittest.TestCase):
    def test_a_master_in_the_delivery_format_passes(self):
        self.assertEqual(modern.violations(GOOD, COLOURS), [])

    def test_each_rule_is_reported(self):
        cases = {
            '<linearGradient id="g"/>': "forbidden element",
            '<path d="M1 1h2" fill="#123456"/>': "palette light value",
            '<path d="M1 1h2" stroke="currentColor" stroke-linecap="butt"/>': "round caps",
            '<path d="M1 1h2" class="x"/>': "not allowed",
            '<g transform="skewX(10)"><path d="M1 1h2"/></g>': "transform",
        }
        for body, message in cases.items():
            text = GOOD.replace("</svg>", body + "</svg>")
            self.assertTrue(any(message in p for p in modern.violations(text, COLOURS)), body)
        self.assertTrue(modern.violations(GOOD.replace('viewBox="0 0 24 24"', 'viewBox="0 0 32 32"'), COLOURS))
        self.assertTrue(modern.violations(GOOD.replace("SPDX-License-Identifier: CC-BY-4.0", "SPDX"), COLOURS))
        self.assertEqual(modern.violations("<svg", COLOURS)[0][:20], "not well-formed XML:")

    def test_dark_theme_swaps_palette_values_only(self):
        svg = '<path fill="#3478da"/><path fill="#294159"/>'
        self.assertEqual(modern.recolour(svg, COLOURS, False), svg)
        self.assertEqual(modern.recolour(svg, COLOURS, True), '<path fill="#75A7FF"/><path fill="#294159"/>')

    def test_modern_themes_are_complete_and_missing_masters_are_listed(self):
        builder.MISSING_MODERN.clear()
        files = builder.resources("hst_modern_dark")
        classic = builder.resources("hst_dark")
        self.assertEqual(set(files), set(classic))  # same requests: no command loses its icon
        drawn = sorted(p.stem for p in (modern.MODERN / "glyphs/stage-1").glob("*.svg"))
        for name in drawn:
            self.assertNotIn(name, builder.MISSING_MODERN)
        if drawn:
            colours = modern.palette()
            svg = files[builder.svg_key(builder.sized(f"cmd/{drawn[0]}.png", 24))].decode()
            self.assertFalse(any(light in svg.upper() for light, dark in colours.items() if light != dark
                                 and light not in colours.values()), "light palette values left in dark theme")
        self.assertEqual(builder.MISSING_MODERN, set())  # every master drawn: the release gate passes

    def test_every_theme_takes_colibres_ink_from_the_build_token(self):
        ink = modern.ink()
        self.assertEqual((ink["light"], ink["dark"]), ("#3A3A38", "#FAFAFA"))  # Colibre's outline ink
        for theme in builder.FULL_THEMES:
            self.assertEqual(builder.PALETTES[theme], ink["dark" if theme.endswith("_dark") else "light"])
        light = builder.resources("hst_modern")[builder.svg_key(builder.sized("cmd/underline.png", 16))].decode()
        self.assertIn(ink["light"], light)
        self.assertNotIn("currentColor", light)

    def test_colours_are_colibres_pale_fills_and_accent_lines(self):
        svg = '<g fill="#3478DA"><path stroke="#3478DA"/><rect data-state="x" fill="#D85650"/><path fill="#929499"/></g>'
        self.assertEqual(modern.harmonise(svg, False),
                         '<g fill="#83BEEC"><path stroke="#1E8BCD"/><rect data-state="x" fill="#ED3D3B"/><path fill="#FAFAFA"/></g>')
        self.assertIn('<path fill="none"/>', modern.harmonise(svg, True))  # dark Colibre leaves its paper unpainted

    def test_ink_contrast_against_the_ribbon(self):
        def luminance(colour):
            channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(a, b):
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + 0.05) / (low + 0.05)
        ink = modern.ink()
        # at least as strong as the classic ink on the light and the dark ribbon
        self.assertGreaterEqual(contrast(ink["light"], "#FFFFFF"), contrast(builder.PALETTES["hst"], "#FFFFFF"))
        self.assertGreaterEqual(contrast(ink["dark"], "#1C2B3B"), contrast(builder.PALETTES["hst_dark"], "#1C2B3B"))

    def test_hand_tuned_modern_masters_follow_the_spec_at_their_size(self):
        for path in sorted((modern.MODERN / "glyphs").glob("stage-1-16/*.svg")):
            self.assertEqual(modern.violations(path.read_text(encoding="utf-8"), modern.palette(), 16, tuned=True), [],
                             path.name)
        bad = GOOD.replace('width="24" height="24" viewBox="0 0 24 24"', 'width="16" height="16" viewBox="0 0 16 16"')
        bad = bad.replace('stroke-width="1.65"', 'stroke-width="1.5"')
        self.assertTrue(any("does not snap" in p for p in modern.violations(bad, COLOURS, 16, tuned=True)))


if __name__ == "__main__":
    unittest.main()
