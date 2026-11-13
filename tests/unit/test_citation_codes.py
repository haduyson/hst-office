# SPDX-License-Identifier: AGPL-3.0-only
"""citation_codes: field codes of citations and the bibliography, including Zotero/Mendeley codes read as-is."""
import json
import unittest

import _paths  # noqa: F401
from hst_office import citation_codes as codes

ITEM = {"id": "a", "type": "book", "title": "Giáo trình \"đặc biệt\" {x} \\ <&>", "author": [{"literal": "Bộ Y tế"}]}


class Encode(unittest.TestCase):
    def test_round_trip_keeps_cites_mode_and_item_data(self):
        cluster = {"citationID": "c1", "mode": "narrative",
                   "items": [{"id": "a", "locator": "314-315", "label": "page", "prefix": "xem", "suppressAuthor": True}]}
        code = codes.encode_citation(cluster, {"a": ITEM})
        self.assertTrue(code.startswith("ADDIN HST_CITATION {"))
        self.assertEqual(codes.kind_of(code), "citation")
        back, items = codes.decode_citation(code)
        self.assertEqual(back, {"citationID": "c1", "mode": "narrative", "items": [
            {"id": "a", "locator": "314-315", "label": "page", "prefix": "xem", "suppressAuthor": True}]})
        self.assertEqual(items, {"a": ITEM})

    def test_new_id_and_normal_mode_by_default(self):
        back, _ = codes.decode_citation(codes.encode_citation({"items": [{"id": "a"}]}, {}))
        self.assertTrue(back["citationID"].startswith("c"))
        self.assertEqual(back["mode"], "normal")

    def test_refuses_empty_missing_id_and_oversize(self):
        with self.assertRaises(codes.CodeError):
            codes.encode_citation({"items": []}, {})
        with self.assertRaises(codes.CodeError):
            codes.encode_citation({"items": [{"locator": "1"}]}, {})
        big = dict(ITEM, note="x" * (codes.MAX_CODE_BYTES + 10))
        with self.assertRaises(codes.CodeError):
            codes.encode_citation({"items": [{"id": "a"}]}, {"a": big})

    def test_bibliography_code(self):
        self.assertEqual(codes.kind_of(codes.encode_bibliography()), "bibliography")
        self.assertEqual(codes.encode_bibliography(), 'ADDIN HST_BIBLIOGRAPHY {"v":1}')


class Decode(unittest.TestCase):
    def test_newer_version_and_bad_json_are_refused(self):
        for code in ('ADDIN HST_CITATION {"v":2,"items":[{"id":"a"}]}', "ADDIN HST_CITATION {not json",
                     'ADDIN HST_CITATION {"v":1,"items":[]}', 'ADDIN HST_CITATION []', "ADDIN OTHER {}"):
            with self.assertRaises(codes.CodeError, msg=code):
                codes.decode_citation(code)

    def test_zotero_citation_is_read(self):
        body = {"citationID": "Zx", "citationItems": [
            {"id": 42, "locator": "7", "suppress-author": True,
             "itemData": {"id": 42, "type": "book", "title": "Deep learning"}}]}
        code = "ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(body)
        self.assertEqual(codes.kind_of(code), "foreign")
        cluster, items = codes.decode_citation(code)
        self.assertEqual(cluster["items"], [{"id": "42", "locator": "7", "suppressAuthor": True}])
        self.assertEqual(items["42"]["title"], "Deep learning")

    def test_kind_of_other_values(self):
        self.assertIsNone(codes.kind_of(None))
        self.assertIsNone(codes.kind_of("ADDIN EN.CITE"))


if __name__ == "__main__":
    unittest.main()
