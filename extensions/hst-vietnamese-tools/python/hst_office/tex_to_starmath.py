# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: LaTeX math (the body of a $…$ span) to the formula language of HST Công thức (no UNO).

convert(tex) returns the formula text or raises TexError; a span that cannot be converted stays text. The reader
(tex_latex_reader) walks the LaTeX once, piece by piece (letters, numbers, symbols, commands with their arguments,
groups, \\left…\\right, environments); tex_starmath_pieces joins the pieces. Letter runs that are formula words (in,
or, sin without a backslash) are written letter by letter. The command tables are in tex_starmath_symbols."""
from .tex_latex_reader import Reader
from .tex_starmath_pieces import TexError, join

__all__ = ("TexError", "convert")


def convert(tex, display=False):
    """The formula text for the LaTeX math tex. Inline (display False), the limits of \\sum and \\int go beside the
    sign, as in a line of text; in display math, above and below it. \\lim keeps its limit below in both."""
    reader = Reader(tex, display)
    pieces, stop = reader.sequence(())
    if stop is not None:
        raise TexError("unexpected %s" % stop)
    text = join(pieces)
    if not text.strip():
        raise TexError("empty")
    return text
