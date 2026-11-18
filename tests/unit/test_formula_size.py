# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: a converted MathType equation keeps the size Word shows it at."""
import unittest

import _paths  # noqa: F401

from hst_office import formula_size

TWIP, MM100 = 9, 0  # com.sun.star.embed.EmbedMapUnits


class FakeSize:
    def __init__(self, width, height):
        self.Width, self.Height = width, height


class FakeEmbedded:
    """An OLE object's own size: twips like a formula, mm100 like a .doc equation, or none (.docx, .rtf)."""
    def __init__(self, height, unit=TWIP):
        self.height, self.unit = height, unit

    def getVisualAreaSize(self, aspect):
        if self.height is None:
            raise RuntimeError("NoVisualAreaSizeException")
        return FakeSize(395, self.height)

    def getMapUnit(self, aspect):
        return self.unit


class FakeGraphic:
    def __init__(self, height):
        self.height = height

    def getPropertyValue(self, name):
        return FakeSize(1406, self.height)


class FakeEquation:
    """The OLE equation Word shows at shown mm100: its own size and its preview picture are at MathType's 100 %."""
    def __init__(self, shown, own=None, preview=None):
        self.Size, self.EmbeddedObject = FakeSize(0, shown), FakeEmbedded(own, MM100)
        if preview is not None:
            self.ReplacementGraphic = FakeGraphic(preview)


class FakeModel:
    def __init__(self, formula):
        self.Formula = formula


class ScaleSizesTest(unittest.TestCase):
    def test_sizes_scaled_outside_quoted_text(self):
        self.assertEqual("size *0.6 { size 7.2{em} rSup { size 4.8{2} } {}}",
                         formula_size.scale_sizes(" size 12{em} rSup { size 8{2} } {}", 0.6))
        self.assertEqual('size *1.5 {"size 12" size 18 {x}}', formula_size.scale_sizes('"size 12" size 12 {x}', 1.5))

    def test_relative_sizes_and_other_words_left_alone(self):
        self.assertEqual("size *2 {size *1.5 {x} + fontsize}", formula_size.scale_sizes("size *1.5 {x} + fontsize", 2))


class WordScaleTest(unittest.TestCase):
    def test_visible_area_in_twips_becomes_mm100(self):
        size = formula_size.visual_size(FakeEmbedded(304))
        self.assertEqual((697, 536), (size.Width, size.Height))

    def test_equation_resized_in_word_keeps_its_scale(self):
        # .rtf/.docx: no own size, preview picture 528 mm100; Word shows the equation at 60 % (316 mm100)
        model = FakeModel(" size 12{em} rSup { size 8{2} } {}")
        self.assertAlmostEqual(0.6, formula_size.keep_word_scale(model, FakeEquation(316, preview=528)), places=2)
        self.assertEqual("size *0.598 { size 7.2{em} rSup { size 4.8{2} } {}}", model.Formula)
        # .doc: the object's own size is MathType's (670 mm100), shown at 131 %
        model = FakeModel(" size 12{x}")
        self.assertAlmostEqual(1.31, formula_size.keep_word_scale(model, FakeEquation(878, own=670)), places=2)

    def test_equation_at_100_percent_is_left_alone(self):
        # MathType's box (706) is taller than Math's (522) at the same point size: not a resize
        model = FakeModel(" size 12{em}")
        self.assertEqual(1.0, formula_size.keep_word_scale(model, FakeEquation(706, own=706)))
        self.assertEqual(1.0, formula_size.keep_word_scale(model, FakeEquation(316)))  # scale unknown
        self.assertEqual(" size 12{em}", model.Formula)


if __name__ == "__main__":
    unittest.main()
