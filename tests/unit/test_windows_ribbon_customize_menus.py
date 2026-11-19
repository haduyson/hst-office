# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows customize-menus check: how it finds the "Tùy chỉnh ribbon" entry of the context menus."""
import importlib.util
import os
import sys
import unittest
from unittest import mock

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
sys.path.insert(0, RUNTIME)


def load():
    spec = importlib.util.spec_from_file_location("customize_menus",
                                                  os.path.join(RUNTIME, "check-windows-ribbon-customize-menus.py"))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"windows_gui": mock.MagicMock()}):
        spec.loader.exec_module(module)
    return module


class MenuEntryTest(unittest.TestCase):
    menus = load()

    def test_the_entry_with_its_ellipsis_matches(self):
        self.assertTrue(self.menus.entry_matches("Tùy chỉnh ribbon…", self.menus.DIALOG))

    def test_the_plain_label_matches(self):
        self.assertTrue(self.menus.entry_matches("Tùy chỉnh ribbon", self.menus.DIALOG))

    def test_other_entries_do_not_match(self):
        self.assertFalse(self.menus.entry_matches("Thêm vào thanh truy cập nhanh", self.menus.DIALOG))
        self.assertFalse(self.menus.entry_matches("", self.menus.DIALOG))
        self.assertFalse(self.menus.entry_matches(None, self.menus.DIALOG))


class _Context:
    def __init__(self, role, name, children=()):
        self.role, self.name, self.children = role, name, list(children)

    def getAccessibleRole(self):
        return self.role

    def getAccessibleName(self):
        return self.name

    def getAccessibleChildCount(self):
        return len(self.children)

    def getAccessibleChild(self, index):
        return mock.Mock(getAccessibleContext=mock.Mock(return_value=self.children[index]))


class RibbonTabsTest(unittest.TestCase):
    """The dialog's tabs are the top-level rows of the tree named "Tùy chỉnh ribbon:", as VCL exposes them."""
    menus = load()
    TREE, LABEL, CHECK = 65, 27, 2

    def walk_of(self, *contexts):
        return lambda _dialog: iter([(c, 0) for c in contexts])

    def test_tab_rows_are_read_from_the_ribbon_tree(self):
        groups = [_Context(self.CHECK, "Bảng tạm", [_Context(self.CHECK, "Dán")])]
        ribbon = _Context(self.TREE, "Tùy chỉnh ribbon:", [_Context(self.LABEL, "Trang đầu", groups),
                                                           _Context(self.LABEL, "Chèn")])
        commands = _Context(self.TREE, "Lệnh", [_Context(self.LABEL, ".uno:AboveSpacing")])
        with mock.patch.object(self.menus.wg, "walk", self.walk_of(commands, ribbon)):
            self.assertEqual(self.menus.ribbon_tabs(object(), self.TREE), ["Trang đầu", "Chèn"])

    def test_no_ribbon_tree_gives_no_tabs(self):
        commands = _Context(self.TREE, "Lệnh", [_Context(self.LABEL, "Trang đầu")])
        with mock.patch.object(self.menus.wg, "walk", self.walk_of(commands)):
            self.assertEqual(self.menus.ribbon_tabs(object(), self.TREE), [])


if __name__ == "__main__":
    unittest.main()
