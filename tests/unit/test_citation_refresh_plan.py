# SPDX-License-Identifier: AGPL-3.0-only
"""citation_refresh_plan with the real formatter: what a refresh writes, in which order, and when it writes nothing.

Fields are given as citation_document.scan lists them: raw order (footnotes before the body) with a reading rank."""
import types
import unittest

import _paths  # noqa: F401
from hst_office import citation_codes as codes
from hst_office import citation_engine, citation_model, citation_refresh_plan as refresh_plan, citation_style

ENGINE = types.SimpleNamespace(process=citation_engine.process, modified=citation_model.modified,
                               load_style=lambda s, o, p: citation_style.load_style(s, o, p))
VI = {"id": "a", "type": "book", "title": "Giáo trình kinh tế", "language": "vi", "publisher": "Giáo dục",
      "publisher-place": "Hà Nội", "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}],
      "issued": {"date-parts": [[2010]]}}
EN = {"id": "b", "type": "article-journal", "title": "A study", "language": "en", "container-title": "Nature",
      "volume": "5", "page": "1-9", "author": [{"family": "Smith", "given": "John"}], "issued": {"date-parts": [[2020]]}}


def cite(cid, ids, items, locator=None):
    cites = [{"id": i} for i in ids]
    if locator:
        cites[-1].update(locator=locator, label="page")
    return codes.encode_citation({"citationID": cid, "items": cites}, items)


def fields(*specs):
    """(kind, code, rank) in raw order."""
    return [{"index": n, "rank": rank, "kind": kind, "code": code, "result": ""} for n, (kind, code, rank) in enumerate(specs)]


class Plan(unittest.TestCase):
    def setUp(self):
        self.doc = fields(("citation", cite("f1", ["b"], {"b": EN}, "3"), 2),  # in a footnote: raw first, read last
                          ("citation", cite("c1", ["a"], {"a": VI}), 0),
                          ("citation", cite("c2", ["b"], {"b": EN}), 1),
                          ("bibliography", codes.encode_bibliography(), 3))

    def test_numbers_follow_reading_order_and_updates_raw_order(self):
        result = refresh_plan.plan(self.doc, {"style": "ieee", "opts": {"language": "en"}}, ENGINE)
        self.assertEqual([h for _c, h in result["citations"]], ["[2, p. 3]", "[1]", "[2]"])
        self.assertEqual(result["order"], ["a", "b"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["citations_changed"], 3)
        self.assertEqual(len(result["bibliography"]), 1)
        self.assertTrue(result["bib_changed"])

    def test_vietnamese_thesis_bibliography_groups_by_language(self):
        result = refresh_plan.plan(self.doc, {"style": "vn-so", "opts": {}}, ENGINE)
        self.assertEqual(result["bib_roles"], ["title", "heading", "entry", "heading", "entry"])
        html = result["bibliography"][0][1]
        self.assertTrue(html.startswith("<p>TÀI LIỆU THAM KHẢO</p><p>Tiếng Việt</p><p>1. Nguyễn Văn An (2010), <i>"))
        self.assertEqual([e["label"] for e in result["entries"]], ["1.", "2."])

    def test_nothing_changes_when_results_are_current(self):
        first = refresh_plan.plan(self.doc, {"style": "apa-7", "opts": {}}, ENGINE)
        texts = {code: html for code, html in first["citations"]}
        current = [dict(f) for f in self.doc]
        for field, (_code, html) in zip([f for f in current if f["kind"] == "citation"], first["citations"]):
            field["result"] = html.replace("<i>", "").replace("</i>", "")
        bib = [f for f in current if f["kind"] == "bibliography"][0]
        bib["result"] = "\n".join(refresh_plan.bibliography_paragraphs(
            ENGINE.process(ENGINE.load_style("apa-7", {}, None), {"a": VI, "b": EN},
                           [{"citationID": "x", "items": [{"id": "a"}, {"id": "b"}]}])["bibliography"], "—")[i][2]
            for i in range(3))
        again = refresh_plan.plan(current, {"style": "apa-7", "opts": {}}, ENGINE)
        self.assertEqual(again["citations_changed"], 0)
        self.assertFalse(again["bib_changed"])
        self.assertTrue(texts)

    def test_pasted_copy_gets_a_new_id_and_newest_item_data_wins(self):
        newer = citation_model.touch(dict(VI, title="Giáo trình kinh tế (tái bản)"))
        doc = fields(("citation", cite("c1", ["a"], {"a": VI}), 0), ("citation", cite("c1", ["a"], {"a": newer}), 1))
        result = refresh_plan.plan(doc, {"style": "vn-so", "opts": {}}, ENGINE)
        first, second = (codes.decode_citation(c) for c, _h in result["citations"])
        self.assertNotEqual(first[0]["citationID"], second[0]["citationID"])
        self.assertEqual(first[1]["a"]["title"], "Giáo trình kinh tế (tái bản)")
        self.assertIn("tái bản", result["entries"][0]["text"])

    def test_unreadable_code_is_kept_with_its_text(self):
        doc = fields(("citation", "ADDIN HST_CITATION {broken", 0), ("citation", cite("c1", ["a"], {"a": VI}), 1))
        doc[0]["result"] = "[7] <cũ>"
        result = refresh_plan.plan(doc, {"style": "vn-so", "opts": {}}, ENGINE)
        self.assertEqual(result["citations"][0], ("ADDIN HST_CITATION {broken", "[7] &lt;cũ&gt;"))
        self.assertTrue(result["warnings"])
        self.assertEqual(result["count"], 1)

    def test_vietnamese_styles_keep_vietnamese_terms_in_an_english_document(self):
        vn = refresh_plan.plan(self.doc, {"style": "vn-so", "opts": {}}, ENGINE, document_language="en")
        intl = refresh_plan.plan(self.doc, {"style": "ieee", "opts": {}}, ENGINE, document_language="en")
        self.assertIn("tr. 3", vn["citations"][0][1])
        self.assertIn("p. 3", intl["citations"][0][1])
        vi = refresh_plan.plan(self.doc, {"style": "ieee", "opts": {}}, ENGINE, document_language="vi")
        self.assertIn("tr. 3", vi["citations"][0][1])

    def test_note_style_and_empty_bibliography(self):
        doc = fields(("bibliography", codes.encode_bibliography(), 0))
        result = refresh_plan.plan(doc, {"style": "chicago-chu-thich", "opts": {}}, ENGINE, empty_text="(trống)")
        self.assertTrue(result["note"])
        self.assertEqual(result["citations"], [])
        self.assertTrue(result["bibliography"][0][1].endswith("<p>(trống)"))  # last paragraph left open


if __name__ == "__main__":
    unittest.main()
