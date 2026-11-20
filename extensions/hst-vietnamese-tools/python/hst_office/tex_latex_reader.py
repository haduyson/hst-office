# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: the LaTeX reader of tex_to_starmath. It walks the LaTeX once, piece by piece: tokens,
sequences up to a stop token, arguments, scripts and primes. Characters are read by tex_latex_characters, commands by
tex_to_starmath_commands."""
from . import tex_latex_characters as characters
from .tex_starmath_pieces import CLOSE, NEWLINE, ORD, OPEN, BAR, Piece, TexError, join


class Reader:
    """LaTeX to pieces. Whitespace separates tokens only, except inside \\text{…}."""

    def __init__(self, tex, display=False):
        self.s, self.i, self.display = tex, 0, display

    # tokens -------------------------------------------------------------------------------------------------
    def _skip_space(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def token(self):
        """("cmd", name) | ("char", c) | (None, None) at the end; consumed."""
        self._skip_space()
        if self.i >= len(self.s):
            return None, None
        char = self.s[self.i]
        if char != "\\":
            self.i += 1
            return "char", char
        start = self.i + 1
        end = start
        while end < len(self.s) and self.s[end].isascii() and self.s[end].isalpha():
            end += 1
        if end == start:
            if start >= len(self.s):
                raise TexError("lone backslash")
            end = start + 1
        elif end < len(self.s) and self.s[end] == "*":  # \operatorname*
            end += 1
        self.i = end
        return "cmd", self.s[start:end]

    def peek(self):
        saved = self.i
        try:
            return self.token()
        finally:
            self.i = saved

    def raw_group(self):
        """The text of a {…} argument as written (\\text, \\begin), braces balanced; a bare character also counts."""
        self._skip_space()
        if self.i >= len(self.s):
            raise TexError("missing argument")
        if self.s[self.i] != "{":
            kind, value = self.token()
            return value if kind == "char" else "\\" + value
        depth, start = 0, self.i + 1
        while self.i < len(self.s):
            char = self.s[self.i]
            if char == "\\":
                self.i += 2
                continue
            depth += {"{": 1, "}": -1}.get(char, 0)
            self.i += 1
            if depth == 0:
                return self.s[start:self.i - 1]
        raise TexError("unclosed {")

    # sequences ----------------------------------------------------------------------------------------------
    def sequence(self, stops):
        """(pieces, stop) up to a stop token: "}", "]", "&", "\\\\", "right", "end"; stop None at the end."""
        pieces = []
        while True:
            kind, value = self.peek()
            if kind is None:
                return pieces, None
            if (kind == "char" and value in stops) or (kind == "cmd" and value in stops):
                self.token()
                return pieces, value
            if kind == "char" and value in "}&]" and value not in stops:
                if value == "]":
                    self.token()
                    pieces.append(self.scripts(Piece(CLOSE, "]")))
                    continue
                raise TexError("unexpected %s" % value)
            if kind == "cmd" and value in ("right", "end"):
                raise TexError("unexpected \\%s" % value)
            if kind == "cmd" and value == "\\":
                self.token()
                self._skip_optional()
                pieces.append(Piece(NEWLINE, "newline"))
                continue
            pieces.extend(self.piece())

    def group_text(self, stop="}"):
        pieces, found = self.sequence((stop,))
        if found != stop:
            raise TexError("unclosed group")
        return join(pieces)

    def argument(self):
        """The formula text of one argument: a {group}, a command with its own arguments, or one character."""
        kind, value = self.peek()
        if kind is None:
            raise TexError("missing argument")
        if (kind, value) == ("char", "{"):
            self.token()
            return self.group_text()
        if kind == "char" and value.isdigit():  # \frac12: one digit each
            self.token()
            return value
        return join(self.piece(scripts=False))

    def _skip_optional(self):
        saved = self.i
        self._skip_space()
        if self.i < len(self.s) and self.s[self.i] == "[":
            end = self.s.find("]", self.i)
            if end > 0:
                self.i = end + 1
                return
        self.i = saved

    def optional(self):
        """The formula text of a [..] argument, or None."""
        self._skip_space()
        if self.i < len(self.s) and self.s[self.i] == "[":
            self.i += 1
            return self.group_text("]")
        return None

    # pieces -------------------------------------------------------------------------------------------------
    def scripts(self, piece):
        """The piece with the primes, ^ and _ that follow it; f' is written f′, beside the letter as MathType
        shows it."""
        sub = sup = None
        while True:
            kind, value = self.peek()
            if kind != "char" or value not in "^_'":
                break
            self.token()
            if value == "'":
                if sub is not None or sup is not None:
                    raise TexError("prime after a script")
                piece = Piece(ORD if piece.kind not in (OPEN, CLOSE, BAR) else piece.kind,
                              piece.text + ("\0" if piece.kind in (OPEN, CLOSE, BAR) else " ") + "′")
                continue
            if (value == "^" and sup is not None) or (value == "_" and sub is not None):
                raise TexError("double script")
            text = self.argument()
            if value == "^":
                sup = text
            else:
                sub = text
        if sub is None and sup is None:
            return piece
        return characters.with_scripts(piece, sub, sup, self.display)

    def piece(self, scripts=True):
        """[Piece] for the next token and its arguments (one piece, none for ignored commands)."""
        kind, value = self.token()
        if kind == "char":
            pieces = characters.character(self, value)
        else:
            pieces = self._command(value)
        if scripts and pieces:
            pieces[-1] = self.scripts(pieces[-1])
        elif scripts and self.peek()[1] in ("^", "_"):  # x^ after an ignored command: on an empty base
            pieces = [self.scripts(Piece(ORD, "{}"))]
        return pieces

    def _command(self, name):
        from . import tex_to_starmath_commands as commands
        return commands.command(self, name)


