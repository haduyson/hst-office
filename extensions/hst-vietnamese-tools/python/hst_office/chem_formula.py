# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Định dạng công thức hoá học: which characters of a text become subscript/superscript, and which are replaced. Pure.

Policy: only tokens that look like a chemical formula are touched; every other word stays exactly as typed, so a
selection of ordinary Vietnamese text with "Năm 2024", "khổ A4" or "COVID-19" in it is safe. A token is a run of
non-space characters (surrounding punctuation such as ",;:" or brackets around the whole token trimmed). It is a
formula when, after an optional leading coefficient, it is a sequence of real element symbols (H, He, … Og), groups
in () or [], digits, a hydrate dot and an optional trailing charge, and either it has at least two element symbols
or it has a subscript or a charge (so "Na+" and "O2" count, the lone word "C" or "I" does not). Words with
lowercase-only letters, Vietnamese letters, or element-looking runs that are not elements ("COVID", "A4", "Năm")
are left alone.

Context: one element and digits with nothing else ("F1", "B2", "C4", "K2") is often a key, a level or a room. Such a
token is formatted when it is the whole target (the one selected word, or the word before the cursor), when it is a
common one-element molecule (COMMON: H2, O2, O3, N2, Cl2, Br2, I2, S8, P4, C60), or when its line or paragraph has
chemistry: a reaction arrow, another formula ("H2SO4", "Fe3+") or "formula + formula". Otherwise it stays as typed.

Rules: a digit run right after an element symbol, ")" or "]" is subscript; a leading coefficient (also after the
hydrate dot) stays normal; a trailing charge (digits + "+"/"-", or a lone sign) is superscript, and when digits run
into the sign ("SO42-") the last digit is the charge and the rest the subscript; "-" in a charge becomes "−"
(U+2212); "." or "*" between two formula parts becomes "·". Arrows "->", "-->", "=>" become "→" and "<->", "<=>"
become "⇌", wherever they stand.
"""
import re

ELEMENTS = frozenset((
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr "
    "Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir "
    "Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl "
    "Mc Lv Ts Og").split())
SUB, SUP = "sub", "sup"
MINUS, DOT = "−", "·"
ARROWS = (("<->", "⇌"), ("<=>", "⇌"), ("-->", "→"), ("->", "→"), ("=>", "→"))
_TRIM = ",;:!?\"'“”‘’…"
_PART = re.compile(r"[A-Z][a-z]?|\d+|[()\[\]]")
_LINE_BREAK = re.compile("[\n\r\u2029\u2028]")
_ARROW_ANYWHERE = re.compile("|".join(re.escape(a) for a, _ in ARROWS) + "|[\u2192\u21cc]")
# one-element molecules formatted anywhere; F2 is not among them: F1–F12 are keyboard keys in ordinary text
COMMON = frozenset("H2 O2 O3 N2 Cl2 Br2 I2 S8 P4 C60".split())


class Edit:
    """One change at [start, end) of the text: kind SUB/SUP formats those characters, or `text` replaces them."""
    __slots__ = ("start", "end", "kind", "text")

    def __init__(self, start, end, kind=None, text=None):
        self.start, self.end, self.kind, self.text = start, end, kind, text

    def __eq__(self, other):
        return (self.start, self.end, self.kind, self.text) == (other.start, other.end, other.kind, other.text)

    def __repr__(self):
        return "Edit(%d, %d, %r, %r)" % (self.start, self.end, self.kind, self.text)


def _charge(token):
    """(body, charge_start) with the trailing charge split off, or (token, None).

    Digits before the sign: after ")" or "]", or after a lone element ("Fe3+", "Cu2+"), they are the charge; two or
    more digits ("SO42-", "Hg22+") give their last digit to the charge and the rest to the subscript; one digit after
    a polyatomic body ("NH4+", "NO3-") is a subscript and the sign alone is the charge."""
    match = re.search(r"(\d*)([+\-\u2212])$", token)
    if not match or match.start() == 0:
        return token, None
    body, digits = token[:match.start()], match.group(1)
    if not digits:
        return body, match.start()
    if body[-1] in ")]" or (len(digits) == 1 and re.fullmatch(r"[A-Z][a-z]?", body)):
        return body, match.start()
    if len(digits) >= 2:
        return token[:match.end(1) - 1], match.end(1) - 1
    return token[:match.start(2)], match.start(2)


def _parse_part(part, offset):
    """Edits of one hydrate part (a formula without dot or charge), or None when it is not a formula."""
    match = re.match(r"\d+", part)
    start = match.end() if match else 0  # leading coefficient: normal
    pieces = _PART.findall(part[start:])
    if "".join(pieces) != part[start:] or not pieces or not pieces[0].isalpha() and pieces[0] not in "([":
        return None
    edits, elements, depth, previous = [], 0, 0, None
    position = offset + start
    for piece in pieces:
        if piece.isdigit():
            if previous is None or previous in "([":
                return None
            edits.append(Edit(position, position + len(piece), SUB))
        elif piece in "([":
            depth += 1
        elif piece in ")]":
            depth -= 1
            if depth < 0:
                return None
        elif piece in ELEMENTS:
            elements += 1
        else:
            return None
        previous = piece if not piece.isdigit() else "1"
        position += len(piece)
    return (edits, elements) if depth == 0 and elements else None


def parse_token(token, offset=0):
    """Edits of one token, or [] when the token is not a formula."""
    edits, formula = _token(token, offset)
    return edits if formula else []


def _token(token, offset):
    """(edits, is a formula): "NaCl" is a formula without edits."""
    body, charge_at = _charge(token)
    parts = re.split(r"([.*·])", body)
    edits, elements, cursor = [], 0, offset
    for index, part in enumerate(parts):
        if index % 2:  # the hydrate separator
            edits.append(Edit(cursor, cursor + 1, text=DOT) if part != DOT else None)
            cursor += 1
            continue
        parsed = _parse_part(part, cursor)
        if parsed is None:
            return [], False
        edits += parsed[0]
        elements += parsed[1]
        cursor += len(part)
    edits = [e for e in edits if e is not None]
    if charge_at is not None:
        start = offset + charge_at
        sign_at = offset + len(token) - 1
        if start < sign_at:
            edits.append(Edit(start, sign_at, SUP))
        edits.append(Edit(sign_at, sign_at + 1, SUP))
        if token[-1] == "-":
            edits.append(Edit(sign_at, sign_at + 1, text=MINUS))
    return edits, elements >= 2 or any(e.kind for e in edits)


def _ambiguous(token):
    """One element and digits only ("F1", "B2", "2H2"): a key, a level or a room as often as a molecule."""
    match = re.fullmatch(r"\d*([A-Z][a-z]?\d+)", token)
    return bool(match) and match.group(1) not in COMMON


def parse(text):
    """Every edit of `text`, sorted by position: formula tokens and reaction arrows. An ambiguous token is formatted
    only when it is the whole text, or its line has chemistry: an arrow, another formula or "formula + formula"."""
    tokens, edits = [], []
    for match in re.finditer(r"\S+", text):
        token, start = match.group(0), match.start()
        stripped = token.rstrip(_TRIM)
        lead = len(stripped) - len(stripped.lstrip(_TRIM))
        stripped = stripped[lead:]
        stripped = stripped.rstrip(".")  # a full stop after a formula; a hydrate dot is never last
        line = len(_LINE_BREAK.findall(text, 0, start))
        found, formula = ([], False) if any(a in stripped for a, _ in ARROWS) else _token(stripped, start + lead)
        tokens.append((line, stripped, found if formula else [], formula, formula and _ambiguous(stripped)))
    chemistry = {line for line, _, _, formula, ambiguous in tokens if formula and not ambiguous}
    chemistry |= {len(_LINE_BREAK.findall(text, 0, m.start())) for m in _ARROW_ANYWHERE.finditer(text)}
    for before, plus, after in zip(tokens, tokens[1:], tokens[2:]):
        if plus[1] == "+" and before[3] and after[3]:
            chemistry.add(plus[0])
    single = len(tokens) == 1
    for line, _, found, _, ambiguous in tokens:
        if not ambiguous or single or line in chemistry:
            edits += found
    for arrow, replacement in ARROWS:
        for match in re.finditer(re.escape(arrow), text):
            if not any(e.start < match.end() and match.start() < e.end for e in edits):
                edits.append(Edit(match.start(), match.end(), text=replacement))
    return sorted(edits, key=lambda e: (e.start, e.text is not None))


def preview(text):
    """Pure helper for tests and logs: `text` with the edits applied as Unicode (₂, ⁺…) to show the result."""
    sub = str.maketrans("0123456789+-−", "₀₁₂₃₄₅₆₇₈₉₊₋₋")
    sup = str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")
    chars = list(text)
    for edit in sorted(parse(text), key=lambda e: e.text is None):  # replace first, then format
        if edit.text is not None:
            chars[edit.start] = edit.text
            for i in range(edit.start + 1, edit.end):
                chars[i] = ""
        else:
            table = sub if edit.kind == SUB else sup
            for i in range(edit.start, edit.end):
                chars[i] = chars[i].translate(table)
    return "".join(chars)
