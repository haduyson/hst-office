# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: the characters of LaTeX math as pieces, and scripts on a piece (tex_latex_reader)."""
from . import tex_starmath_symbols as sym
from .tex_starmath_pieces import (BAR, BIN, CLOSE, DEGREE, FUNC, LIMFUNC, NUM, NUMPUNCT, OP, OPEN, ORD, REL, SPACE,
                                  UNICODE_BINARY, UNICODE_ORDINARY, UNICODE_RELATION, Piece, TexError, braced, join,
                                  quote)


def character(reader, char):
    """[Piece] for a character that starts a piece (a letter run, a number, a group, a bracket, an operator)."""
    if char.isascii() and char.isalpha():
        start = reader.i - 1
        while reader.i < len(reader.s) and reader.s[reader.i].isascii() and reader.s[reader.i].isalpha():
            reader.i += 1
        run = reader.s[start:reader.i]
        if run.lower() in sym.KEYWORDS:
            return [Piece(ORD, c) for c in run]
        return [Piece(ORD, run)]
    if char.isdigit() or (char == "." and reader.i < len(reader.s) and reader.s[reader.i].isdigit()):
        start = reader.i - 1
        while reader.i < len(reader.s) and (reader.s[reader.i].isdigit() or (
                reader.s[reader.i] in ".," and reader.i + 1 < len(reader.s) and reader.s[reader.i + 1].isdigit())):
            reader.i += 1
        return [Piece(NUM, reader.s[start:reader.i])]
    if char == "{":
        inner, stop = reader.sequence(("}",))
        if stop != "}":
            raise TexError("unclosed {")
        if len(inner) == 1 and inner[0].kind == ORD and inner[0].text in (",", "."):
            return [Piece(NUMPUNCT, inner[0].text)]
        return [Piece(ORD, "{%s}" % join(inner) if inner else "{}")]
    if char in "([":
        return [Piece(OPEN, char)]
    if char == ")":
        return [Piece(CLOSE, char)]
    if char == "|":
        return [Piece(BAR, "|")]
    if char in "+-/":
        return [Piece(BIN, char)]
    if char == "*":  # N^*: the formula language has no lone star
        return [Piece(ORD, quote(char))]
    if char in "=<>":
        return [Piece(REL, char)]
    if char in ",;:.?!":
        return [Piece(ORD, char)]
    if char == "~":
        return [Piece(SPACE, "~")]
    if char in "#%\"@`$":
        return [Piece(ORD, quote(char))]
    if char in UNICODE_RELATION:
        return [Piece(REL, UNICODE_RELATION[char])]
    if char in UNICODE_BINARY:
        return [Piece(BIN, UNICODE_BINARY[char])]
    if char in UNICODE_ORDINARY:
        return [Piece(ORD, UNICODE_ORDINARY[char])]
    if char in "^_":  # a script with nothing before it
        reader.i -= 1
        return [Piece(ORD, "{}")]
    if char == "&" or char == "}":
        raise TexError("unexpected %s" % char)
    return [Piece(ORD, char if char.isalpha() else quote(char))]



def with_scripts(piece, sub, sup, display):
    if sup in ("circ", DEGREE) and sub is None and piece.kind in (ORD, NUM):  # 30^\\circ is 30°
        return Piece(piece.kind, "nospace{%s %s}" % (piece.text, DEGREE))
    if piece.kind == OP and not display and not piece.text.startswith(("lim", "oper")):  # inline: beside the sign
        return Piece(OP, piece.text + ("_{%s}" % sub if sub is not None else "") + (
            "^{%s}" % sup if sup is not None else ""))
    if piece.kind == OP:
        text = piece.text + (" from{%s}" % sub if sub is not None else "")
        text += " to{%s}" % sup if sup is not None else ""
        return Piece(OP, text)
    if piece.kind == LIMFUNC:  # \max_{x}: the limit goes below, as in display
        base = "{%s}" % piece.text
        if sub is not None:
            base = "{%s csub {%s}}" % (base, sub)
        if sup is not None:
            base = "{%s csup {%s}}" % (base, sup)
        return Piece(FUNC, base)
    suffix = ("_{%s}" % sub if sub is not None else "") + ("^{%s}" % sup if sup is not None else "")
    if piece.kind in (OPEN, CLOSE, BAR):  # the script goes on the bracket: the pairing writes it after the bracket
        return Piece(piece.kind, piece.text + "\0" + suffix)
    base = piece.text or "{}"
    kind = piece.kind if piece.kind in (FUNC, NUM) else ORD
    return Piece(kind, braced(base) + suffix)
