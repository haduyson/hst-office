# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức: the LaTeX commands with arguments (fractions, roots, accents, fonts, text, \\left…\\right,
environments) for tex_to_starmath. command(reader, name) reads the command's arguments from the reader and returns
its pieces; an unknown command raises TexError, so the span stays text."""
from . import tex_starmath_symbols as sym
from .tex_starmath_pieces import (BAR, BIN, BRACKET_COMMANDS, CLOSE, FUNC, LIMFUNC, MID, OP, OPEN, ORD, REL, SPACE,
                                  Piece, TexError, join, quote)

FRACTIONS = ("frac", "dfrac", "tfrac", "cfrac")
BINOMIALS = ("binom", "dbinom", "tbinom")
SKIPPED_ARGUMENT = ("label", "hspace", "hspace*", "vspace", "vspace*")


def command(reader, name):
    simple = _symbol(name)
    if simple is not None:
        return simple
    if name in sym.IGNORED:
        return []
    if name in FRACTIONS:
        top, bottom = reader.argument(), reader.argument()
        return [Piece(ORD, "{{%s} over {%s}}" % (top, bottom))]
    if name in BINOMIALS:
        top, bottom = reader.argument(), reader.argument()
        return [Piece(ORD, "{left( binom{%s}{%s} right)}" % (top, bottom))]
    if name == "sqrt":
        index = reader.optional()
        body = reader.argument()
        return [Piece(ORD, "nroot{%s}{%s}" % (index, body) if index else "sqrt{%s}" % body)]
    if name in sym.ACCENT:
        return [Piece(ORD, "%s{%s}" % (sym.ACCENT[name], reader.argument()))]
    if name in ("overset", "stackrel", "underset"):
        mark, base = reader.argument(), reader.argument()
        if mark == sym.ORDINARY["frown"] and name != "underset":  # \overset{\frown}{AB}: the arc AB
            return [Piece(ORD, "widearc{%s}" % base)]
        return [Piece(ORD, "{{%s} %s {%s}}" % (base, "csub" if name == "underset" else "csup", mark))]
    if name in ("xrightarrow", "xleftarrow"):
        below = reader.optional()
        above = reader.argument()
        return [Piece(ORD, "{{%s} %s {%s}}" % (above, name, below or ""))]
    if name in ("overbrace", "underbrace"):
        return _brace(reader, name)
    if name in sym.TEXT:
        return [Piece(ORD, sym.TEXT[name] + quote(_text(reader.raw_group())))]
    if name == "mathbb":
        return [Piece(ORD, " ".join(_double_struck(c) for c in reader.raw_group() if not c.isspace()))]
    if name in ("operatorname", "operatorname*"):
        word = reader.raw_group().strip()
        if not word.isalpha():
            raise TexError("operatorname")
        return [Piece(LIMFUNC if name.endswith("*") else FUNC, "func " + word)]
    if name in sym.FONT:
        return [Piece(ORD, "%s{%s}" % (sym.FONT[name], reader.argument()))]
    if name == "not":
        return [_negated(reader)]
    if name == "left":
        return [_fenced(reader)]
    if name == "middle":
        fence = _fence_token(reader)
        if fence not in ("|", "\\vert", "\\mid"):
            raise TexError("middle")
        return [Piece(MID, "mline")]
    if name == "begin":
        from .tex_to_starmath_environments import environment
        return [environment(reader, reader.raw_group().strip())]
    if name == "phantom":
        return [Piece(ORD, "phantom{%s}" % reader.argument())]
    if name in SKIPPED_ARGUMENT:
        reader.raw_group()
        return [Piece(SPACE, "~")] if name.startswith("hspace") else []
    raise TexError("\\" + name)


def _symbol(name):
    """[Piece] of a command without arguments, None for other commands."""
    if name in BRACKET_COMMANDS:
        key = BRACKET_COMMANDS[name]
        if key in ("|", "‖"):
            return [Piece(BAR, key)]
        return [Piece(OPEN if key in ("{", "langle", "lfloor", "lceil") else CLOSE, key)]
    if name in sym.ORDINARY:
        return [Piece(ORD, sym.ORDINARY[name])]
    if name in sym.BINARY:
        return [Piece(BIN, sym.BINARY[name])]
    if name in sym.RELATION:
        return [Piece(REL, sym.RELATION[name])]
    if name in sym.SPACE:
        return [Piece(SPACE, sym.SPACE[name])]
    if name in sym.BIG_OPERATOR:
        return [Piece(OP, sym.BIG_OPERATOR[name])]
    if name in sym.LIMIT_FUNCTION:
        return [Piece(LIMFUNC, "func " + name)]
    if name in sym.FUNCTION:
        return [Piece(FUNC, name if name in sym.OWN_FUNCTION else "func " + name)]
    return None


def _text(raw):
    """\\text{…} as shown: escaped characters lose their backslash, and ~ is a space."""
    out, index = [], 0
    while index < len(raw):
        char = raw[index]
        if char == "\\" and index + 1 < len(raw):
            following = raw[index + 1]
            if following.isalpha():
                raise TexError("command in \\text")
            out.append(" " if following in ", ;:" else following)
            index += 2
            continue
        out.append(" " if char == "~" else char)
        index += 1
    return "".join(out).replace("{", "").replace("}", "")


def _double_struck(letter):
    if letter in sym.DOUBLE_STRUCK:  # ℕ ℤ ℚ ℝ ℂ as letters: the formula's setN… glyphs sit cramped by relations
        glyph = sym.DOUBLE_STRUCK[letter]
        return glyph if ord(glyph) < 0x10000 else quote(glyph)
    raise TexError("mathbb")


def _negated(reader):
    kind, value = reader.token()
    key = value if kind == "char" else value
    if key not in sym.NEGATED:
        raise TexError("not")
    return Piece(REL, sym.NEGATED[key])


def _brace(reader, name):
    body = reader.argument()
    script = "^" if name == "overbrace" else "_"
    label = ""
    if reader.peek() == ("char", script):
        reader.token()
        label = reader.argument()
    return [Piece(ORD, "{{%s} %s {%s}}" % (body, name, label))]


def _fence_token(reader):
    kind, value = reader.token()
    if kind is None:
        raise TexError("missing fence")
    return value if kind == "char" else "\\" + value


def _fenced(reader):
    """\\left X … \\right Y, which may hold \\middle|."""
    opening = sym.OPEN_FENCE.get(_fence_token(reader))
    if opening is None:
        raise TexError("left")
    pieces, stop = reader.sequence(("right",))
    if stop != "right":
        raise TexError("\\left without \\right")
    closing = sym.CLOSE_FENCE.get(_fence_token(reader))
    if closing is None:
        raise TexError("right")
    return Piece(ORD, "{left %s %s right %s}" % (opening, join(pieces) or "{}", closing))
