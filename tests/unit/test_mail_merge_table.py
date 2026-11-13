# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư recipient list: headers, column kinds, stable row keys, Vietnamese sorting and search, the checked
recipients, file names from a pattern and the staging rows the engine merges from."""
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_format as fmt
from hst_office import mail_merge_table as mt

HEADERS = ["Họ và tên", "Số tiền", "Ngày sinh", "Điện thoại"]
KINDS = [fmt.COL_TEXT, fmt.COL_NUMBER, fmt.COL_DATE, fmt.COL_TEXT]
ROWS = [("Nguyễn Văn An", 1500000.0, 31113.0, "0901234567"),
        ("Trần Thị Bích Ngọc", 12345678.0, 33928.0, "0901234568"),
        ("Lê Hoàng Ánh", 250000.0, 28857.0, "0901234569"),
        ("Phạm Đức Đạt", 9800000.0, None, "0901234570")]


def table():
    return mt.Table(HEADERS, KINDS, ROWS)


class Headers(unittest.TestCase):
    def test_empty_and_repeated_headers_get_column_names(self):
        self.assertEqual(mt.clean_headers([" Họ  và tên ", "", "Họ và tên", mt.FILE_COLUMN]),
                         ["Họ và tên", "Cột 2", "Cột 3", "Cột 4"])

    def test_column_kinds(self):
        cells = [["text", "text"], ["number", "", "number"], ["date"], ["number", "text"], ["", ""]]
        self.assertEqual(mt.column_kinds(cells), ["text", "number", "date", "text", "text"])


class Keys(unittest.TestCase):
    def test_identical_rows_get_distinct_keys(self):
        keys = mt.row_keys([("a",), ("a",), ("b",)])
        self.assertEqual(len(set(keys)), 3)
        self.assertEqual(keys[0][:12], keys[1][:12])

    def test_keys_do_not_depend_on_position(self):
        self.assertEqual(mt.row_keys([("x",), ("y",)])[1], mt.row_keys([("y",)])[0])


class Order(unittest.TestCase):
    def test_by_given_name_vietnamese(self):
        names = [ROWS[i][0] for i in mt.order(table(), mt.SORT_GIVEN_NAME)]
        self.assertEqual(names, ["Nguyễn Văn An", "Lê Hoàng Ánh", "Phạm Đức Đạt", "Trần Thị Bích Ngọc"])

    def test_by_number_column_descending_and_file_order(self):
        self.assertEqual(mt.order(table(), "Số tiền", descending=True), [1, 3, 0, 2])
        self.assertEqual(mt.order(table()), [0, 1, 2, 3])

    def test_empty_dates_sort_last(self):
        self.assertEqual(mt.order(table(), "Ngày sinh")[-1], 3)

    def test_given_name_without_a_name_column_keeps_file_order(self):
        other = mt.Table(["Mã"], [fmt.COL_TEXT], [("b",), ("a",)])
        self.assertEqual(mt.order(other, mt.SORT_GIVEN_NAME), [0, 1])


class Search(unittest.TestCase):
    def test_without_diacritics_and_case(self):
        t = table()
        self.assertEqual([r[0] for r in t.rows if mt.matches(t, r, "NGOC")], ["Trần Thị Bích Ngọc"])
        self.assertTrue(mt.matches(t, t.rows[0], "1.500.000"))
        self.assertTrue(mt.matches(t, t.rows[0], "  "))

    def test_checked_excludes_keys(self):
        t = table()
        self.assertEqual(mt.checked_indexes(t, [t.keys[2]], mt.SORT_GIVEN_NAME), [0, 3, 1])


class FileNames(unittest.TestCase):
    def test_pattern_with_columns_and_formats(self):
        t = table()
        self.assertEqual(mt.file_name("Giấy mời - {Họ và tên} - {Ngày sinh}", t, t.rows[0]),
                         "Giấy mời - Nguyễn Văn An - 07-03-1985")
        self.assertEqual(mt.file_name("{Không có}", t, t.rows[0]), "{Không có}")
        self.assertEqual(mt.file_name(' a/b:c*? ', t, t.rows[0]), "a-b-c-")
        self.assertEqual(mt.file_name("", t, t.rows[0]), "Văn bản")
        self.assertEqual(mt.pattern_columns("x {A} {B}"), ["A", "B"])

    def test_unique_names(self):
        self.assertEqual(mt.unique_names(["A", "a", "B", "A"]), ["A", "a (2)", "B", "A (3)"])


class Staging(unittest.TestCase):
    def test_rows_words_and_file_name(self):
        t = table()
        headers, kinds, rows = mt.staging(t, [2, 0], "Phiếu lương - {Họ và tên}")
        self.assertEqual(headers[4:], ["Số tiền (bằng chữ)", "Số tiền (tiền bằng chữ)", mt.FILE_COLUMN])
        self.assertEqual(len(kinds), len(headers))
        self.assertEqual(rows[0][0], "Lê Hoàng Ánh")
        self.assertEqual(rows[0][3], "0901234569")
        self.assertEqual(rows[1][5], "Một triệu năm trăm nghìn đồng chẵn")
        self.assertEqual(rows[1][-1], "Phiếu lương - Nguyễn Văn An")


if __name__ == "__main__":
    unittest.main()
