# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: where the LaTeX spans are in a paragraph's text, and the end-of-run message."""
import unittest
from collections import namedtuple

import _paths  # noqa: F401

from hst_office import tex_math_spans, tex_toggle_texts


def spans(text):
    return [(text[s.start:s.end], s.body, s.display) for s in tex_math_spans.find_spans(text)]


class SpanTest(unittest.TestCase):
    def test_four_delimiters(self):
        text = r"Cho $x>0$ và \(y<1\). Tính $$S=x+y$$ rồi \[P=xy\]."
        self.assertEqual(spans(text), [("$x>0$", "x>0", False), (r"\(y<1\)", "y<1", False),
                                       ("$$S=x+y$$", "S=x+y", True), (r"\[P=xy\]", "P=xy", True)])

    def test_escaped_dollar_and_prices_stay_text(self):
        self.assertEqual(spans(r"Giá 5$ và 7$, còn \$3 thì không"), [])
        self.assertEqual(spans(r"$a=\$5$"), [(r"$a=\$5$", r"a=\$5", False)])

    def test_dollar_needs_text_right_inside(self):
        self.assertEqual(spans("$ x$ và $y $"), [])
        self.assertEqual(spans("$x$2"), [])

    def test_inline_spans_end_with_the_paragraph_display_spans_do_not(self):
        self.assertEqual(spans("$x\n+1$"), [])
        self.assertEqual(spans("$$\nx+1\n$$"), [("$$\nx+1\n$$", "\nx+1\n", True)])
        self.assertEqual(spans("\\[\na\n\\]"), [("\\[\na\n\\]", "\na\n", True)])

    def test_unclosed_and_empty_delimiters(self):
        self.assertEqual(spans("$$x"), [])
        self.assertEqual(spans(r"\(x"), [])
        self.assertEqual(spans("$$$$"), [])

    def test_braces_and_brackets_inside_a_span(self):
        self.assertEqual(spans(r"$x\in[-7;3)$"), [(r"$x\in[-7;3)$", r"x\in[-7;3)", False)])
        self.assertEqual(spans(r"\(\left[a;b\right)\)"), [(r"\(\left[a;b\right)\)", r"\left[a;b\right)", False)])

    def test_wrap(self):
        self.assertEqual(tex_math_spans.wrap("x", False), "$x$")
        self.assertEqual(tex_math_spans.wrap("x", True), "$$x$$")


Result = namedtuple("Result", "converted failed reverted kept")


class ReportTest(unittest.TestCase):
    def test_counts(self):
        text = tex_toggle_texts.report(Result(40, 2, 0, 0))
        self.assertIn("40 công thức LaTeX", text)
        self.assertIn("2 công thức LaTeX không chuyển được", text)
        self.assertIn("tô vàng", text)
        self.assertEqual(tex_toggle_texts.report(Result(0, 0, 1, 0)), "Đã chuyển 1 công thức về mã LaTeX.")
        self.assertIsNone(tex_toggle_texts.report(Result(0, 0, 0, 0)))


if __name__ == "__main__":
    unittest.main()
