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


if __name__ == "__main__":
    unittest.main()
