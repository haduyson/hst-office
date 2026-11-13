# SPDX-License-Identifier: AGPL-3.0-only
"""Bibliography order: language groups, given-name or family-name sorting, first-citation order, year suffixes."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_bib_order as order
from hst_office import citation_style as styles


def item(item_id, author, year, title="T", language="vi"):
    people = [{"literal": author}] if author.startswith("Bộ") else [
        {"family": author.split()[0], "given": " ".join(author.split()[1:]), "hst-vi": True}
        if language == "vi" else {"family": author.split()[-1], "given": " ".join(author.split()[:-1])}]
    return {"id": item_id, "type": "book", "title": title, "language": language, "author": people,
            "issued": {"date-parts": [[year]]} if year else {}}


ITEMS = [item("smith", "John Smith", 2001, language="en"), item("dao", "Trần Văn Đào", 2005),
         item("an", "Nguyễn Văn An", 2010), item("bo", "Bộ Giáo dục và Đào tạo", 2009),
         item("binh", "Lê Bình", 2003), item("adams", "Ann Adams", 1999, language="en"),
         item("ru", "Лев Толстой", 1869, "Война и мир", "ru")]


def ids(arranged):
    return [[i["id"] for i in group] for _, group in arranged]


class Arrange(unittest.TestCase):
    def test_vietnamese_thesis_groups_and_given_name_order(self):
        arranged = order.arrange(ITEMS, styles.load_style("vn-so"), {})
        self.assertEqual([code for code, _ in arranged], ["vi", "en", "ru"])
        self.assertEqual(ids(arranged), [["an", "binh", "bo", "dao"], ["adams", "smith"], ["ru"]])
        self.assertEqual(order.numbers(arranged), {"an": 1, "binh": 2, "bo": 3, "dao": 4, "adams": 5, "smith": 6,
                                                   "ru": 7})

    def test_one_list_by_family_name(self):
        style = styles.load_style("vn-tac-gia-nam", preset="mot-danh-muc-theo-ho")
        self.assertEqual(ids(order.arrange(ITEMS, style, {})),
                         [["adams", "bo", "binh", "an", "smith", "dao", "ru"]])

    def test_citation_order(self):
        first = {"smith": 0, "an": 1, "ru": 2}
        arranged = order.arrange([i for i in ITEMS if i["id"] in first], styles.load_style("ieee"), first)
        self.assertEqual(ids(arranged), [["smith", "an", "ru"]])

    def test_year_suffixes_and_no_date_first(self):
        style = styles.load_style("apa-7")
        works = [item("b", "John Smith", 2001, "Beta", "en"), item("a", "John Smith", 2001, "Alpha", "en"),
                 item("n", "John Smith", None, "Undated", "en"), item("x", "Jane Smith", 2001, "Other", "en")]
        arranged = order.arrange(works, style, {})
        self.assertEqual(ids(arranged), [["x", "n", "a", "b"]])
        self.assertEqual(order.year_suffixes(arranged, style), {"x": "a", "a": "b", "b": "c"})  # same cite text
        self.assertEqual(order.year_suffixes(arranged, styles.load_style("ieee")), {})

    def test_mla_repeated_author(self):
        style = styles.load_style("mla-9")
        works = [item("a", "John Smith", 2001, "Alpha", "en"), item("b", "John Smith", 2002, "Beta", "en")]
        self.assertEqual(order.same_author_as_previous(order.arrange(works, style, {}), style), {"b"})


if __name__ == "__main__":
    unittest.main()
