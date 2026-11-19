# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows contextual keep-tab check: its reading of the MSAA tab row and the objects it covers."""
import importlib.util
import os
import sys
import unittest
from unittest import mock

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
sys.path.insert(0, RUNTIME)


def load():
    spec = importlib.util.spec_from_file_location("keep_tab", os.path.join(RUNTIME, "check-windows-contextual-keep-tab.py"))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"windows_gui": mock.MagicMock()}):
        spec.loader.exec_module(module)
    return module


class KeepTabTest(unittest.TestCase):
    keep = load()

    def test_parse_tabs_reads_names_and_the_selected_state(self):
        text = "noise\nTABS Trang đầu[0x0] | Ảnh [x][0x2] | Chèn[0x100002]\nSMALL BUTTONS a[1,0x0]\n"
        self.assertEqual(self.keep.parse_tabs(text), [("Trang đầu", False), ("Ảnh [x]", True), ("Chèn", True)])

    def test_parse_tabs_without_a_tab_row(self):
        self.assertEqual(self.keep.parse_tabs("NOTFOUND\n"), [])

    def test_covers_picture_table_shape_everywhere_and_the_chart_in_sheets(self):
        for app in ("writer", "impress", "draw"):
            self.assertEqual(set(self.keep.KINDS[app]), {"picture", "table", "shape"})
        self.assertEqual(set(self.keep.KINDS["calc"]), {"pivot", "table", "picture", "shape", "chart"})
        self.assertEqual(self.keep.KINDS["calc"][:2], ("pivot", "table"))
        self.assertEqual(self.keep.command_for("calc", "table"), ".uno:Bold")
        self.assertEqual(self.keep.command_for("writer", "table"), ".uno:InsertRowsAfter")
        self.assertTrue(all(kind in self.keep.COMMANDS for kinds in self.keep.KINDS.values() for kind in kinds))

    def test_calc_table_is_a_database_range_with_a_table_style(self):
        doc = mock.MagicMock()
        table = mock.MagicMock()
        table.CellRangeAddress = mock.MagicMock
        with mock.patch.dict(sys.modules, {"com": mock.MagicMock(), "com.sun": mock.MagicMock(),
                                           "com.sun.star": mock.MagicMock(), "com.sun.star.table": table}):
            cell = self.keep.make_calc_table(doc)
        name, area = doc.DatabaseRanges.addNewByName.call_args.args
        self.assertEqual((area.StartColumn, area.EndColumn, area.EndRow), (10, 11, 3))
        doc.DatabaseRanges.getByName.assert_called_once_with(name)
        doc.DatabaseRanges.getByName.return_value.setPropertyValue.assert_called_once_with(
            "TableStyleName", "TableStyleMedium2")
        self.assertIs(cell, doc.Sheets.getByIndex.return_value.getCellByPosition.return_value)

    def test_park_gets_a_dispatch_that_waits(self):
        office = mock.MagicMock()
        self.keep._Dispatcher(office).dispatch("frame", ".uno:Escape")
        office.dispatch_async.assert_called_once_with("frame", ".uno:Escape")
        office.dispatch_async.return_value.join.assert_called_once_with(30)


if __name__ == "__main__":
    unittest.main()
