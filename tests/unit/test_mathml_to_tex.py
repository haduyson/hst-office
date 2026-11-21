# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: a formula's MathML (as HST Công thức exports it) back to LaTeX."""
import unittest

import _paths  # noqa: F401

from hst_office import mathml_to_tex, tex_to_starmath

HEAD = '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"><semantics>'
TAIL = '<annotation encoding="StarMath 5.0">x</annotation></semantics></math>'


def tex(body):
    return mathml_to_tex.tex(HEAD + body + TAIL)


def fence(char, form, stretchy):
    return '<mo fence="true" form="%s" stretchy="%s">%s</mo>' % (form, "true" if stretchy else "false", char)


class MathmlToTexTest(unittest.TestCase):
    def test_fraction_root_scripts(self):
        self.assertEqual(tex("<mfrac><mrow><mn>2</mn><mi>x</mi></mrow><mn>3</mn></mfrac>"), r"\frac{2x}{3}")
        self.assertEqual(tex("<mroot><mi>x</mi><mn>3</mn></mroot>"), r"\sqrt[3]{x}")
        self.assertEqual(tex("<msubsup><mi>x</mi><mn>1</mn><mn>2</mn></msubsup>"), "x_{1}^{2}")
        self.assertEqual(tex("<msup><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow><mn>2</mn></msup>"), "{a+b}^{2}")

    def test_greek_operators_sets(self):
        self.assertEqual(tex("<mrow><mi>α</mi><mo>≤</mo><mi>π</mi><mo>∈</mo><mi mathvariant='normal'>ℝ</mi></mrow>"),
                         r"\alpha\le\pi\in\mathbb{R}")
        self.assertEqual(tex("<mrow><mi>x</mi><mo>→</mo><mo>+</mo><mi>∞</mi></mrow>"), r"x\to+\infty")
        self.assertEqual(tex("<mrow><mi>&infin;</mi><mo>&lt;</mo><mn>1</mn></mrow>"), r"\infty<1")  # as exported

    def test_fences_stretchy_and_lone(self):
        body = "<mrow>%s<mrow><mi>a</mi><mi>;</mi><mi>b</mi></mrow>%s</mrow>" % (fence("[", "prefix", True),
                                                                             fence(")", "postfix", True))
        self.assertEqual(tex(body), r"\left[ a;b\right)")
        self.assertEqual(tex("<mrow><mo stretchy='false'>[</mo><mn>1</mn><mi>;</mi><mn>2</mn>"
                             "<mo stretchy='false'>)</mo></mrow>"), "[1;2)")

    def test_system_is_an_array_in_a_brace(self):
        body = ("<mrow>%s<mtable><mtr><mtd columnalign='left'><mi>x</mi></mtd></mtr>"
                "<mtr><mtd columnalign='left'><mi>y</mi></mtd></mtr></mtable></mrow>" % fence("{", "prefix", True))
        self.assertEqual(tex(body), r"\left\{ \begin{array}{l}x\\ y\end{array}\right.")

    def test_accents_limits_text(self):
        self.assertEqual(tex("<mover accent='true'><mi>AB</mi><mo stretchy='true'>⃗</mo></mover>"),
                         r"\overrightarrow{AB}")
        self.assertEqual(tex("<mover accent='true'><mi>AB</mi><mo stretchy='true'>⌢</mo></mover>"),
                         r"\overset{\frown}{AB}")
        self.assertEqual(tex("<mrow><munder><mi>lim</mi><mrow><mi>x</mi><mo>→</mo><mn>0</mn></mrow></munder>"
                             "<mi>x</mi></mrow>"), r"\lim_{x\to0}x")
        self.assertEqual(tex("<munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi>"
                             "</munderover>"), r"\sum_{i=1}^{n}")
        self.assertEqual(tex("<mtext>Diện tích 50%</mtext>"), r"\text{Diện tích 50\%}")
        self.assertEqual(tex("<mn>0,5</mn>"), "0{,}5")

    def test_written_latex_converts_again(self):
        bodies = ["<mfrac><mi>a</mi><mi>b</mi></mfrac>", "<msqrt><mi>x</mi></msqrt>",
                  "<mrow><mi>sin</mi><mi>x</mi></mrow>", "<mrow><mn>30</mn><mo>∘</mo></mrow>"]
        for body in bodies:
            with self.subTest(body):
                tex_to_starmath.convert(tex(body))

    def test_unknown_or_broken_mathml_fails(self):
        with self.assertRaises(mathml_to_tex.TexBackError):
            tex("<merror><mi>x</mi></merror>")
        with self.assertRaises(mathml_to_tex.TexBackError):
            mathml_to_tex.tex("<math")


if __name__ == "__main__":
    unittest.main()
