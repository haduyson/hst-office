# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư without UNO: CSV values (Vietnamese numbers, dd/mm/yyyy dates, leading zeros kept), sheet cells to a
recipient table, the stored document settings (damaged JSON ignored), the handler's status for the ribbon (record
label, greyed buttons) and the vi/en text tables."""
import os
import sys
import types
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_format as fmt
from hst_office import mail_merge_source as src
from hst_office import mail_merge_store as store
from hst_office import mail_merge_table as mt
from hst_office import mail_merge_texts as texts


class CsvValues(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(src.csv_cell("1500000"), ("number", 1500000.0))
        self.assertEqual(src.csv_cell("1.500.000"), ("number", 1500000.0))
        self.assertEqual(src.csv_cell("1.500"), ("number", 1500.0))
        self.assertEqual(src.csv_cell("1234,5"), ("number", 1234.5))
        self.assertEqual(src.csv_cell("1500.5"), ("number", 1500.5))
        self.assertEqual(src.csv_cell("-250"), ("number", -250.0))

    def test_leading_zero_and_long_codes_stay_text(self):
        self.assertEqual(src.csv_cell("0901234567"), ("text", "0901234567"))
        self.assertEqual(src.csv_cell("001234567890123456"), ("text", "001234567890123456"))
        self.assertEqual(src.csv_cell("1234567890123456"), ("text", "1234567890123456"))

    def test_dates_and_empty(self):
        self.assertEqual(src.csv_cell("07/03/1985"), ("date", 31113.0))
        self.assertEqual(src.csv_cell("7-3-1985"), ("date", 31113.0))
        self.assertEqual(src.csv_cell("31/02/2020"), ("text", "31/02/2020"))
        self.assertEqual(src.csv_cell("  "), ("", None))

    def test_windows_code_page_fallback(self):
        windows = "Ho\u0323 va\u0300 tên".encode("cp1258")  # tone marks as combining characters, like Windows
        self.assertEqual(src.decode_csv(windows), "Họ và tên")
        self.assertEqual(src.decode_csv("﻿Tên".encode("utf-8")), "Tên")


TEXT_KEY, DATE_KEY, GENERAL_KEY = 100, 37, 0


class _FakeFormats:
    def getByKey(self, key):  # noqa: N802 - UNO name
        return types.SimpleNamespace(Type={TEXT_KEY: src.TEXT_FLAG, DATE_KEY: src.DATE_FLAG}.get(key, 1))


class _FakeSheet:
    """The few XSpreadsheet calls sheet_grid makes: a used area from A1, one format range per column."""

    def __init__(self, rows, text_columns=(), date_columns=()):
        self.rows, self.text_columns, self.date_columns = rows, set(text_columns), set(date_columns)
        self.area = types.SimpleNamespace(StartColumn=0, StartRow=0, EndColumn=len(rows[0]) - 1, EndRow=len(rows) - 1)

    def createCursor(self):  # noqa: N802 - UNO name
        sheet = self
        return types.SimpleNamespace(gotoStartOfUsedArea=lambda _x: None, gotoEndOfUsedArea=lambda _x: None,
                                     RangeAddress=sheet.area, getDataArray=lambda: tuple(sheet.rows))

    def getCellRangeByPosition(self, *_area):  # noqa: N802 - UNO name
        parts = []
        for column in range(len(self.rows[0])):
            key = TEXT_KEY if column in self.text_columns else DATE_KEY if column in self.date_columns else GENERAL_KEY
            address = types.SimpleNamespace(StartColumn=column, EndColumn=column, StartRow=1, EndRow=len(self.rows) - 1)
            parts.append(types.SimpleNamespace(NumberFormat=key, RangeAddress=address))
        return types.SimpleNamespace(CellFormatRanges=types.SimpleNamespace(getCount=lambda: len(parts),
                                                                            getByIndex=parts.__getitem__))

    def getCellByPosition(self, column, row):  # noqa: N802 - UNO name
        value = self.rows[row][column]
        return types.SimpleNamespace(getString=lambda: value if isinstance(value, str) else "%g" % value)


class Grid(unittest.TestCase):
    def test_headers_kinds_and_mixed_columns(self):
        grid = [[("", None), ("", None), ("", None)],
                [("text", "Họ tên"), ("text", "Số"), ("", None)],
                [("text", "An"), ("number", 5.0), ("", None)],
                [("text", "Bình"), ("text", "chưa có"), ("", None)]]
        table = src.table_from_grid(grid)
        self.assertEqual(table.headers, ["Họ tên", "Số"])
        self.assertEqual(table.kinds, [fmt.COL_TEXT, fmt.COL_TEXT])
        self.assertEqual(table.rows, [("An", "5"), ("Bình", "chưa có")])

    def test_text_formatted_numbers_stay_text(self):
        """Years typed before the column was formatted as Text are numbers in a Text cell: merged as typed."""
        sheet = _FakeSheet([("CCCD", "Năm sinh", "Số tiền", "Ngày"),
                            ("001203004567", 2000.0, 1500000.0, 36526.0),
                            ("079199001234", 1999.0, 2500.0, 36527.0)],
                           text_columns={1}, date_columns={3})
        table = src.table_from_grid(src.sheet_grid(sheet, _FakeFormats()))
        self.assertEqual(table.kinds, [fmt.COL_TEXT, fmt.COL_TEXT, fmt.COL_NUMBER, fmt.COL_DATE])
        self.assertEqual([row[1] for row in table.rows], ["2000", "1999"])
        self.assertEqual(fmt.default_kind(table.kinds[1]), fmt.TEXT)
        self.assertEqual(fmt.default_kind(table.kinds[2], [r[2] for r in table.rows]), fmt.NUMBER)

    def test_header_only_is_empty(self):
        with self.assertRaises(src.SourceError) as caught:
            src.table_from_grid([[("text", "Họ tên")]])
        self.assertEqual(caught.exception.code, "empty")

    def test_csv_file(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mail_merge_list.csv")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("Họ và tên;Số tiền;Điện thoại\nNguyễn Văn An;1.500.000;0901234567\n")
        try:
            table = src.read_csv(path)
        finally:
            os.remove(path)
        self.assertEqual(table.kinds, [fmt.COL_TEXT, fmt.COL_NUMBER, fmt.COL_TEXT])
        self.assertEqual(table.rows[0], ("Nguyễn Văn An", 1500000.0, "0901234567"))


class Meta(unittest.TestCase):
    def test_defaults_and_damage(self):
        self.assertEqual(store.parse_meta("")["excluded"], [])
        self.assertEqual(store.parse_meta("{not json")["source"], "")
        meta = store.parse_meta('{"source": 5, "excluded": ["a", 3], "sheet": "Danh sách", "kinds": {"x": "date", "y": 1}}')
        self.assertEqual((meta["source"], meta["excluded"], meta["sheet"], meta["kinds"]), ("", ["a"], "Danh sách", {"x": "date"}))

    def test_source_name_has_no_space(self):
        self.assertNotIn(" ", store.source_name({"id": "ab12cd34"}))


class Status(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ("unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.frame", "com.sun.star.lang"):
            sys.modules.setdefault(name, types.ModuleType(name))
        sys.modules["unohelper"].Base = type("Base", (), {})
        for name in ("XDispatch", "XDispatchProvider"):
            setattr(sys.modules["com.sun.star.frame"], name, type(name, (), {}))
        for name in ("XInitialization", "XServiceInfo"):
            setattr(sys.modules["com.sun.star.lang"], name, type(name, (), {}))
        from hst_office import mail_merge_handler
        cls.handler = mail_merge_handler

    def session(self, source="x.csv", loaded=True, preview=False, position=0, excluded=()):
        table = mt.Table(["Tên"], [fmt.COL_TEXT], [("A",), ("B",), ("C",)]) if loaded else None
        session = types.SimpleNamespace(has_list=bool(source), table=table, preview=preview, position=position)
        session.checked = lambda: [i for i in range(3) if table.keys[i] not in excluded]
        return session

    def test_without_a_list_only_the_list_commands_work(self):
        session = self.session(source="", loaded=False)
        self.assertEqual(self.handler.status("Recipients", session), (True, None))
        self.assertEqual(self.handler.status("Finish", session), (False, None))
        self.assertEqual(self.handler.status("Record", session), (False, "Bản ghi"))
        self.assertEqual(self.handler.status("Next", None), (False, None))

    def test_record_label_and_ends(self):
        session = self.session(preview=True, position=2)
        self.assertEqual(self.handler.status("Record", session), (True, "Bản ghi 3 / 3"))
        self.assertEqual(self.handler.status("Record", session, "en"), (True, "Record 3 / 3"))
        self.assertFalse(self.handler.status("Next", session)[0])
        self.assertTrue(self.handler.status("Prev", session)[0])
        self.assertEqual(self.handler.status("Preview", session), (True, True))


class Texts(unittest.TestCase):
    def test_same_keys_and_no_trailing_ellipsis(self):
        self.assertEqual(set(texts.VI), set(texts.EN))
        for key, value in texts.VI.items():
            self.assertFalse(value.endswith(("…", "...")), key)
            self.assertEqual(value.count("%s") + value.count("%d"), texts.EN[key].count("%s") + texts.EN[key].count("%d"), key)

    def test_every_kind_has_a_label(self):
        for kinds in fmt.KINDS_FOR_COLUMN.values():
            for kind in kinds:
                self.assertIn("kind." + kind, texts.VI)


if __name__ == "__main__":
    unittest.main()
