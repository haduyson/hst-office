# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức: the pieces LaTeX is read into and how they join as formula text (no UNO).

A piece is a kind and its formula text. join() writes a sequence of pieces with the rules the formula language needs
and LaTeX does not:
  - a binary operator or relation needs something on its left and right, else the formula drops it: {} fills the
    gap (\\cdot b, = b in an aligned row, x =);
  - a big operator (\\sum, \\int, \\lim) needs an operand: {} when nothing follows;
  - brackets that pair up are written as pairs; a bracket without its partner, as in the half-open interval [-7;3),
    is written as a lone symbol, so it never breaks the formula;
  - 3{,}5 is one number."""
from collections import namedtuple

Piece = namedtuple("Piece", "kind text")
ORD, BIN, REL, OP, FUNC, LIMFUNC, SPACE, OPEN, CLOSE, BAR, NEWLINE, MID, NUM, NUMPUNCT = (
    "ord", "bin", "rel", "op", "func", "limfunc", "space", "open", "close", "bar", "newline", "mid", "num",
    "numpunct")
UNARY = frozenset(("+", "-", "+-", "-+"))
# bracket key -> (partner key, paired opening, paired closing, lone opening, lone closing)
BRACKETS = {"(": (")", "(", ")", "\\(", "\\)"), "[": ("]", "[", "]", "\\[", "\\]"),
            "{": ("}", "lbrace", "rbrace", "\\lbrace", "\\rbrace"), "|": ("|", "lline", "rline", "\\lline", "\\rline"),
            "‖": ("‖", "ldline", "rdline", "\\ldline", "\\rdline"),
            "langle": ("rangle", "langle", "rangle", "\\langle", "\\rangle"),
            "lfloor": ("rfloor", "lfloor", "rfloor", "\\lfloor", "\\rfloor"),
            "lceil": ("rceil", "lceil", "rceil", "\\lceil", "\\rceil")}
CLOSERS = {partner[0]: key for key, partner in BRACKETS.items()}
BRACKET_COMMANDS = {"{": "{", "lbrace": "{", "}": "}", "rbrace": "}", "|": "‖", "Vert": "‖", "vert": "|",
                    "langle": "langle", "rangle": "rangle", "lfloor": "lfloor", "rfloor": "rfloor",
                    "lceil": "lceil", "rceil": "rceil"}
UNICODE_RELATION = {"≤": "<=", "≥": ">=", "≠": "<>", "≈": "approx", "∈": "in", "∉": "notin", "⊂": "subset",
                    "⊆": "subseteq", "⇒": "drarrow", "⇔": "dlrarrow", "→": "toward", "≡": "equiv"}
UNICODE_BINARY = {"±": "+-", "·": "cdot", "×": "times", "÷": "div", "∪": "union", "∩": "intersection", "−": "-"}
DEGREE = '"°"'  # ^\\circ: the degree sign beside the number, as typeset; the formula's circ is a small ring operator
UNICODE_ORDINARY = {"∞": "infinity", "°": DEGREE, "π": "%pi", "…": "dotslow", "∅": "emptyset"}


class TexError(ValueError):
    """The LaTeX is malformed or uses a command the converter does not know."""



def quote(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def braced(text):
    return text if _simple(text) else "{%s}" % text


def _simple(text):
    return bool(text) and " " not in text and not text.startswith('"') or (text.startswith("{") and _one_group(text))


def _one_group(text):
    depth = 0
    for index, char in enumerate(text):
        depth += {"{": 1, "}": -1}.get(char, 0)
        if depth == 0:
            return index == len(text) - 1
    return False


def _pair_brackets(pieces):
    """Pieces with each bracket written as one of a pair or as a lone symbol."""
    pieces = list(pieces)
    stack = []  # (index, key) of open brackets
    paired = {}
    for index, piece in enumerate(pieces):
        if piece.kind not in (OPEN, CLOSE, BAR):
            continue
        key = piece.text.split("\0", 1)[0]
        if piece.kind == BAR and stack and stack[-1][1] == key:
            paired[stack.pop()[0]], paired[index] = "open", "close"
        elif piece.kind in (OPEN, BAR):
            stack.append((index, key))
        else:
            opener = CLOSERS.get(key)
            depth = next((d for d in range(len(stack) - 1, -1, -1) if stack[d][1] == opener), None)
            if depth is not None:
                paired[stack[depth][0]], paired[index] = "open", "close"
                del stack[depth:]
    result = []
    for index, piece in enumerate(pieces):
        if piece.kind not in (OPEN, CLOSE, BAR):
            result.append(piece)
            continue
        key, script = piece.text, ""
        if "\0" in key:
            key, script = key.split("\0", 1)
        role = paired.get(index)
        opener = key if piece.kind != CLOSE else CLOSERS[key]
        _, pair_open, pair_close, lone_open, lone_close = BRACKETS[opener]
        if role == "open":
            result.append(Piece(OPEN, pair_open + script))
        elif role == "close":
            result.append(Piece(CLOSE, pair_close + script))
        else:
            lone = lone_close if piece.kind == CLOSE else lone_open
            result.append(Piece(ORD, braced(lone) + script if script else lone))
    return result


def _merge_numbers(pieces):
    """3{,}5 is one number, as the formula language writes it (3,5)."""
    result = []
    for piece in pieces:
        if piece.kind == NUM and len(result) >= 2 and result[-1].kind == NUMPUNCT and result[-2].kind == NUM:
            punct = result.pop()
            result[-1] = Piece(NUM, result[-1].text + punct.text + piece.text)
        else:
            result.append(piece)
    return [Piece(ORD, p.text) if p.kind == NUMPUNCT else p for p in result]


def join(pieces):
    """The formula text of a sequence of pieces."""
    pieces = _pair_brackets(_merge_numbers(pieces))
    out = []
    last = "start"  # start | open | bin | rel | operand
    for index, piece in enumerate(pieces):
        kind = piece.kind
        if kind == BIN:
            if last != "operand" and piece.text not in UNARY:
                out.append("{}")
            last = "bin"
        elif kind == REL:  # a relation with nothing on its left is dropped by the formula: {} keeps it
            if last != "operand":
                out.append("{}")
            last = "rel"
        elif kind in (OPEN, NEWLINE, MID):
            last = "open"
        elif kind != SPACE:
            last = "operand"
        out.append(piece.text)
        if kind == OP:
            following = next((p for p in pieces[index + 1:] if p.kind != SPACE), None)
            if following is None or following.kind not in (ORD, NUM, FUNC, LIMFUNC, OPEN, OP):
                out.append("{}")
    if last in ("bin", "rel"):
        out.append("{}")
    return " ".join(part for part in out if part)

