# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: a converted MathType equation keeps the size Word shows it at."""
import unittest

import _paths  # noqa: F401

from hst_office import formula_size

TWIP = 9  # com.sun.star.embed.EmbedMapUnits.TWIP


class FakeSize:
    def __init__(self, width, height):
        self.Width, self.Height = width, height


class FakeFormula:
    """A new formula (model and embedded object at once): its MathType text and its visible area in twips."""
    def __init__(self, formula, height_twip, width_twip=395):
        self.Formula, self.height, self.width = formula, height_twip, width_twip

    def getVisualAreaSize(self, aspect):
        return FakeSize(self.width, self.height)

    def getMapUnit(self, aspect):
        return TWIP


class ScaleSizesTest(unittest.TestCase):
    def test_sizes_scaled_outside_quoted_text(self):
        self.assertEqual("size *0.6 { size 7.2{em} rSup { size 4.8{2} } {}}",
                         formula_size.scale_sizes(" size 12{em} rSup { size 8{2} } {}", 0.6))
        self.assertEqual('size *1.5 {"size 12" size 18 {x}}', formula_size.scale_sizes('"size 12" size 12 {x}', 1.5))

    def test_relative_sizes_and_other_words_left_alone(self):
        self.assertEqual("size *2 {size *1.5 {x} + fontsize}", formula_size.scale_sizes("size *1.5 {x} + fontsize", 2))


class ShownSizeTest(unittest.TestCase):
    def test_visible_area_in_twips_becomes_mm100(self):
        size = formula_size.visual_size(FakeFormula("x", 304, 395))
        self.assertEqual((697, 536), (size.Width, size.Height))

    def test_equation_resized_in_word_keeps_its_shown_size(self):
        # 304 twips = 536 mm100 at MathType's size; Word shows the equation at 60 % (316 mm100)
        formula = FakeFormula(" size 12{em} rSup { size 8{2} } {}", 304)
        self.assertAlmostEqual(0.59, formula_size.keep_shown_size(formula, formula, 316), places=2)
        self.assertTrue(formula.Formula.startswith("size *0.59 { size 7.1{em}"), formula.Formula)

    def test_equation_at_its_own_size_is_left_alone(self):
        formula = FakeFormula(" size 12{em}", 304)
        self.assertEqual(1.0, formula_size.keep_shown_size(formula, formula, 527))  # 2 % off: MathType's size
        self.assertEqual(1.0, formula_size.keep_shown_size(formula, formula, 0))  # size unknown
        self.assertEqual(" size 12{em}", formula.Formula)


if __name__ == "__main__":
    unittest.main()
