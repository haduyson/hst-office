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
        # Math would reach 24 below MathType's box: it moves up 24 mm100 (0.7 pt) and the line keeps the room
        self.assertEqual((113, 0, 57, 57), (new.TopMargin, new.BottomMargin, new.LeftMargin, new.RightMargin))
        self.assertEqual((formula_place.NONE, -517), (new.VertOrient, new.VertOrientPosition))
        self.assertEqual((-517, 623, 1294), formula_place.room(new))
        self.assertEqual(-380 - 24, new.VertOrientPosition + new.TopMargin)

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



class FitRoomTest(unittest.TestCase):
    def test_formula_higher_than_mathtype_is_drawn_smaller(self):
        # top 529 above the baseline in a room 635 high; Math reaches 580 above: 51 too high, 8.8 % smaller
        self.assertAlmostEqual(529 / 580, formula_place.fit_scale((-529, 635, 1224), (716, 620), 580))

    def test_arrow_label_higher_than_mathtype_is_drawn_smaller(self):
        # s011: "{t^o} xrightarrow {}" took 1224 x 635 with its top 529 above the baseline; Math reaches 607 above
        self.assertAlmostEqual(529 / 607, formula_place.fit_scale((-529, 635, 1224), (716, 607), 607))
        # s011: 15180 x 787, top 469 above the baseline (318 below); Math 797 high, baseline 570: 101 too high
        self.assertAlmostEqual(469 / 570, formula_place.fit_scale((-469, 787, 15180), (14185, 797), 570))

    def test_formula_lower_than_mathtype_is_drawn_smaller(self):
        # 100 below the baseline in a room 500 high; Math 508 high reaches 108 below: 7.4 % smaller
        self.assertAlmostEqual(100 / 108, formula_place.fit_scale((-400, 500, 800), (700, 400 + 108), 400))
        self.assertAlmostEqual(0.8, formula_place.fit_scale((-400, 500, 800), (700, 400 + 125), 400))  # 125 below

    def test_formula_a_little_beyond_the_room_moves_inside_it(self):
        # s041: "x" 388 x 459 centred, top 381 above the baseline (78 below); Math 450 high, baseline 360: 90 below,
        # 12 too low: it moves up 12 mm100 (0.3 pt) and keeps its size
        self.assertEqual(1.0, formula_place.fit_scale((-381, 459, 388), (286, 450), 360))
        values, top = formula_place.spacing((-381, 459, 388), (286, 450), 360)
        self.assertEqual((-381, 9, 0), (top, values["TopMargin"], values["BottomMargin"]))

    def test_fitting_formula_and_too_large_a_change_are_left_alone(self):
        self.assertEqual(1.0, formula_place.fit_scale((-529, 635, 1224), (716, 500), 400))
        self.assertEqual(1.0, formula_place.fit_scale((-439, 545, 1482), (818, 852), 852 - 1))  # 48 % off


if __name__ == "__main__":
    unittest.main()
