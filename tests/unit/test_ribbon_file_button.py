# SPDX-License-Identifier: AGPL-3.0-only
"""The ribbon's File button (hst-file-button-visibility.patch).

The File tab ("Tệp tin") is drawn as a filled button. The colours are taken from the patch: the
label must be readable text on every fill (WCAG 4.5:1), the resting fill must stand out from the
tab row (3:1), each state must be darker than the one before, and high contrast must use the
system colours.
"""
import os
import re
import unittest

from _paths import ROOT
from test_ribbon_paint_palette import contrast, luminance

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-file-button-visibility.patch")
WHITE = (0xFF, 0xFF, 0xFF)
# the tab row: the ribbon look's own colour and the plain GTK (Adwaita) one
TAB_ROW = {"light": ((0xF0, 0xF5, 0xFA), (0xF6, 0xF5, 0xF4)), "dark": ((0x16, 0x24, 0x35), (0x2B, 0x2B, 0x2B))}


def patch_text():
    with open(PATCH, encoding="utf-8") as handle:
        return handle.read()


def fills():
    """{"light": (rest, hover, pressed), "dark": (...)} from fileTabColorsFor()."""
    text = patch_text()
    body = text[text.index("+FileTabColors fileTabColorsFor("):text.index("+tools::Long FileTabExtraWidth(")]
    body = body.replace("\n+", " ")
    named = {name: tuple(int(v, 16) for v in rgb) for name, *rgb in
             re.findall(r"constexpr Color (\w+)\(0x(\w\w), 0x(\w\w), 0x(\w\w)\);", body)}

    def colour(token):
        match = re.fullmatch(r"Color\(0x(\w\w), 0x(\w\w), 0x(\w\w)\)", token.strip())
        return tuple(int(v, 16) for v in match.groups()) if match else named[token.strip()]

    found = re.findall(r"FileTabColors\{ bPressed \? (.+?) : bHover \? (.+?) : (.+?),\s+COL_WHITE \}", body)
    if len(found) != 2:
        raise AssertionError("expected a dark and a light set of fills")
    return {theme: (colour(rest), colour(hover), colour(pressed))
            for theme, (pressed, hover, rest) in zip(("dark", "light"), found)}


class RibbonFileButtonTest(unittest.TestCase):
    def test_brand_fill(self):
        self.assertEqual(fills()["light"][0], (0x00, 0x72, 0xBB))  # HST brand blue

    def test_label_is_readable(self):
        for theme, states in fills().items():
            for state, fill in zip(("rest", "hover", "pressed"), states):
                with self.subTest(theme=theme, state=state):
                    self.assertGreaterEqual(contrast(WHITE, fill), 4.5)

    def test_button_stands_out_from_the_tab_row(self):
        for theme, states in fills().items():
            for row in TAB_ROW[theme]:
                with self.subTest(theme=theme, row=row):
                    self.assertGreaterEqual(contrast(states[0], row), 3.0)

    def test_states_get_darker(self):
        for theme, (rest, hover, pressed) in fills().items():
            with self.subTest(theme=theme):
                self.assertGreater(luminance(rest), luminance(hover))
                self.assertGreater(luminance(hover), luminance(pressed))

    def test_scope(self):
        text = patch_text()
        # high contrast: the system selection colours, not the brand colours
        self.assertIn("return FileTabColors{ rStyle.GetHighlightColor(), rStyle.GetHighlightTextColor() };", text)
        # only the notebookbar's File tab, and off with the ribbon look's switch
        self.assertIn('FILE_TAB_NAME = u"FileLabel"_ustr;', text)
        self.assertIn("+                             && dynamic_cast<const NotebookbarTabControlBase*>(this)", text)
        self.assertEqual(text.count("hst::ribbon::ownerDrawEnabled()"), 3)  # one is context
        self.assertIn("aFont.SetWeight(WEIGHT_BOLD);", text)
        self.assertIn("rRenderContext.SetFont(aHstPlainFont);", text)  # the other tabs stay regular
        # the name is the one the File panel reacts to
        with open(os.path.join(PATCHES, "hst-file-backstage.patch"), encoding="utf-8") as handle:
            self.assertIn('pTabs->GetPageName(nPageId) != "FileLabel"', handle.read())

    def test_last_in_series(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            names = handle.read().split()
        self.assertIn("hst-file-button-visibility.patch", names)
        self.assertGreater(names.index("hst-file-button-visibility.patch"), names.index("hst-ribbon-tab-search.patch"))


if __name__ == "__main__":
    unittest.main()
