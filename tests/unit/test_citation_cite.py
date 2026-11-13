# SPDX-License-Identifier: AGPL-3.0-only
"""In-text clusters: number ranges, one bracket per number, superscript, locators, author–year collapsing."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_cite as cite
from hst_office import citation_engine as engine
from hst_office import citation_runs as runs
from hst_office import citation_style as styles

NUMBERS = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 7, "f": 9}


def numeric(style_id, cites, preset=None, **opts):
    return runs.to_markup(cite.numeric_cluster(cites, NUMBERS, styles.load_style(style_id, opts, preset)))


def ids(*names):
    return [{"id": n} for n in names]


class Numeric(unittest.TestCase):
    def test_vietnamese_one_bracket_per_number(self):
        """Học viện Tài chính 2022: [19], [25], [41]; numbers ascending, no ranges."""
        self.assertEqual(numeric("vn-so", ids("e", "a", "b", "c", "d", "f")), "[1], [2], [3], [4], [7], [9]")
        self.assertEqual(numeric("vn-so", [{"id": "c", "locator": "314-315"}]), "[3, tr. 314–315]")
        self.assertEqual(numeric("vn-so", [{"id": "c", "locator": "12"}, {"id": "a"}]), "[1], [3, tr. 12]")
        self.assertEqual(numeric("vn-so", [{"id": "zzz"}]), "[?]")

    def test_vietnamese_combined_preset(self):
        self.assertEqual(numeric("vn-so", ids("e", "a", "b", "c", "d", "f"), "gop-ngoac"), "[1–4, 7, 9]")
        self.assertEqual(numeric("vn-so", ids("a", "b"), "gop-ngoac"), "[1, 2]")
        self.assertEqual(numeric("vn-so", [{"id": "c", "locator": "12"}, {"id": "a"}], "gop-ngoac"), "[1; 3, tr. 12]")

    def test_variants(self):
        self.assertEqual(numeric("vn-so", ids("f", "a", "e"), "khong-nhom"), "[1], [7], [9]")
        self.assertEqual(numeric("vn-so", [{"id": "c", "locator": "314-315"}], "thu-tu-trich"), "[3, 314–315]")
        self.assertEqual(numeric("ieee", ids("a", "b", "c", "e")), "[1]–[3], [7]")
        self.assertEqual(numeric("ama-11", ids("a", "b", "c", "e")), "^1-3,7^")
        self.assertEqual(numeric("ama-11", [{"id": "a", "locator": "34", "label": "page"}], language="en"), "^1(p34)^")
        self.assertEqual(numeric("vancouver", ids("a", "c"), brackets="()"), "(1, 3)")
        self.assertEqual(numeric("vn-so", [{"id": "a", "locator": "2", "label": "chapter", "prefix": "xem "}]),
                         "[xem 1, chương 2]")

    def test_locator_text(self):
        opts = styles.load_style("apa-7", {"language": "en"}).options
        self.assertEqual(cite.locator_text(opts, "5"), "p. 5")
        self.assertEqual(cite.locator_text(opts, "5-7"), "pp. 5–7")
        self.assertEqual(cite.locator_text(opts, "3", "figure"), "fig. 3")
        self.assertEqual(cite.locator_text(opts, "3", "unknown-label"), "p. 3")
        self.assertEqual(cite.locator_text(opts, ""), "")


ITEMS = {
    "an": {"id": "an", "type": "book", "title": "Kinh tế", "language": "vi", "issued": {"date-parts": [[2010]]},
           "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}]},
    "two": {"id": "two", "type": "article-journal", "title": "X", "issued": {"date-parts": [[2009]]},
            "author": [{"family": "Lê", "given": "Văn B", "hst-vi": True}, {"family": "Trần", "given": "Thị C",
                                                                           "hst-vi": True}]},
    "many": {"id": "many", "type": "article-journal", "title": "Growth", "language": "en",
             "issued": {"date-parts": [[2006]]}, "author": [{"family": f} for f in ("Romer", "Doe", "Roe")]},
    "s19": {"id": "s19", "title": "A", "language": "en", "issued": {"date-parts": [[2019]]},
            "author": [{"family": "Smith", "given": "J."}]},
    "s20": {"id": "s20", "title": "B", "language": "en", "issued": {"date-parts": [[2020]]},
            "author": [{"family": "Smith", "given": "J."}]},
    "anon": {"id": "anon", "type": "report", "title": "Báo cáo thường niên: 2020", "language": "vi"},
}


def author_date(style_id, cites, narrative=False, preset=None, **opts):
    style = styles.load_style(style_id, opts, preset)
    return runs.to_markup(cite.author_date_cluster(cites, ITEMS, {}, style, narrative))


class AuthorDate(unittest.TestCase):
    def test_vietnamese_author_year(self):
        self.assertEqual(author_date("vn-tac-gia-nam", ids("an", "two", "many")),
                         "(Nguyễn Văn An, 2010; Lê Văn B & Trần Thị C, 2009; Romer & cộng sự, 2006)")
        self.assertEqual(author_date("vn-tac-gia-nam", [{"id": "an", "locator": "17-21"}]),
                         "(Nguyễn Văn An, 2010, tr. 17–21)")
        self.assertEqual(author_date("vn-tac-gia-nam", ids("an"), narrative=True), "Nguyễn Văn An (2010)")
        self.assertEqual(author_date("vn-tac-gia-nam", ids("an"), preset="et-al"), "(Nguyễn Văn An, 2010)")
        self.assertEqual(author_date("vn-tac-gia-nam", ids("many"), preset="et-al"), "(Romer et al., 2006)")

    def test_apa_sorting_collapsing_and_flags(self):
        self.assertEqual(author_date("apa-7", ids("s20", "many", "s19"), language="en"),
                         "(Romer et al., 2006; Smith, 2019, 2020)")
        self.assertEqual(author_date("apa-7", [{"id": "s19", "suppressAuthor": True}]), "(2019)")
        self.assertEqual(author_date("apa-7", [{"id": "s19", "authorOnly": True}]), "Smith")
        self.assertEqual(author_date("apa-7", ids("anon"), language="en"), "(*Báo cáo thường niên*, n.d.)")
        self.assertEqual(author_date("apa-7", ids("anon")), "(*Báo cáo thường niên*, không năm)")
        self.assertEqual(author_date("apa-7", ids("an"), preset="dao-ten-viet"), "(An, 2010)")

    def test_chicago_mla_harvard(self):
        self.assertEqual(author_date("chicago-tac-gia-nam", [{"id": "s19", "locator": "15"}]), "(Smith 2019, 15)")
        self.assertEqual(author_date("mla-9", [{"id": "s19", "locator": "15"}]), "(Smith 15)")
        self.assertEqual(author_date("mla-9", ids("many")), "(Romer và cộng sự)")  # Vietnamese document
        self.assertEqual(author_date("mla-9", ids("many"), language="en"), "(Romer et al.)")
        self.assertEqual(author_date("harvard", ids("many"), language="en"), "(Romer, Doe and Roe, 2006)")
        self.assertEqual(author_date("apa-7", ids("missing")), "(?)")

    def test_apa_initials_for_shared_family_names(self):
        """APA 7 §8.20: different first authors with one family name get initials; same author, same year: a/b."""
        items = {"j1": {"id": "j1", "title": "A", "issued": {"date-parts": [[2001]]},
                        "author": [{"family": "Smith", "given": "John"}]},
                 "j2": {"id": "j2", "title": "B", "issued": {"date-parts": [[2001]]},
                        "author": [{"family": "Smith", "given": "John"}]},
                 "a1": {"id": "a1", "title": "C", "issued": {"date-parts": [[2001]]},
                        "author": [{"family": "Smith", "given": "Ann"}, {"family": "Doe"}]}}
        clusters = [{"citationID": "x", "items": [{"id": i} for i in ("j1", "j2", "a1")]}]
        result = engine.process(styles.load_style("apa-7"), items, clusters, document_language="en")
        self.assertEqual(result["citations"][0]["text"], "(A. Smith & Doe, 2001; J. Smith, 2001a, 2001b)")
        mla = engine.process(styles.load_style("mla-9"), items, clusters, document_language="en")
        self.assertNotIn("J. Smith", mla["citations"][0]["text"])  # option off in MLA


if __name__ == "__main__":
    unittest.main()
