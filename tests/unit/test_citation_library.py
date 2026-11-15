# SPDX-License-Identifier: AGPL-3.0-only
"""The user's reference library: atomic save, damaged files kept aside, duplicates, merge, search."""
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401

from hst_office import citation_dedupe as dedupe
from hst_office import citation_library as library

ITEM = {"id": "a", "type": "article-journal", "title": "Deep learning", "DOI": "10.1038/nature14539",
        "author": [{"family": "LeCun", "given": "Yann"}], "issued": {"date-parts": [[2015]]}}


class Library(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = library.library_path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_missing_file_is_an_empty_library_and_save_round_trips(self):
        lib = library.Library.load(self.path)
        self.assertEqual(len(lib), 0)
        added, duplicates = lib.add([ITEM, {"title": "Kinh tế học vĩ mô", "type": "book"}])
        self.assertEqual((len(added), duplicates), (2, []))
        lib.save()
        self.assertTrue(self.path.endswith(os.path.join("hst-citations", "library.json")))
        with open(self.path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["schemaVersion"], 1)
        again = library.Library.load(self.path)
        self.assertEqual(again.get("a")["title"], "Deep learning")
        self.assertTrue(again.get("a")["custom"]["hst"]["modified"])
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.path)) if n.startswith(".tmp")], [])

    def test_damaged_file_is_copied_aside_and_never_overwritten(self):
        os.makedirs(os.path.dirname(self.path))
        for attempt, expected in ((1, ".bad"), (2, ".bad-2")):
            with open(self.path, "w", encoding="utf-8") as handle:
                handle.write("{broken %d" % attempt)
            with self.assertRaises(library.LibraryDamaged) as caught:
                library.Library.load(self.path)
            self.assertTrue(caught.exception.bad_path.endswith(expected))
        with open(self.path + ".bad", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "{broken 1")

    def test_newer_schema_opens_read_only(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"schemaVersion": 2, "items": [ITEM, ITEM, "bad"]}, handle)
        lib = library.Library.load(self.path)
        self.assertEqual(len(lib), 2)  # the repeated id got a fresh one
        self.assertTrue(lib.warnings)
        with self.assertRaises(library.LibraryError):
            lib.save()

    def test_duplicates_merge_and_keep_both(self):
        lib = library.Library(self.path)
        lib.add([ITEM])
        same_doi = dict(ITEM, id="b", DOI="https://doi.org/10.1038/NATURE14539", volume="521")
        same_title = {"id": "c", "title": "Deep Learning", "author": [{"family": "Lecun"}], "issued": "2015"}
        added, duplicates = lib.add([same_doi, same_title])
        self.assertEqual(added, [])
        self.assertEqual([existing for _, existing in duplicates], ["a", "a"])
        lib.merge("a", duplicates[0][0])
        self.assertEqual(lib.get("a")["volume"], "521")
        self.assertEqual(lib.get("a")["DOI"], "10.1038/nature14539")  # stored values win
        copy_id = lib.keep_both(same_title)
        self.assertNotEqual(copy_id, "c")
        self.assertEqual(len(lib), 2)

    def test_search_update_remove(self):
        lib = library.Library(self.path)
        lib.add([ITEM, {"id": "v", "type": "book", "title": "Kinh tế học vĩ mô", "issued": "2010",
                        "author": [{"family": "Trần", "given": "Văn Bình", "hst-vi": True}]}])
        self.assertEqual([i["id"] for i in lib.search("tran binh")], ["v"])
        self.assertEqual([i["id"] for i in lib.search("KINH TE 2010")], ["v"])
        self.assertEqual(len(lib.search("")), 2)
        lib.update(dict(lib.get("v"), title="Kinh tế học"))
        self.assertEqual(lib.get("v")["title"], "Kinh tế học")
        with self.assertRaises(KeyError):
            lib.update({"id": "nope", "title": "x"})
        self.assertEqual(len(lib.remove(["v", "nope"])), 1)


class Dedupe(unittest.TestCase):
    def test_doi_and_isbn_normalisation(self):
        self.assertEqual(dedupe.clean_doi("https://doi.org/10.54607/hcmue.js.18.8.3112(2021)"),
                         "10.54607/hcmue.js.18.8.3112(2021)")
        self.assertEqual(dedupe.normalize_doi("doi: 10.1056/NEJMe2002387."), "10.1056/nejme2002387")
        self.assertEqual(dedupe.normalize_doi("not a doi"), "")
        self.assertEqual(dedupe.isbn13("0-306-40615-2"), "9780306406157")
        self.assertEqual(dedupe.isbn13("978-0-306-40615-7"), "9780306406157")
        self.assertEqual(dedupe.isbn13("978-0-306-40615-8"), "")
        self.assertEqual(dedupe.isbns("0306406152; 9780393071016"), ["9780306406157", "9780393071016"])
        index = dedupe.Index([{"id": "x", "ISBN": "0-306-40615-2"}])
        self.assertEqual(index.find({"id": "y", "ISBN": "9780306406157"}), "x")


if __name__ == "__main__":
    unittest.main()
