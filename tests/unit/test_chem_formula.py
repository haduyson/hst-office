# SPDX-License-Identifier: AGPL-3.0-only
"""Định dạng công thức hoá học: which characters become subscript/superscript and which are replaced
(hst_office.chem_formula), and how the command applies them to a text range (chem_formula_action)."""
import unittest

import _paths  # noqa: F401
from hst_office import chem_formula as chem
from hst_office.chem_formula import SUB, SUP, Edit, parse, preview


class FormulaRules(unittest.TestCase):
    CASES = {
        "H2SO4": "H₂SO₄",
        "Fe2(SO4)3": "Fe₂(SO₄)₃",
        "2H2O": "2H₂O",
        "SO42-": "SO₄²⁻",
        "Fe3+": "Fe³⁺",
        "Na+": "Na⁺",
        "Cl-": "Cl⁻",
        "CuSO4.5H2O": "CuSO₄·5H₂O",
        "CuSO4*5H2O": "CuSO₄·5H₂O",
        "Ca(OH)2": "Ca(OH)₂",
        "NH4+": "NH₄⁺",
        "[Fe(CN)6]4-": "[Fe(CN)₆]⁴⁻",
        "Cr2O72-": "Cr₂O₇²⁻",
        "PO43-": "PO₄³⁻",
        "NO3-": "NO₃⁻",
        "Hg22+": "Hg₂²⁺",
        "Cu2+": "Cu²⁺",
        "O2": "O₂",
        "C6H12O6": "C₆H₁₂O₆",
        "(NH4)2SO4": "(NH₄)₂SO₄",
    }

    def test_owner_cases_and_tricky_ones(self):
        for text, expected in self.CASES.items():
            self.assertEqual(preview(text), expected, text)

    def test_arrows(self):
        self.assertEqual(preview("2H2 + O2 -> 2H2O"), "2H₂ + O₂ → 2H₂O")
        self.assertEqual(preview("N2 + 3H2 <-> 2NH3"), "N₂ + 3H₂ ⇌ 2NH₃")
        self.assertEqual(preview("A <=> B => C --> D"), "A ⇌ B → C → D")

    def test_real_formatting_not_unicode_digits(self):
        """The digits stay ASCII; only their formatting changes (Word round-trips CharEscapement through .docx)."""
        self.assertEqual(parse("H2SO4"), [Edit(1, 2, SUB), Edit(4, 5, SUB)])
        self.assertEqual(parse("Fe3+"), [Edit(2, 3, SUP), Edit(3, 4, SUP)])
        self.assertEqual(parse("SO42-"), [Edit(2, 3, SUB), Edit(3, 4, SUP), Edit(4, 5, SUP), Edit(4, 5, text=chem.MINUS)])

    def test_plain_text_in_a_selection_is_left_alone(self):
        text = "Năm 2024, khổ A4, COVID-19, bản 1.0.3, 2.5 kg, mục 3-4, Điều 5. Dung dịch H2SO4 loãng; ion SO42-."
        self.assertEqual(preview(text), text.replace("H2SO4", "H₂SO₄").replace("SO42-", "SO₄²⁻"))
        for word in ("Năm", "2024", "A4", "COVID-19", "khổ", "Hà Nội", "I", "C", "IN", "No", "ISO 9001", "e-mail",
                     "x2", "abc", "MH370", "F1", "Mr.", "3-4"):
            with self.subTest(word):
                changed = preview(word)
                if word in ("F1",):  # an element followed by a digit is a formula by design (F₁ is fluorine)
                    continue
                self.assertEqual(changed, word)

    def test_punctuation_around_a_formula(self):
        self.assertEqual(preview("(CO2), H2O; O3: NaCl."), "(CO₂), H₂O; O₃: NaCl.")
        self.assertEqual(preview("“H2O”"), "“H₂O”")

    def test_offsets_count_from_the_text_start(self):
        edits = parse("ab H2O")
        self.assertEqual(edits, [Edit(4, 5, SUB)])

    def test_never_two_edits_overlap_except_minus(self):
        for text in list(self.CASES) + ["Cu2+ + 2OH- -> Cu(OH)2"]:
            spans = [(e.start, e.end) for e in parse(text) if e.text is None]
            self.assertEqual(len(spans), len(set(spans)), text)


class _Cursor:
    def __init__(self, doc):
        self.doc, self.pos, self.end = doc, 0, 0

    def goRight(self, count, expand):
        if not expand:
            self.pos = self.end = self.pos + count
        else:
            self.end += count
        return True

    def getString(self):
        return "".join(c for c, _ in self.doc.chars[self.pos:self.end])

    @property
    def CharEscapement(self):
        return self.doc.chars[self.pos][1]

    CharEscapementHeight = 100

    def setString(self, text):
        self.doc.chars[self.pos:self.end] = [[c, 0] for c in text]

    def setPropertyValue(self, name, value):
        if name == "CharEscapement":
            for item in self.doc.chars[self.pos:self.end]:
                item[1] = value


class _Range:
    """A text range of characters with an escapement each, enough for chem_formula_action."""

    def __init__(self, text):
        self.chars = [[c, 0] for c in text]

    def getString(self):
        return "".join(c for c, _ in self.chars)

    def getText(self):
        return self

    def getStart(self):
        return self

    def createTextCursorByRange(self, _):
        return _Cursor(self)


class ApplyToRange(unittest.TestCase):
    """chem_formula_action.apply on a fake text range: replacements land before their formatting."""

    def test_order_and_values(self):
        from hst_office import chem_formula_action as action
        rng = _Range("Cl- -> SO42-")
        self.assertEqual(action.apply(rng), 7)
        self.assertEqual(rng.getString(), "Cl\u2212 \u2192 SO42\u2212")
        self.assertEqual([e for _, e in rng.chars], [0, 0, 14000, 0, 0, 0, 0, 0, -14000, 14000, 14000])

    def test_log_for_the_slides_undo(self):
        """What ChemUndo replays: each operation in execution order with what it replaced."""
        from hst_office import chem_formula_action as action
        log = []
        action.apply(_Range("Cl- H2"), log)
        self.assertEqual(log, [("format", 5, 1, SUB, [(0, 100)]), ("text", 2, "-", chem.MINUS),
                               ("format", 2, 1, SUP, [(0, 100)])])


if __name__ == "__main__":
    unittest.main()
