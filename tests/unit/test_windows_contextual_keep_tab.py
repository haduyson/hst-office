# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows contextual keep-tab check: its reading of the MSAA tab row and the objects it covers."""
import importlib.util
import os
import sys
import tempfile
import threading
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

    def test_parse_rects_keeps_the_shown_ribbon_tabs_left_to_right(self):
        text = ("RECT 120 40 60 24 Chèn\nRECT 0 0 0 0 Định dạng ảnh\nRECT 50 40 60 24 Trang đầu\n"
                "RECT 30 900 80 20 Trang tính 1\nnoise\n")
        self.assertEqual(self.keep.parse_rects(text), ["Trang đầu", "Chèn"])

    def test_every_object_expects_its_office_named_tabs(self):
        self.assertEqual(self.keep.EXPECTED["table"], ("Thiết kế bảng", "Bố trí bảng"))
        self.assertTrue(all(kind in self.keep.EXPECTED for kinds in self.keep.KINDS.values() for kind in kinds))

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

    def test_a_held_close_is_recorded_and_our_processes_end(self):
        office, res = mock.MagicMock(), mock.MagicMock()
        office.stop.side_effect = lambda: threading.Event().wait(5)
        processes = mock.MagicMock()
        shot = os.path.join(tempfile.mkdtemp(), "shot.png")
        with mock.patch.dict(sys.modules, {"windows_gui_processes": processes}), \
                mock.patch.object(self.keep, "msaa", return_value="WINDOW 1 9:Lưu thay đổi?[0x0]"):
            self.keep.stop_office(office, shot, res, "impress", timeout=0.1)
        with open(shot[:-4] + ".txt", encoding="utf-8") as handle:
            self.assertIn("Lưu thay đổi?", handle.read())
        self.assertIn("Lưu thay đổi?", res.call_args.args[2])
        office.proc.kill.assert_called_once_with()
        processes.terminate.assert_called_once_with(office.url)
        self.assertFalse(res.call_args.args[1])

    def test_a_clean_close_records_nothing(self):
        office, res = mock.MagicMock(), mock.MagicMock()
        self.keep.stop_office(office, "shot.png", res, "writer", timeout=5)
        office.proc.kill.assert_not_called()
        res.assert_not_called()

    def test_a_held_command_is_recorded_with_what_holds_it(self):
        office, res, doc = mock.MagicMock(), mock.MagicMock(), mock.MagicMock()
        office.dispatch_async.return_value.is_alive.return_value = True
        args = mock.MagicMock(out=tempfile.mkdtemp())
        states = iter([[("Trang đầu", True)], [("Trang đầu", False), ("Định dạng ảnh", False)],
                       [("Trang đầu", False), ("Định dạng ảnh", True)], [("Trang đầu", False), ("Định dạng ảnh", True)]])
        with mock.patch.object(self.keep, "ribbon_tabs", side_effect=lambda _office: next(states)), \
                mock.patch.object(self.keep, "select_tab"), mock.patch.object(self.keep, "park"), \
                mock.patch.object(self.keep, "SETTLE", 0), \
                mock.patch.object(self.keep, "msaa", return_value="WINDOW 7 9:Chèn hàng[0x0]"):
            self.keep.check_kind("impress", "picture", doc, {"picture": "obj"}, "frame", office, res, args)
        held = [c.args for c in res.call_args_list if "returned" in c.args[0]]
        self.assertEqual(len(held), 1)
        self.assertFalse(held[0][1])
        self.assertIn("Chèn hàng", held[0][2])
        self.assertTrue(res.call_args_list[-1].args[0].endswith("still selected after .uno:GraphicFilterInvert"))

    def test_park_gets_a_dispatch_that_waits(self):
        office = mock.MagicMock()
        self.keep._Dispatcher(office).dispatch("frame", ".uno:Escape")
        office.dispatch_async.assert_called_once_with("frame", ".uno:Escape")
        office.dispatch_async.return_value.join.assert_called_once_with(30)


if __name__ == "__main__":
    unittest.main()
