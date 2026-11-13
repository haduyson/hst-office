# SPDX-License-Identifier: AGPL-3.0-only
"""Reference items (CSL-JSON) are validated at one boundary; dates parse the shapes importers and users write."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_dates as dates
from hst_office import citation_model as model


class NormalizeItem(unittest.TestCase):
    def test_keeps_known_fields_and_cleans_values(self):
        item, warnings = model.normalize_item({
            "id": " x1 ", "type": "book", "title": "  Kinh tế học ", "volume": 2, "edition": 3.0,
            "author": ["Nguyễn Văn An", {"family": "Smith", "given": "John", "junk": 1}, {}],
            "issued": "2010-05-07", "accessed": {"raw": "2024"}, "unknown-key": "dropped",
            "custom": {"hst": {"modified": "2026-11-13T00:00:00+00:00"}}})
        self.assertEqual(warnings, [])
        self.assertEqual(item["id"], "x1")
        self.assertEqual(item["title"], "Kinh tế học")  # NFC
        self.assertEqual((item["volume"], item["edition"]), ("2", "3"))
        self.assertEqual(item["author"], [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True},
                                          {"family": "Smith", "given": "John"}])
        self.assertEqual(item["issued"], {"date-parts": [[2010, 5, 7]]})
        self.assertEqual(item["accessed"], {"date-parts": [[2024]]})
        self.assertNotIn("unknown-key", item)
        self.assertEqual(model.modified(item), "2026-11-13T00:00:00+00:00")

    def test_unknown_type_missing_id_and_empty_item(self):
        item, warnings = model.normalize_item({"type": "hologram"})
        self.assertEqual(item["type"], "document")
        self.assertTrue(item["id"].startswith("hst-"))
        self.assertEqual(len(warnings), 2)
        with self.assertRaises(ValueError):
            model.normalize_item("not an object")

    def test_names_literal_and_lone_given_name(self):
        self.assertEqual(model.normalize_name({"literal": "Bộ Y tế", "family": "x"}), {"literal": "Bộ Y tế"})
        self.assertEqual(model.normalize_name({"given": "Plato"}), {"literal": "Plato"})
        self.assertIsNone(model.normalize_name({"family": "  "}))
        self.assertEqual(model.normalize_name({"family": "Lê", "given": "Hà", "hst-vi": 1}),
                         {"family": "Lê", "given": "Hà", "hst-vi": True})

    def test_embedding_copy_drops_bulky_fields(self):
        item = {"id": "a", "type": "book", "title": "T", "abstract": "long", "keyword": "k", "note": "n" * 600}
        embedded = model.for_embedding(item)
        self.assertEqual(embedded, {"id": "a", "type": "book", "title": "T"})
        self.assertIn("abstract", item)
        self.assertEqual(model.for_embedding({"id": "b", "note": "short"})["note"], "short")

    def test_touch_records_modification_time(self):
        item = model.touch({"id": "a"})
        self.assertRegex(model.modified(item), r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(len(model.TYPE_LABELS), len({t for t, _ in model.TYPE_LABELS}))
        self.assertTrue(all(t in model.CSL_TYPES for t, _ in model.TYPE_LABELS))


class Dates(unittest.TestCase):
    def test_parse_shapes(self):
        cases = {"2010": [[2010]], "2010-05-07": [[2010, 5, 7]], "2010/05/07/Spring": [[2010, 5, 7]],
                 "2010///": [[2010]], "07/05/2010": [[2010, 5, 7]], "May 7, 2010": [[2010, 5, 7]],
                 "7 May 2010": [[2010, 5, 7]], "2010 May 7": [[2010, 5, 7]], "2010 Jan-Feb": [[2010, 1]],
                 "ngày 07 tháng 5 năm 2009": [[2009, 5, 7]], "2010-2011": [[2010], [2011]],
                 "2015-05-28T10:00:00Z": [[2015, 5, 28]], "Sept. 2001": [[2001, 9]]}
        for text, parts in cases.items():
            self.assertEqual(dates.parse(text), {"date-parts": parts}, text)

    def test_no_date_and_literal(self):
        self.assertEqual(dates.parse("n.d."), {})
        self.assertEqual(dates.parse("không năm"), {})
        self.assertEqual(dates.parse("đang in"), {"literal": "đang in"})
        self.assertIsNone(dates.normalize(""))
        self.assertEqual(dates.normalize({"date-parts": [["2010", "13"]]}), {"date-parts": [[2010]]})
        self.assertEqual(dates.normalize({"date-parts": [["x"]], "literal": "circa 1900"}), {"literal": "circa 1900"})
        self.assertEqual(dates.year({"literal": "x"}), None)
        self.assertEqual(dates.parts({"date-parts": [[2010, 5]]}), (2010, 5, 0))


if __name__ == "__main__":
    unittest.main()
