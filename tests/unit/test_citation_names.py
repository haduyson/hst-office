# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese and foreign names: parsing, initials, recognition and Vietnamese alphabetical order."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_names as names


class Parse(unittest.TestCase):
    def test_written_forms(self):
        cases = {
            "Smith, John A.": {"family": "Smith", "given": "John A."},
            "John A. Smith": {"family": "Smith", "given": "John A."},
            "Nguyễn Văn An": {"family": "Nguyễn", "given": "Văn An", "hst-vi": True},
            "Văn An Nguyễn": {"family": "Nguyễn", "given": "Văn An", "hst-vi": True},
            "Nguyễn, Văn An": {"family": "Nguyễn", "given": "Văn An", "hst-vi": True},
            "Nguyễn Thị Minh Khai": {"family": "Nguyễn", "given": "Thị Minh Khai", "hst-vi": True},
            "{World Health Organization}": {"literal": "World Health Organization"},
            "Bộ Giáo dục và Đào tạo": {"literal": "Bộ Giáo dục và Đào tạo"},
            "WHO": {"literal": "WHO"},
            "Ludwig van Beethoven": {"family": "Beethoven", "given": "Ludwig", "non-dropping-particle": "van"},
            "Smith, John, Jr.": {"family": "Smith", "given": "John", "suffix": "Jr."},
            "Plato": {"family": "Plato"},
        }
        for text, expected in cases.items():
            self.assertEqual(names.parse_name(text), expected, text)
        self.assertEqual(names.parse_name("Tổng cục Thống kê", organization=False),
                         {"family": "Tổng", "given": "cục Thống kê", "hst-vi": True})

    def test_vietnamese_recognition(self):
        self.assertTrue(names.has_vietnamese_marks("Phạm"))
        self.assertTrue(names.has_vietnamese_marks("Đỗ"))
        self.assertFalse(names.has_vietnamese_marks("Толстой Лев Николаевич"))  # й is a Cyrillic breve
        self.assertFalse(names.has_vietnamese_marks("Québec Hélène"))
        self.assertTrue(names.is_vietnamese({"family": "Lê", "given": "Hà"}))  # family name + accent
        self.assertFalse(names.is_vietnamese({"family": "Nguyen", "given": "Van An"}))  # no accents: as written
        self.assertFalse(names.is_vietnamese({"family": "Nguyễn", "given": "Văn", "hst-vi": False}))
        self.assertTrue(names.is_east_asian({"family": "鲁", "given": "迅"}))

    def test_initials(self):
        self.assertEqual(names.initials("John Ronald"), "J. R.")
        self.assertEqual(names.initials("John Ronald", space=False), "J.R.")
        self.assertEqual(names.initials("John Ronald", period=False), "JR")
        self.assertEqual(names.initials("Jean-Paul"), "J.-P.")
        self.assertEqual(names.initials("J.-P."), "J.-P.")
        self.assertEqual(names.initials("JA"), "J. A.")
        self.assertEqual(names.initials("Đức Anh", ascii_only=True), "D. A.")
        self.assertEqual(names.full_name({"family": "Nguyễn", "given": "Văn An", "hst-vi": True}), "Nguyễn Văn An")
        self.assertEqual(names.full_name({"family": "Smith", "given": "J.", "suffix": "Jr."}), "J. Smith, Jr.")


class Order(unittest.TestCase):
    def key(self, full, order="given"):
        return names.name_sort_key(names.parse_name(full), order)

    def test_vietnamese_by_given_name_in_alphabet_order(self):
        people = ["Trần Văn Đào", "Lê Văn Bình", "Phạm Thị Ân", "Nguyễn Văn An", "Hoàng Dũng"]
        ordered = sorted(people, key=self.key)
        self.assertEqual(ordered, ["Nguyễn Văn An", "Phạm Thị Ân", "Lê Văn Bình", "Hoàng Dũng", "Trần Văn Đào"])
        self.assertEqual(self.key("Nguyễn Thị Minh Khai")[0], names.collation_key("Khai"))

    def test_same_given_name_then_family_and_middle(self):
        ordered = sorted(["Trần Văn An", "Lê Thị An", "Lê Văn An"], key=self.key)
        self.assertEqual(ordered, ["Lê Thị An", "Lê Văn An", "Trần Văn An"])

    def test_family_first_order_reads_left_to_right(self):
        ordered = sorted(["Trần Văn An", "Lê Văn Bình"], key=lambda n: self.key(n, "family"))
        self.assertEqual(ordered, ["Lê Văn Bình", "Trần Văn An"])

    def test_organisation_sorts_by_first_word_and_other_scripts_last(self):
        keys = {"Bộ Giáo dục và Đào tạo": names.name_sort_key({"literal": "Bộ Giáo dục và Đào tạo"}),
                "Bình": self.key("Lê Văn Bình"), "Толстой": names.name_sort_key({"family": "Толстой"}),
                "Zola": names.name_sort_key({"family": "Zola"})}
        self.assertEqual(sorted(keys, key=keys.get), ["Bình", "Bộ Giáo dục và Đào tạo", "Zola", "Толстой"])
        self.assertEqual(names.search_text({"family": "Đặng", "given": "Thu Trang", "hst-vi": True}),
                         "dang thu trang")


if __name__ == "__main__":
    unittest.main()
