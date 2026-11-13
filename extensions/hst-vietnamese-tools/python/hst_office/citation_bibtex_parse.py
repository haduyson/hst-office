# SPDX-License-Identifier: AGPL-3.0-only
"""BibTeX/BibLaTeX syntax: entries (@type{key, field = value, …} or with parentheses), @string macros, "#"
concatenation, nested braces, quoted values, month macros; @comment and @preamble are skipped. Values are returned
raw (LaTeX not decoded yet). Errors name the line and skip to the next "@". Pure Python (no uno)."""
import re

MONTHS = {m: str(i + 1) for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
_IDENT = re.compile(r"[A-Za-z0-9_:.+/'-]+")


class BibSyntaxError(ValueError):
    def __init__(self, message, position):
        super().__init__(message)
        self.position = position


class _Reader:
    def __init__(self, text, macros):
        self.text, self.pos, self.macros = text, 0, macros

    def skip(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos] == "%":  # comment to the end of the line
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end + 1
            else:
                break

    def peek(self):
        self.skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, chars):
        char = self.peek()
        if not char or char not in chars:
            raise BibSyntaxError("cần “%s” nhưng gặp “%s”" % (chars, char or "hết tệp"), self.pos)
        self.pos += 1
        return char

    def ident(self):
        self.skip()
        match = _IDENT.match(self.text, self.pos)
        if not match:
            raise BibSyntaxError("thiếu tên", self.pos)
        self.pos = match.end()
        return match.group(0)

    def braced(self):
        start, depth = self.pos, 0
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    return self.text[start + 1:self.pos - 1]
            self.pos += 1
        raise BibSyntaxError("ngoặc nhọn không đóng", start)

    def quoted(self):
        start, depth = self.pos, 0
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            depth += {"{": 1, "}": -1}.get(char, 0)
            if char == '"' and depth == 0:
                self.pos += 1
                return self.text[start + 1:self.pos - 1]
            self.pos += 1
        raise BibSyntaxError("dấu ngoặc kép không đóng", start)

    def value(self):
        parts = []
        while True:
            char = self.peek()
            if char == "{":
                parts.append(self.braced())
            elif char == '"':
                parts.append(self.quoted())
            else:
                name = self.ident()
                parts.append(self.macros.get(name.lower(), MONTHS.get(name.lower(), name)))
            if self.peek() != "#":
                return "".join(parts)
            self.pos += 1

    def fields(self, closing):
        result = {}
        while True:
            char = self.peek()
            if char == closing:
                self.pos += 1
                return result
            if char == ",":
                self.pos += 1
                continue
            name = self.ident().lower()
            self.expect("=")
            result[name] = self.value()


def line_of(text, position):
    return text.count("\n", 0, position) + 1


def entries(text):
    """([(entry type, key, {field: raw value}, line)], [warnings])."""
    macros, found, warnings = {}, [], []
    position = 0
    while True:
        at = text.find("@", position)
        if at < 0:
            break
        reader = _Reader(text, macros)
        reader.pos = at + 1
        try:
            kind = reader.ident().lower()
            opening = reader.expect("{(")
            closing = "}" if opening == "{" else ")"
            if kind in ("comment", "preamble"):
                reader.pos -= 1
                if opening == "{":
                    reader.braced()
                else:
                    reader.pos = text.find(")", reader.pos) + 1 or len(text)
            elif kind == "string":
                macros.update({k: v for k, v in reader.fields(closing).items()})
            else:
                key = reader.ident() if reader.peek() not in (",", closing) else ""
                found.append((kind, key, reader.fields(closing), line_of(text, at)))
            position = reader.pos
        except BibSyntaxError as exc:
            warnings.append("Dòng %d: bỏ qua mục BibTeX lỗi (%s)" % (line_of(text, exc.position), exc))
            position = at + 1
    return found, warnings
