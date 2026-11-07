# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon owner-draw palette (vcl HstRibbonPaint.cxx from hst-ribbon-paint.patch).

The colours are taken from the patch and checked against the ribbon panel colours of
docs/design/ribbon-look/PROPOSAL.md: the checked border, the tab accent and the separator must
be visible as UI parts (WCAG 1.4.11, 3:1 against the state fill or panel, separators excepted),
captions must be readable text (4.5:1), and pressed must be stronger than checked, which must be
stronger than the panel.
"""
import os
import re
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-paint.patch")
FIELDS = ("hover", "pressed", "checked", "checked_border", "separator", "caption", "tab_accent", "tab_hover")
PANEL = {"light": (0xFF, 0xFF, 0xFF), "dark": (0x1C, 0x2B, 0x3B)}


def patch_text():
    with open(PATCH, encoding="utf-8") as handle:
        return handle.read()


def palettes():
    """{"dark": {...}, "light": {...}} from the two Palette{...} literals of paletteFor()."""
    text = patch_text()
    body = text[text.index("+Palette paletteFor("):text.index("+bool ownerDrawAllowed(")]
    literals = re.findall(r"Palette\{(.*?)\};", body.replace("\n+", " "), re.S)
    if len(literals) != 2:
        raise AssertionError("expected a dark and a light palette")
    result = {}
    for name, literal in zip(("dark", "light"), literals):
        colours = [tuple(int(v, 16) for v in m) for m in re.findall(r"Color\(0x(\w\w), 0x(\w\w), 0x(\w\w)\)", literal)]
        if len(colours) != len(FIELDS):
            raise AssertionError(f"{name}: {len(colours)} colours")
        result[name] = dict(zip(FIELDS, colours))
    return result


def luminance(rgb):
    linear = [v / 255 for v in rgb]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in linear]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


class RibbonPaintPaletteTest(unittest.TestCase):
    def test_palettes_from_patch(self):
        found = palettes()
        self.assertEqual(found["light"]["tab_accent"], (0x00, 0x72, 0xBB))  # HST brand blue
        self.assertEqual(found["light"]["separator"], (0xDC, 0xE6, 0xF0))
        self.assertEqual(found["dark"]["checked"], (0x23, 0x47, 0x62))

    def test_contrast(self):
        for theme, colours in palettes().items():
            panel = PANEL[theme]
            with self.subTest(theme=theme):
                self.assertGreaterEqual(contrast(colours["caption"], panel), 4.5)
                self.assertGreaterEqual(contrast(colours["tab_accent"], panel), 3.0)
                self.assertGreaterEqual(contrast(colours["checked_border"], colours["checked"]), 3.0)
                self.assertGreater(contrast(colours["separator"], panel), 1.1)

    def test_state_strength(self):
        for theme, colours in palettes().items():
            panel = PANEL[theme]
            strength = {k: contrast(colours[k], panel) for k in ("hover", "checked", "pressed")}
            with self.subTest(theme=theme, strength=strength):
                self.assertGreater(strength["pressed"], strength["checked"])
                self.assertGreater(strength["checked"], 1.0)
                self.assertGreater(strength["hover"], 1.0)

    def test_scope_and_rollback(self):
        text = patch_text()
        self.assertIn("return !rStyle.GetHighContrastMode();", text)  # high contrast stays native
        self.assertIn("officecfg::Office::HSTRibbon::OwnerDraw::get()", text)
        self.assertIn("dynamic_cast<const NotebookbarTabControlBase*>(this)", text)  # notebookbar tabs only
        self.assertIn("if (mpData->mbHstOwnerDraw && !bIsWindow", text)  # marked toolboxes, controls native


if __name__ == "__main__":
    unittest.main()
