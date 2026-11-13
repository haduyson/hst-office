# SPDX-License-Identifier: AGPL-3.0-only
"""The "sửa tên Việt" step: inverted Vietnamese names, capitals, missing language — suggested, applied on accept."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_vn_fix as vn_fix

ITEM = {"id": "a", "title": "NHÌN LẠI HAI NĂM PHÁT TRIỂN LÚA LAI", "author": [
    {"family": "Hòa", "given": "Quản Minh"},           # Crossref
    {"family": "Lê Thị", "given": "Ngọc Thương"},       # VJOL
    {"literal": "Ngọc Thương Lê Thị"},                  # VJOL, one string
    {"family": "Nguyễn", "given": "Văn An", "hst-vi": True},
    {"family": "Lê", "given": "Hà"},
    {"family": "Smith", "given": "John"},
    {"literal": "Bộ Giáo dục và Đào tạo"}]}


class Suggestions(unittest.TestCase):
    def test_suggestions(self):
        found = vn_fix.suggest([ITEM])
        names = [(s["kind"], s["index"]) for s in found if s["field"] == "author"]
        self.assertEqual(names, [("name-order", 0), ("name-order", 1), ("name-order", 2), ("mark-vi", 4)])
        self.assertEqual(found[0]["new"], {"family": "Quản", "given": "Minh Hòa", "hst-vi": True})
        self.assertEqual(found[1]["new"], {"family": "Lê", "given": "Thị Ngọc Thương", "hst-vi": True})
        title = next(s for s in found if s["kind"] == "sentence-case")
        self.assertEqual(title["new"], "Nhìn lại hai năm phát triển lúa lai")
        self.assertEqual(next(s for s in found if s["kind"] == "language")["new"], "vi")

    def test_apply_only_accepted(self):
        found = vn_fix.suggest([ITEM])
        fixed = vn_fix.apply([ITEM], [found[0], {"item": "other", "field": "title", "index": None, "new": "x"}])[0]
        self.assertEqual(fixed["author"][0], {"family": "Quản", "given": "Minh Hòa", "hst-vi": True})
        self.assertEqual(fixed["author"][1], ITEM["author"][1])
        self.assertEqual(fixed["title"], ITEM["title"])
        self.assertEqual(ITEM["author"][0], {"family": "Hòa", "given": "Quản Minh"})  # input untouched
        self.assertEqual(vn_fix.vietnamese_order(["Smith", "John"]), None)


if __name__ == "__main__":
    unittest.main()
