# SPDX-License-Identifier: AGPL-3.0-only
"""Rich runs: punctuation collapsing while formatting, and the public/HTML forms the document layer renders."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_runs as runs


class Collect(unittest.TestCase):
    def collect(self, *pieces):
        out = runs.Out()
        for piece in pieces:
            out.add(*piece) if isinstance(piece, tuple) else out.add(piece)
        return runs.plain(runs.merge(out.runs))

    def test_period_after_terminal_punctuation_is_dropped(self):
        self.assertEqual(self.collect("Smith, J. A.", ". ", "Title"), "Smith, J. A. Title")
        self.assertEqual(self.collect(("Why?", "i"), "."), "Why?")
        self.assertEqual(self.collect("Wow!", ". Next"), "Wow! Next")

    def test_trailing_separator_gives_way_to_new_punctuation(self):
        self.assertEqual(self.collect("Nxb Giáo dục", ", ", "."), "Nxb Giáo dục.")
        self.assertEqual(self.collect("A", ", ", ", B"), "A, B")
        self.assertEqual(self.collect("A", "; ", ". "), "A.")

    def test_spaces_collapse_and_outer_spaces_trim(self):
        self.assertEqual(self.collect(" A ", " B "), "A B")
        self.assertEqual(runs.merge([("", "i"), ("a", "i"), ("b", "i"), ("c", "")]), [("ab", "i"), ("c", "")])

    def test_quote_punctuation_moves_inside_double_quotes_only(self):
        found = runs.quote_punctuation([("“Title”", ""), (", ", ""), ("Journal", "i")])
        self.assertEqual(runs.plain(found), "“Title,” Journal")
        self.assertEqual(runs.plain(runs.quote_punctuation([("‘Title’, x", "")])), "‘Title’, x")
        self.assertEqual(runs.plain(runs.quote_punctuation([("“A”.", "")])), "“A.”")


class Forms(unittest.TestCase):
    def test_public_round_trip_and_html(self):
        found = [("Smith ", ""), ("Title & <x>", "i"), ("1", "s"), ("B", "bi")]
        public = runs.to_public(found)
        self.assertEqual(public[1], {"text": "Title & <x>", "italic": True})
        self.assertEqual(public[3], {"text": "B", "italic": True, "bold": True})
        self.assertEqual(runs.from_public(public), runs.merge(found))
        self.assertEqual(runs.to_html(found), "Smith <i>Title &amp; &lt;x&gt;</i><sup>1</sup><i><b>B</b></i>")
        self.assertEqual(runs.to_markup(found), "Smith *Title & <x>*^1^***B***")
        with self.assertRaises(ValueError):
            runs.from_public([{"text": 3}])


if __name__ == "__main__":
    unittest.main()
