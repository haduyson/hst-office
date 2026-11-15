# SPDX-License-Identifier: AGPL-3.0-only
"""Exports to RIS, BibTeX and CSL-JSON read back into the same references."""
import json
import os
import unittest

import _paths

from hst_office import citation_export as export
from hst_office import citation_import as importer

FIELDS = ("type", "title", "container-title", "publisher", "publisher-place", "volume", "issue", "DOI", "URL",
          "edition", "genre", "language", "issued", "accessed")


def samples():
    with open(os.path.join(_paths.ROOT, "tests", "fixtures", "citations", "samples.json"), encoding="utf-8") as handle:
        return json.load(handle)


class RoundTrip(unittest.TestCase):
    def check(self, fmt, skip=None):
        items = samples()
        back = importer.import_text(export.export(items, fmt), fmt=fmt)
        self.assertEqual((len(back.items), back.warnings), (len(items), []))
        for before, after in zip(items, back.items):
            skipped = (skip or {}).get(before["id"], ())
            for field in FIELDS:
                if field in skipped:
                    continue
                expected = before.get(field)
                if field == "language" and expected and fmt != "csl-json":
                    expected = expected.split("-")[0]
                self.assertEqual(after.get(field), expected, (fmt, before["id"], field))
            self.assertEqual(after.get("page", "").replace("–", "-"), before.get("page", ""), before["id"])
            people = [n.get("family") or n.get("literal") for n in before.get("author", [])]
            self.assertEqual([n.get("family") or n.get("literal") for n in after.get("author", [])], people)

    def test_ris(self):
        self.check("ris")

    def test_bibtex(self):
        # BibTeX has no legislation type and no field for a web page's site name
        self.check("bibtex", {"vi-law": ("type",), "vi-decree": ("type",), "en-who": ("container-title",),
                              "en-nodate": ("container-title",)})

    def test_csl_json(self):
        self.check("csl-json")


class Shapes(unittest.TestCase):
    def test_ris_lines_and_names(self):
        text = export.to_ris(samples()[:1])
        self.assertIn("\r\n", text)
        self.assertTrue(text.startswith("TY  - BOOK\r\nAU  - Trần, Văn Bình\r\n"))
        self.assertIn("ER  - ", text)
        with self.assertRaises(ValueError):
            export.export([], "docx")

    def test_bibtex_keys_escape_and_types(self):
        items = [{"id": "a", "type": "thesis", "genre": "Luận văn Thạc sĩ", "title": "Tối ưu 50% & hơn",
                  "author": [{"family": "Trần", "given": "Văn Bình"}], "issued": {"date-parts": [[2019]]},
                  "publisher": "Trường Đại học X"},
                 {"id": "b", "type": "thesis", "title": "Tối ưu khác", "author": [{"family": "Trần"}],
                  "issued": {"date-parts": [[2019]]}, "URL": "https://example.org/a_b%20c"}]
        text = export.to_bibtex(items)
        self.assertIn("@mastersthesis{tran2019,", text)  # no title word longer than three letters
        self.assertIn("@phdthesis{tran2019khac,", text)
        self.assertIn("title = {Tối ưu 50\\% \\& hơn}", text)
        self.assertIn("school = {Trường Đại học X}", text)
        self.assertIn("@phdthesis{", text)
        self.assertIn("url = {https://example.org/a_b%20c}", text)
        self.assertIn("author = {{Trần}}", text)

    def test_portable_csl_json_drops_hst_extras(self):
        item = {"id": "a", "author": [{"family": "Lê", "given": "An", "hst-vi": True}],
                "custom": {"hst": {"modified": "x"}}}
        self.assertEqual(json.loads(export.to_csl_json([item], portable=True)),
                         [{"id": "a", "author": [{"family": "Lê", "given": "An"}]}])
        self.assertIn("hst-vi", export.to_csl_json([item]))


if __name__ == "__main__":
    unittest.main()
