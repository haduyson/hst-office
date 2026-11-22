# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The Insert › Symbol drop-down starts with the symbols Word users pick every day (hst-symbol-defaults.patch).

The drop-down shows the favourite characters and the recent ones. Their defaults in Common.xcs must hold the check
boxes and ticks, arrows, math signs and the Vietnamese ₫ and №, as Unicode characters (never Wingdings code points),
each with a font that has the glyph on every platform, and leave room for the user's own favourites.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches" / "libreoffice" / "hst-symbol-defaults.patch"
SERIES = ROOT / "patches" / "libreoffice" / "series"

REQUIRED = "☐☑☒✓✗✔•→←↑↓⇒°±×÷≤≥≠≈∞€©₫№"
BOXES_AND_TICKS = "☐☑☒✓✔✗"
# Fonts HST can rely on: DejaVu Sans is bundled on every platform and has every symbol above; Times New Roman is
# HST Writer's default font (Liberation Serif, bundled, stands in where it is missing).
FONTS = {"DejaVu Sans", "Times New Roman"}
# DejaVu Sans only: Times New Roman and Liberation Serif have no ballot boxes, ticks or crosses.
NEEDS_DEJAVU = set(BOXES_AND_TICKS + "⇒")
# Glyphs of Windows' Times New Roman 7.03 (GlyphTypeface.CharacterToGlyphMap on a Windows 11 test PC); Liberation Serif,
# its stand-in on Linux, has the same ones. A symbol pinned to Times New Roman must be one of them.
TIMES_NEW_ROMAN_HAS = set("•→←↑↓°±×÷≤≥≠≈∞€©₫№")
FAVOURITE_LIMIT = 16  # SfxCharmapContainer keeps at most 16 favourites and 16 recent characters
RECENT_LIMIT = 16


def patched_values():
    """{prop name: [items]} for the string-list props the patch rewrites, read from the patch's new side."""
    new_side = "\n".join(line[1:] for line in PATCH.read_text(encoding="utf-8").splitlines()
                         if line[:1] in (" ", "+") and not line.startswith("+++"))
    values = {}
    for match in re.finditer(r'<prop oor:name="(\w+)"[^>]*>\s*<info>.*?</info>\s*<value>(.*?)</value>', new_side,
                             re.S):
        values[match.group(1)] = re.findall(r"<it>(.*?)</it>", match.group(2))
    return values


class SymbolDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = patched_values()
        cls.favourites = cls.values.get("FavoriteCharacterList", [])
        cls.favourite_fonts = cls.values.get("FavoriteCharacterFontList", [])
        cls.recent = cls.values.get("RecentCharacterList", [])
        cls.recent_fonts = cls.values.get("RecentCharacterFontList", [])

    def test_patch_is_in_the_series(self):
        self.assertIn("hst-symbol-defaults.patch", SERIES.read_text(encoding="utf-8").split())

    def test_drop_down_holds_the_required_symbols(self):
        shown = set(self.favourites + self.recent)
        self.assertEqual([c for c in REQUIRED if c not in shown], [])

    def test_check_boxes_and_ticks_are_favourites(self):
        # Favourites stay put; recent characters are pushed out by the user's own picks.
        self.assertEqual([c for c in BOXES_AND_TICKS if c not in self.favourites], [])

    def test_each_character_has_its_font(self):
        self.assertEqual(len(self.favourites), len(self.favourite_fonts))
        self.assertEqual(len(self.recent), len(self.recent_fonts))
        pairs = list(zip(self.favourites + self.recent, self.favourite_fonts + self.recent_fonts))
        self.assertEqual([font for _, font in pairs if font not in FONTS], [])
        self.assertEqual([c for c, font in pairs if c in NEEDS_DEJAVU and font != "DejaVu Sans"], [])
        self.assertEqual([c for c, font in pairs if font == "Times New Roman" and c not in TIMES_NEW_ROMAN_HAS], [])

    def test_unicode_characters_not_symbol_font_code_points(self):
        for char in self.favourites + self.recent:
            self.assertEqual(len(char), 1, char)
            self.assertFalse(0xF000 <= ord(char) <= 0xF0FF, f"U+{ord(char):04X} is a symbol-font code point")
            self.assertGreater(ord(char), 0x7F, char)

    def test_no_duplicates_and_room_for_own_favourites(self):
        both = self.favourites + self.recent
        self.assertEqual(len(both), len(set(both)))
        self.assertLess(len(self.favourites), FAVOURITE_LIMIT)  # "Add to Favourites" stays available
        self.assertLessEqual(len(self.recent), RECENT_LIMIT)


if __name__ == "__main__":
    unittest.main()
