# SPDX-License-Identifier: AGPL-3.0-only
"""A .csl file the user imports: refused when unsafe or broken, installed into the user's styles, formatted."""
import os
import tempfile
import unittest

import _paths
import citation_golden as golden

from hst_office import citation_csl_parse as csl_parse
from hst_office import citation_csl_style as csl_style
from hst_office import citation_engine as engine
from hst_office import citation_runs as runs
from hst_office import citation_style as styles

CSL = os.path.join(_paths.ROOT, "tests", "fixtures", "citations", "csl", "hst-test-numeric.csl")
NS = 'xmlns="http://purl.org/net/xbiblio/csl"'


def read():
    with open(CSL, "rb") as handle:
        return handle.read()


class Parse(unittest.TestCase):
    def test_refusals(self):
        bad = {b'<?xml version="1.0"?><!DOCTYPE style [<!ENTITY x "y">]><style/>': "DOCTYPE",
               b"<style>": "XML", b"<other/>": "<style>",
               ('<style %s class="in-text"><citation/></style>' % NS).encode(): "<citation><layout>",
               ('<style %s class="in-text"><citation><layout><text macro="m"/></layout></citation></style>'
                % NS).encode(): "macro không có: m",
               ('<style %s class="weird"><citation><layout/></citation></style>' % NS).encode(): "class"}
        for data, message in bad.items():
            with self.assertRaises(csl_parse.CslError) as caught:
                csl_parse.parse(data)
            self.assertIn(message, str(caught.exception))
        with self.assertRaises(csl_parse.CslError):
            csl_parse.parse(b" " * (csl_parse.MAX_BYTES + 1))

    def test_unsupported_elements_are_warnings(self):
        data = read().replace(b"<info>", b"<info><fancy/>")
        self.assertIn("<fancy>", csl_parse.parse(data).warnings[0])
        parsed = csl_parse.parse(read())
        self.assertEqual((parsed.title, parsed.cls, parsed.warnings), ("HST test numeric", "in-text", []))
        self.assertEqual(parsed.terms[("et-al", "long")], ("and others", "and others"))


class Format(unittest.TestCase):
    def test_install_load_and_format(self):
        with tempfile.TemporaryDirectory() as user_dir:
            style_id, warnings = csl_style.install(user_dir, read())
            self.assertEqual((style_id, warnings), ("user-hst-test-numeric", []))
            self.assertEqual(csl_style.install(user_dir, read())[0], "user-hst-test-numeric-2")
            listed = {s["id"]: s for s in styles.list_styles(user_dir)}
            self.assertEqual((listed[style_id]["kind"], listed[style_id]["class"]), ("csl", "numeric"))
            style = styles.load_style(style_id, user_dir=user_dir)
        items = golden.samples()
        clusters = [{"citationID": "a", "items": [{"id": "en-lecun", "locator": "437-438"}]},
                    {"citationID": "b", "items": [{"id": i} for i in ("en-watson", "en-krugman", "en-murray")]},
                    {"citationID": "c", "items": [{"id": i} for i in ("vi-book", "vi-book-b", "en-krugman",
                                                                      "en-lecun", "en-murray")]}]
        result = engine.process(style, items, clusters, uncited_ids=["zh-luxun", "vi-law"])
        self.assertEqual([c["text"] for c in result["citations"]], ["[3, pp. 437-438]", "[2, 4, 7]", "[2–6]"])
        entries = [runs.to_markup(runs.from_public(e["runs"])) for e in result["bibliography"]["groups"][0]["entries"]]
        self.assertEqual(entries[2], "[3] LeCun, Y., Y. Bengio, and G. Hinton (2015). “Deep learning.” *Nature*, vol. 521, "
                                     "pp. 436–444. https://doi.org/10.1038/nature14539.")
        self.assertEqual(entries[4], "[5] Trần, V. B. (2010). *Kinh tế học vĩ mô*. Hà Nội: Giáo dục Việt Nam.")
        self.assertEqual(entries[-1], "[8] 鲁迅 (1923). *呐喊*. 北京: 新潮社.")
        self.assertTrue(result["bibliography"]["hangingIndent"])

    def test_author_date_note_and_vietnamese_locale(self):
        text = read().decode().replace('default-locale="en-US"', 'default-locale="vi-VN"')
        text = text.replace('<text variable="citation-number"/>', '<text macro="author"/>')
        text = text.replace('<text variable="citation-number" prefix="[" suffix="] "/>', "")
        text = text.replace('<key variable="citation-number"/>', '<key macro="author"/>')
        style = csl_style.CslEngineStyle(csl_parse.parse(text.replace('collapse="citation-number"', "").encode()), "u")
        self.assertEqual((style.cls, style.options["language"]), ("author-date", "vi"))
        items = golden.samples()
        result = engine.process(style, items, [{"citationID": "a", "items": [{"id": "en-vaswani", "locator": "5"}]}])
        self.assertEqual(result["citations"][0]["text"], "[Vaswani, A. and others, tr. 5]")
        note = csl_style.CslEngineStyle(csl_parse.parse(text.replace('class="in-text"', 'class="note"').encode()), "n")
        self.assertEqual(note.cls, "note")


if __name__ == "__main__":
    unittest.main()
