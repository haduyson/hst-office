# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức: LaTeX of exam papers to HST Công thức formula text (expected output per snippet)."""
import json
import os
import unittest

import _paths  # noqa: F401

from hst_office import tex_to_starmath

CORPUS = os.path.join(_paths.ROOT, "tests", "fixtures", "tex-toggle", "exam-snippets.json")


def load():
    with open(CORPUS, encoding="utf-8") as stream:
        return json.load(stream)


class CorpusTest(unittest.TestCase):
    def test_every_snippet_gives_its_formula(self):
        corpus = load()
        self.assertGreaterEqual(len(corpus["snippets"]), 40)
        for item in corpus["snippets"]:
            with self.subTest(item["id"]):
                self.assertEqual(tex_to_starmath.convert(item["tex"]), item["starmath"])

    def test_malformed_or_unknown_latex_fails(self):
        for item in load()["failures"]:
            with self.subTest(item["id"]):
                with self.assertRaises(tex_to_starmath.TexError):
                    tex_to_starmath.convert(item["tex"])


class ConstructTest(unittest.TestCase):
    def convert(self, tex):
        return tex_to_starmath.convert(tex)

    def test_fractions_and_roots(self):
        self.assertEqual(self.convert(r"\frac12"), "{{1} over {2}}")
        self.assertEqual(self.convert(r"\tfrac{a}{b}"), "{{a} over {b}}")
        self.assertEqual(self.convert(r"\sqrt[n]{x}"), "nroot{n}{x}")
        self.assertEqual(self.convert(r"\sqrt x"), "sqrt{x}")

    def test_scripts_take_one_character_or_a_group(self):
        self.assertEqual(self.convert("x^23"), "x^{2} 3")
        self.assertEqual(self.convert("x_{n+1}^{2}"), "x_{n + 1}^{2}")
        self.assertEqual(self.convert("f'(x)"), "f ′ ( x )")
        self.assertEqual(self.convert("y''^2"), "{y ′ ′}^{2}")

    def test_half_open_intervals_keep_their_lone_bracket(self):
        self.assertEqual(self.convert("[-7;3)"), r"\[ - 7 ; 3 \)")
        self.assertEqual(self.convert(r"\left[ a;b \right)"), "{left [ a ; b right )}")
        self.assertEqual(self.convert("(a;b]"), r"\( a ; b \]")
        self.assertEqual(self.convert("(a+b)^2"), "( a + b )^{2}")

    def test_operators_without_an_operand_get_an_empty_one(self):
        self.assertEqual(self.convert(r"\cdot b"), "{} cdot b")
        self.assertEqual(self.convert("x+"), "x + {}")
        self.assertEqual(self.convert("x=-3"), "x = - 3")
        self.assertEqual(self.convert(r"\sum_{i=1}^{n}"), "sum_{i = 1}^{n} {}")

    def test_letter_runs_that_are_formula_words_are_spelled_out(self):
        self.assertEqual(self.convert("in"), "i n")
        self.assertEqual(self.convert("AB"), "AB")
        self.assertEqual(self.convert(r"\vec{or}"), "vec{o r}")

    def test_text_keeps_vietnamese_and_quotes(self):
        self.assertEqual(self.convert(r'\text{với "mọi" } x'), r'"với \"mọi\" " x')
        self.assertEqual(self.convert(r"\text{50\%}"), '"50%"')

    def test_number_sets_degrees_percent_spaces_dots(self):
        self.assertEqual(self.convert(r"\mathbb{N}^*"), "ℕ^{\"*\"}")
        self.assertEqual(self.convert(r"90^\circ"), 'nospace{90 "°"}')  # the degree sign, not a small ring
        self.assertEqual(self.convert(r"90^{\circ}C"), 'nospace{90 "°"} C')
        self.assertEqual(self.convert("90°"), '90 "°"')
        self.assertEqual(self.convert(r"f\circ g"), "f circ g")
        self.assertEqual(self.convert(r"5\%"), '5 "%"')
        self.assertEqual(self.convert(r"a\,b\quad c"), "a ` b ~ c")
        self.assertEqual(self.convert(r"1,\dots,n"), "1 , dotslow , n")

    def test_arc_idiom(self):
        self.assertEqual(self.convert(r"\overset\frown{AB}"), "widearc{AB}")
        self.assertEqual(self.convert(r"\overset{a}{=}"), "{{{} = {}} csup {a}}")

    def test_inline_limits_beside_the_sign_display_limits_above_and_below(self):
        self.assertEqual(self.convert(r"\int_0^1 x\,dx"), "int_{0}^{1} x ` dx")
        self.assertEqual(tex_to_starmath.convert(r"\int_0^1 x\,dx", display=True), "int from{0} to{1} x ` dx")
        self.assertEqual(tex_to_starmath.convert(r"\sum_{k=1}^n k", display=True), "sum from{k = 1} to{n} k")
        self.assertEqual(self.convert(r"\lim_{x\to 0} x"), "lim from{x toward 0} x")  # below, as MathType inline

    def test_limit_functions_put_their_limit_below(self):
        self.assertEqual(self.convert(r"\max_{x\in D} f"), "{{func max} csub {x in D}} f")

    def test_systems(self):
        self.assertEqual(self.convert(r"\begin{cases}x=1\\y=2\end{cases}"),
                         "{left lbrace stack{alignl {x = 1} # alignl {y = 2}} right none}")
        self.assertEqual(self.convert(r"\begin{bmatrix}1&0\\0&1\\\end{bmatrix}"),
                         "{left [ matrix{{1} # {0} ## {0} # {1}} right ]}")

    def test_empty_span_fails(self):
        with self.assertRaises(tex_to_starmath.TexError):
            self.convert("  ")


if __name__ == "__main__":
    unittest.main()
