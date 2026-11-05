# SPDX-License-Identifier: AGPL-3.0-only
"""Paragraph roles of the document body (pure logic): what a line is decides how it looks.

A line of a skeleton (data/vietnamese/skeletons-*.json) or of the wizard's body field is classified the same way, so an
installed template and a typed document come out alike. `@role text` in a skeleton names the role explicitly.
"""
import re

ARTICLE = re.compile(r"^(Điều\s+(?:\d+|\.\.\.|…|\[[^\]]*\])\s*\.?)(\s.*)?$", re.S)
BASIS = re.compile(r"^(Căn cứ|Theo đề nghị|Xét đề nghị)\b")
RESOLVE = re.compile(r"^(QUYẾT ĐỊNH|QUYẾT NGHỊ|CHỈ THỊ|KẾT LUẬN)\s*:?$")
EXPLICIT = re.compile(r"^@([a-zA-Z]+)\s+(.*)$", re.S)


def run(text, size, **extra):
    return {"text": text, "size": size, "bold": False, "italic": False, **extra}


def para(runs, align="center", **extra):
    return {"type": "paragraph", "align": align, "runs": runs, **extra}


def lines_of(text):
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def classify(line, seen_basis=False):
    """(role, text) of one body line; a capitals line before the first basis is the issuing authority (form 1.2)."""
    explicit = EXPLICIT.match(line)
    if explicit:
        return explicit.group(1), explicit.group(2)
    if BASIS.match(line):
        return "basis", line
    if RESOLVE.match(line):
        return "resolve", line
    if ARTICLE.match(line):
        return "article", line
    if not seen_basis and line == line.upper() and any(c.isalpha() for c in line):
        return "authority", line
    return "body", line


def _body_format(T, **extra):
    return {"indent_first_mm": T["bodyFirstLineIndentMm"], "spacing_after_pt": T["paragraphSpacingPt"],
            "line_spacing": T["lineSpacing"], **extra}


def _article(line, T):
    match = ARTICLE.match(line)
    return [run(match.group(1), T["body"], bold=True)] + ([run(match.group(2), T["body"])] if match.group(2) else [])


def body_blocks(lines, T):
    """Paragraph blocks of the body lines."""
    blocks, seen = [], False
    for line in lines:
        role, text = classify(line, seen)
        seen = seen or role == "basis"
        if role == "basis":
            blocks.append(para([run(text, T["body"], italic=True)], "justify", role="Basis", **_body_format(T)))
        elif role in ("authority", "resolve"):
            blocks.append(para([run(text, T["body"], bold=True)], "center", role=role.capitalize(), spacing_before_pt=6,
                               spacing_after_pt=T["paragraphSpacingPt"], keep_with_next=True))
        elif role == "article":
            blocks.append(para(_article(text, T), "justify", role="Article", **_body_format(T)))
        else:
            blocks.append(para([run(text, T["body"])], "justify", role="Body", **_body_format(T)))
    return blocks
