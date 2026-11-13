# SPDX-License-Identifier: AGPL-3.0-only
"""citation_numbering: the typed "[3, tr. 15" before Alt+Shift+I, and numbers mapped to sources."""
import unittest

import _paths  # noqa: F401
from hst_office import citation_numbering as numbering


class ParseTyped(unittest.TestCase):
    def check(self, text, numbers, locator="", length=None, label="page"):
        found = numbering.parse_typed(text)
        self.assertIsNotNone(found, text)
        self.assertEqual(found["numbers"], numbers, text)
        self.assertEqual(found["locator"], locator, text)
        self.assertEqual(found["label"], label, text)
        if length is not None:
            self.assertEqual(found["length"], length, text)

    def test_forms_theses_use(self):
        self.check("theo nghiên cứu [3", [3], length=2)
        self.check("theo nghiên cứu [3]", [3], length=3)
        self.check("x [3, tr. 15]", [3], "15")
        self.check("x [3, tr.15-16", [3], "15-16")
        self.check("x [3–5]", [3, 4, 5])
        self.check("x [3, 7]", [3, 7])
        self.check("x [3, 7, tr. 314–315]", [3, 7], "314–315")
        self.check("x [12, p. 4]", [12], "4")
        self.check("x [2, tập 3", [2], "3", label="volume")
        self.check("[5; 21; 49]", [5, 21, 49])

    def test_not_a_typed_citation(self):
        for text in ("", "plain text", "[3] then more text", "[abc", "[0", "[5-3]", "x [3, tr. ]", "[1-99]"):
            self.assertIsNone(numbering.parse_typed(text), text)

    def test_duplicates_are_kept_once(self):
        self.check("[3, 3, 2-4]", [3, 2, 4])


class Mapping(unittest.TestCase):
    def test_ids_for_numbers(self):
        self.assertEqual(numbering.ids_for_numbers([2, 1], ["a", "b"]), (["b", "a"], []))
        self.assertEqual(numbering.ids_for_numbers([3], ["a", "b"]), ([], [3]))

    def test_cluster_puts_the_locator_on_the_last_source(self):
        cluster = numbering.cluster_for(["a", "b"], "15", "page")
        self.assertEqual(cluster["items"], [{"id": "a"}, {"id": "b", "locator": "15", "label": "page"}])
        self.assertEqual(numbering.cluster_for(["a"])["items"], [{"id": "a"}])


if __name__ == "__main__":
    unittest.main()
