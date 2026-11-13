# SPDX-License-Identifier: AGPL-3.0-only
"""Importers: RIS (Scholar, Scopus, Web of Science, VJOL), BibTeX, CSL-JSON, EndNote XML, PubMed, EndNote tagged."""
import codecs
import os
import unittest

import _paths

from hst_office import citation_import as importer
from hst_office.citation_text_io import ImportFailure, decode

FIXTURES = os.path.join(_paths.ROOT, "tests", "fixtures", "citations")


def load(name):
    return importer.import_file(os.path.join(FIXTURES, name))


class Ris(unittest.TestCase):
    def test_scholar_crlf_records(self):
        result = load("scholar.ris")
        self.assertEqual((result.format, len(result.items), result.warnings), ("ris", 2, []))
        article, book = result.items
        self.assertEqual(article["page"], "436-444")
        self.assertEqual(article["ISSN"], "0028-0836")
        self.assertEqual(book["ISBN"], "9780393071016")
        self.assertEqual(book["type"], "book")

    def test_scopus_continuation_and_unknown_tag(self):
        item = load("scopus.ris").items[0]
        self.assertTrue(item["abstract"].endswith("considerable biological interest."))
        self.assertEqual(item["note"], "XY: Unknown exporter tag")
        self.assertEqual(item["language"], "en")
        self.assertIn("thẻ không hỗ trợ", load("scopus.ris").warnings[0])

    def test_wos_chapter_editors_and_vietnamese_thesis(self):
        chapter, thesis = load("wos.ris").items
        self.assertEqual(chapter["container-title"], "The genetic basis of human cancer")
        self.assertEqual([e["family"] for e in chapter["editor"]], ["Vogelstein", "Kinzler"])
        self.assertEqual(thesis["author"], [{"family": "Đặng", "given": "Thu Trang", "hst-vi": True}])
        self.assertEqual(thesis["genre"], "Luận án Tiến sĩ Kinh tế")

    def test_vjol_missing_er_doi_with_parentheses_and_name_fixes(self):
        result = load("vjol.ris")
        self.assertEqual(len(result.items), 2)
        self.assertIn("thiếu “ER”", result.warnings[0])
        self.assertEqual(result.items[0]["DOI"], "10.54607/hcmue.js.18.8.3112(2021)")
        self.assertEqual(result.items[0]["issued"], {"date-parts": [[2021, 8, 30]]})
        kinds = [s["kind"] for s in result.suggestions if s["item"] == result.items[0]["id"]]
        self.assertEqual(kinds, ["name-order", "name-order", "sentence-case", "language"])


class OtherFormats(unittest.TestCase):
    def test_bibtex(self):
        result = load("sample.bib")
        self.assertEqual(len(result.items), 6)
        self.assertRegex(result.warnings[0], r"^Dòng 64: ")
        lecun, tran, chapter, thesis, who, vaswani = result.items
        self.assertEqual((lecun["container-title"], lecun["issued"]), ("Nature", {"date-parts": [[2015, 5]]}))
        self.assertEqual(tran["title"], "Kinh tế học vĩ mô")
        self.assertEqual(tran["author"], [{"family": "Trần", "given": "Văn Bình", "hst-vi": True}])
        self.assertEqual((tran["publisher"], tran["language"]), ("Giáo dục Việt Nam", "vi"))
        self.assertEqual(chapter["type"], "chapter")
        self.assertEqual((thesis["type"], thesis["publisher"]), ("thesis", "Trường Đại học Kinh tế Quốc dân"))
        self.assertEqual((who["type"], who["author"]), ("webpage", [{"literal": "World Health Organization"}]))
        self.assertEqual(vaswani["note"], "arXiv:1706.03762")

    def test_csl_json_endnote_pubmed_enw(self):
        zotero = load("zotero.json")
        self.assertEqual(len(zotero.items), 3)
        self.assertEqual(zotero.items[0]["issued"], {"date-parts": [[2015, 5, 28]]})
        self.assertEqual(len(zotero.warnings), 2)
        endnote = load("endnote.xml").items
        self.assertEqual(endnote[0]["DOI"], "10.1056/NEJMe2002387")
        self.assertEqual(endnote[0]["issued"], {"date-parts": [[2020, 3, 26]]})
        self.assertEqual(endnote[1]["editor"], [{"family": "Lê", "given": "Thị Hoa", "hst-vi": True}])
        pubmed = load("pubmed.nbib").items
        self.assertEqual(pubmed[0]["title"], "Covid-19 - Navigating the Uncharted")
        self.assertEqual(pubmed[0]["author"][0], {"family": "Fauci", "given": "Anthony S"})
        self.assertEqual((pubmed[0]["PMID"], pubmed[1]["page"]), ("32109011", "436-44"))
        enw = load("scholar.enw").items
        self.assertEqual((enw[0]["volume"], enw[1]["edition"]), ("521", "2"))

    def test_detection_and_refusals(self):
        self.assertEqual(importer.detect("TY  - JOUR\nER  - "), "ris")
        self.assertEqual(importer.detect("  @article{x, title={a}}"), "bibtex")
        self.assertEqual(importer.detect("[{}]"), "csl-json")
        self.assertEqual(importer.detect("PMID- 1\nTI  - x"), "nbib")
        self.assertEqual(importer.detect("%0 Book\n%T x"), "enw")
        with self.assertRaises(ImportFailure):
            importer.detect("just some text")
        with self.assertRaises(ImportFailure):
            importer.import_text('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><xml><records/></xml>',
                                 fmt="endnote-xml")
        with self.assertRaises(ImportFailure) as caught:
            importer.import_text("[1, 2", fmt="csl-json")
        self.assertEqual(caught.exception.line, 1)


class Decoding(unittest.TestCase):
    def test_encodings_and_errors(self):
        self.assertEqual(decode(codecs.BOM_UTF8 + "Lê".encode()), "Lê")
        self.assertEqual(decode("Lê\r\nAn".encode("utf-16")), "Lê\nAn")
        self.assertEqual(decode("Lê".encode()), "Lê")
        with self.assertRaises(ImportFailure) as caught:
            decode(b"TY  - JOUR\nTI  - Vi\xeat\n")
        self.assertEqual(caught.exception.line, 2)
        with self.assertRaises(ImportFailure):
            decode(b"x" * (10 * 1024 * 1024 + 1))
        with self.assertRaises(ImportFailure):
            decode(b"a\x00b")


if __name__ == "__main__":
    unittest.main()
