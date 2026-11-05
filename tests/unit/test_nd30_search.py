# SPDX-License-Identifier: AGPL-3.0-only
"""Quick Search of the wizard: same folding as the feature search, grouped rows, keyboard moves skip the headings."""
import unittest

import _paths  # noqa: F401
from hst_office import nd30, nd30_search as search

GROUPS = {"hanh-chinh": "Hành chính", "qppl": "Quy phạm pháp luật", "dang": "Đảng", "van-thu": "Biểu mẫu văn thư"}
TYPES = nd30.rules()["documentTypes"]


class Search(unittest.TestCase):
    def first(self, query):
        return search.matches(TYPES, query)[0]["id"]

    def test_fold(self):
        self.assertEqual(search.fold("Đề án"), "de an")
        self.assertEqual(search.fold("Quyết định"), search.fold("Quyết định"))

    def test_keywords(self):
        for query, wanted in (("cong van", "cong-van"), ("công văn", "cong-van"), ("ke hoach", "ke-hoach"), ("gm", "giay-moi"), ("giấy mời", "giay-moi"), ("TTr", "to-trinh"),
                              ("QĐ", "quyet-dinh"), ("thong tu", "thong-tu"), ("so di", "so-van-ban-di"), ("so den", "so-van-ban-den"), ("sao y", "sao-y"), ("ctr", "chuong-trinh")):
            self.assertEqual(self.first(query), wanted, query)

    def test_empty_query_lists_all_grouped(self):
        rows = search.rows(TYPES, "", GROUPS)
        self.assertEqual(sum(1 for r in rows if r[1]), len(TYPES))
        self.assertEqual([r[0].strip("─ ") for r in rows if not r[1]], list(GROUPS.values()))

    def test_no_match(self):
        self.assertEqual(search.rows(TYPES, "khongcoloainay", GROUPS), [])

    def test_keyboard_skips_headings(self):
        rows = search.rows(TYPES, "cong van", GROUPS)
        first = search.next_row(rows, -1, 1)
        self.assertEqual(first, 1)
        second = search.next_row(rows, first, 1)
        self.assertEqual(rows[second][1], "dang-cong-van")
        self.assertEqual(search.next_row(rows, second, 1), second)
        self.assertEqual(search.next_row(rows, first, -1), first)


if __name__ == "__main__":
    unittest.main()
