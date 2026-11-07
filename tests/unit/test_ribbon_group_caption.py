# SPDX-License-Identifier: AGPL-3.0-only
"""Group captions versus key tips (is_group_caption in tests/runtime/ribbon_scorecard_live.py).

The key-tip check treats short capital labels as tips; a one-letter group caption such as Sheets' "Ô" must not count.
Fake accessibility nodes stand in for AT-SPI, so this needs no office and no display.
"""
import os
import sys
import unittest

from _paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
try:
    import pyatspi
    import ribbon_scorecard_live as live
except ImportError:  # pragma: no cover - pyatspi is part of the GUI test tool set
    pyatspi = None


class Box:
    def __init__(self, x, y, width, height):
        self.x, self.y, self.width, self.height = x, y, width, height


class Relation:
    def __init__(self, kind):
        self.kind = kind

    def getRelationType(self):  # noqa: N802 - AT-SPI name
        return self.kind


class Node:
    def __init__(self, role, box, children=(), relations=()):
        self.role, self.box, self.children, self.relations, self.parent = role, Box(*box), list(children), relations, None
        for child in self.children:
            child.parent = self

    childCount = property(lambda self: len(self.children))  # noqa: N815 - AT-SPI name

    def getChildAtIndex(self, index):  # noqa: N802
        return self.children[index]

    def getRoleName(self):  # noqa: N802
        return self.role

    def getRelationSet(self):  # noqa: N802
        return [Relation(kind) for kind in self.relations]

    def queryComponent(self):  # noqa: N802
        return self

    def getExtents(self, _coords):  # noqa: N802
        return self.box


def extents(node):
    box = node.box
    return box.x, box.y, box.width, box.height


@unittest.skipIf(pyatspi is None, "pyatspi is not installed")
class GroupCaptionTest(unittest.TestCase):
    def group(self, caption_box):
        caption = Node("label", caption_box)
        Node("panel", (100, 60, 120, 100), [Node("tool bar", (100, 60, 120, 60)), caption])
        return caption

    def test_bottom_row_caption_without_relation(self):
        caption = self.group((100, 140, 120, 18))
        self.assertTrue(live.is_group_caption(caption, extents(caption)))

    def test_caption_with_label_for_relation(self):
        caption = Node("label", (0, 0, 10, 10), relations=(pyatspi.RELATION_LABEL_FOR,))
        Node("filler", (0, 0, 10, 10), [caption])
        self.assertTrue(live.is_group_caption(caption, extents(caption)))

    def test_key_tip_over_a_button_is_not_a_caption(self):
        tip = self.group((130, 90, 16, 18))
        self.assertFalse(live.is_group_caption(tip, extents(tip)))

    def test_key_tip_on_the_bar_is_not_a_caption(self):
        tip = Node("label", (130, 30, 16, 18))
        Node("panel", (0, 0, 1485, 182), [Node("page tab list", (0, 0, 1485, 30)), tip])
        self.assertFalse(live.is_group_caption(tip, extents(tip)))


if __name__ == "__main__":
    unittest.main()
