# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư, Word fields: reading a Word field instruction ("IF { MERGEFIELD Giới_tính } = "Nam" "Ông" "Bà"") into a
Field: its type and its tokens, a token being literal text and nested Fields, quoted or not. Pure Python
(mail_merge_word_fields evaluates the result)."""
import re
import unicodedata

_KEY = re.compile(r"[\W_]+", re.UNICODE)


class Field:
    def __init__(self, kind, tokens):
        self.kind, self.tokens = kind, tokens  # tokens: [(parts, quoted)], parts: str or Field

    @property
    def arguments(self):
        """Tokens before the first switch (switch arguments are not arguments)."""
        result = []
        for token in self.tokens:
            if _is_switch(token):
                break
            result.append(token)
        return result

    def switches(self):
        """[(switch letter, argument token or None)] in order."""
        found, index = [], 0
        while index < len(self.tokens):
            token = self.tokens[index]
            if _is_switch(token):
                argument = None
                if index + 1 < len(self.tokens) and not _is_switch(self.tokens[index + 1]):
                    argument, index = self.tokens[index + 1], index + 1
                found.append((_plain(token)[1:2], argument))
            index += 1
        return found


def _plain(token):
    return "".join(p for p in token[0] if isinstance(p, str))


def _is_switch(token):
    parts, quoted = token
    return not quoted and len(parts) == 1 and isinstance(parts[0], str) and parts[0].startswith("\\")


def is_word_code(column):
    """A column that holds a Word instruction (the DOCX import names such fields' columns so)."""
    head = column.lstrip().upper()
    return head.startswith("MERGEFIELD ") or head.startswith("IF ")


def name_key(name):
    """Word writes "Họ và tên" as "Họ_và_tên"; both give the same key."""
    return _KEY.sub("_", unicodedata.normalize("NFC", str(name)).casefold()).strip("_")


def parse(code):
    """The Field of an instruction ("IF { MERGEFIELD x } = …"); ValueError when it cannot be read."""
    field, index = _parse_body(code, 0)
    if index != len(code):
        raise ValueError("unbalanced braces")
    return field


def _parse_body(text, index):
    """(Field, index after its closing brace or at the end)."""
    tokens, parts, quoted, in_quotes = [], [], False, False
    current = ""

    def flush():
        nonlocal parts, current, quoted
        if current:
            parts.append(current)
        if parts or quoted:
            tokens.append((parts, quoted))
        parts, current, quoted = [], "", False
    while index < len(text):
        char = text[index]
        if char == "{":
            if current:
                parts.append(current)
                current = ""
            nested, index = _parse_body(text, index + 1)
            parts.append(nested)
            continue
        if char == "}" and not in_quotes:
            flush()
            return _field(tokens), index + 1
        if char == '"':
            in_quotes, quoted = not in_quotes, True
        elif char == "\\" and in_quotes and index + 1 < len(text) and text[index + 1] in '"\\':
            current += text[index + 1]
            index += 1
        elif char.isspace() and not in_quotes:
            flush()
        else:
            current += char
        index += 1
    flush()
    return _field(tokens), index


def _field(tokens):
    kind = _plain(tokens[0]).upper() if tokens else ""
    return Field(kind, tokens[1:])


def names_text(code):
    """How a field shows without a recipient: <Lương> for a MERGEFIELD, the condition with «names» for an IF."""
    try:
        field = parse(code)
    except ValueError:
        return "<%s>" % code
    if field.kind == "MERGEFIELD" and field.arguments:
        return "<%s>" % _plain(field.arguments[0])

    def show(token):
        text = "".join(p if isinstance(p, str) else "«%s»" % _plain(p.arguments[0]) if p.kind == "MERGEFIELD"
                       and p.arguments else "{%s}" % p.kind for p in token[0])
        return '"%s"' % text if token[1] else text
    return "<%s %s>" % (field.kind, " ".join(show(t) for t in field.arguments))


def merge_names(code):
    """Names of the MERGEFIELDs an instruction reads (for checks)."""
    try:
        field = parse(code)
    except ValueError:
        return []
    found = []

    def walk(node):
        if node.kind == "MERGEFIELD" and node.arguments:
            found.append(_plain(node.arguments[0]))
        for parts, _quoted in node.tokens:
            for part in parts:
                if isinstance(part, Field):
                    walk(part)
    walk(field)
    return found
