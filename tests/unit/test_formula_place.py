# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: a converted formula takes the room its MathType equation took in the line."""
import unittest

import _paths  # noqa: F401

from hst_office import formula_place

AT_PARAGRAPH = "AT_PARAGRAPH"


class Enum:
    """A UNO enum as Python sees it."""
    def __init__(self, value):
        self.value = value


class Size:
    def __init__(self, width, height):
        self.Width, self.Height = width, height


class Frame:
    """A Writer object's frame: size, spacing, vertical orientation and position, anchor."""
    def __init__(self, width, height, orient=0, position=0, anchor=formula_place.AS_CHARACTER, **spacing):
        self.Size, self.AnchorType = Size(width, height), Enum(anchor)
        self.VertOrient, self.VertOrientPosition = orient, position
        for name in formula_place.SPACING:
            setattr(self, name, spacing.get(name, 0))

    def setPropertyValue(self, name, value):
        setattr(self, name, value)


class KeepRoomTest(unittest.TestCase):
    def test_formula_fills_the_equation_room_on_the_baseline(self):
        # s037: MathType 1295 x 623 mm100, its top 517 above the baseline; Math 1180 x 510, baseline 380 below its top
        old = Frame(1295, 623, position=-517)
        new = Frame(1180, 510)
        formula_place.keep_room(new, old, 380)
        self.assertEqual((137, 0, 57, 57), (new.TopMargin, new.BottomMargin, new.LeftMargin, new.RightMargin))
        self.assertEqual((formula_place.NONE, -517), (new.VertOrient, new.VertOrientPosition))
        # the line keeps the equation's top; Math reaches 24 lower than MathType's box, which is not cut
        self.assertEqual((-517, 647, 1294), formula_place.room(new))
        self.assertEqual(-380, new.VertOrientPosition + new.TopMargin)  # formula baseline on the text baseline

    def test_room_of_an_equation_with_its_bottom_on_the_baseline(self):
        old = Frame(800, 500, orient=1, position=0)  # never laid out: bottom on the baseline
        self.assertEqual((-500, 500, 800), formula_place.room(old))

    def test_room_where_the_layout_put_a_centred_equation(self):
        # s035.doc: Equation 3.0 centred on the characters (CHAR_CENTER); the layout wrote its top back
        old = Frame(1411, 706, orient=5, position=-531)
        self.assertEqual((-531, 706, 1411), formula_place.room(old))
        new = Frame(1259, 522)
        formula_place.keep_room(new, old, 406)
        self.assertEqual((125, 59, 76), (new.TopMargin, new.BottomMargin, new.LeftMargin))
        self.assertEqual(-531, new.VertOrientPosition)

    def test_larger_formula_is_not_cut(self):
        values, top = formula_place.spacing((-400, 500, 800), (900, 700), 600)
        self.assertEqual({"TopMargin": 0, "BottomMargin": 0, "LeftMargin": 0, "RightMargin": 0}, values)
        self.assertEqual(-600, top)

    def test_formula_not_in_a_line_has_no_spacing(self):
        new = Frame(1180, 510, anchor=AT_PARAGRAPH, TopMargin=300)
        formula_place.keep_room(new, Frame(1295, 623), 380)
        self.assertEqual(0, new.TopMargin)


if __name__ == "__main__":
    unittest.main()
