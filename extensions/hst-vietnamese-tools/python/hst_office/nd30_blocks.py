# SPDX-License-Identifier: AGPL-3.0-only
"""Paragraph roles of the document body (pure logic): what a line is decides how it looks.

A line of a skeleton (data/vietnamese/skeletons-*.json) or of the wizard's body field is classified the same way, so an
installed template and a typed document come out alike. `@role text` in a skeleton names the role explicitly; a skeleton
item with a "table" key is a ruled table of an office form.
"""
import re

ARTICLE = re.compile(r"^(Điều\s+(?:\d+|\.\.\.|…|\[[^\]]*\])\s*\.?)(\s.*)?$", re.S)
BASIS = re.compile(r"^-?\s*(Căn cứ|Theo đề nghị|Xét đề nghị)\b")
RESOLVE = re.compile(r"^(QUYẾT ĐỊNH|QUYẾT NGHỊ|CHỈ THỊ|KẾT LUẬN)\s*:?$")
CHAPTER = re.compile(r"^(Phần|Chương|Mục|Tiểu mục)\s+\S+$")
ANNEX = re.compile(r"^Phụ lục(\s+[IVXLCDM\d]+)?$")
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
    if ANNEX.match(line):
        return "annex", line
    if CHAPTER.match(line):
        return "chapter", line
    if ARTICLE.match(line):
        return "article", line
    if line == line.upper() and any(c.isalpha() for c in line) and not re.match(r"^[IVX\d]+\.", line):
        return ("chapterName" if seen_basis else "authority"), line
    return "body", line


def _text_format(T, **extra):
    spacing = {"line_exact_pt": T["lineExactPt"]} if T.get("lineExactPt") else {"line_spacing": T["lineSpacing"]}
    return {"spacing_after_pt": T["paragraphSpacingPt"], **spacing, **extra}


def _body_format(T, **extra):
    return _text_format(T, indent_first_mm=T["bodyFirstLineIndentMm"], **extra)


def _article(line, T, whole_bold):
    match = ARTICLE.match(line)
    if whole_bold and not line.rstrip().endswith((".", ";", ":")):  # the name of an article; a sentence stays upright
        return [run(line, T["body"], bold=True)]
    return [run(match.group(1), T["body"], bold=True)] + ([run(match.group(2), T["body"])] if match.group(2) else [])


def _table(table, T):
    """A ruled form table: bold header row, the (1) (2) column numbers of the annex forms, then the rows."""
    size = 12
    cell = lambda text, **k: [para([run(text, size, **k)], "center" if k.get("bold") else "left", role="TableText")]
    rows = [{"cells": [cell(h, bold=True) for h in table["header"]]}]
    if table.get("numbered"):
        rows.append({"cells": [[para([run("(%d)" % (i + 1), size)], role="TableText")] for i in range(len(table["header"]))]})
    rows += [{"cells": [cell(text) for text in row]} for row in table["rows"]]
    return {"type": "grid", "name": "Form", "widthsPct": table["widthsPct"], "rows": rows, "borders": True, "repeatHeader": True, "spacing_after_pt": 6}


def body_blocks(lines, d):
    """Paragraph and table blocks of the body lines, by the rules of the profile `d`."""
    T = d["typography"]
    blocks, seen = [], False
    for line in lines:
        if isinstance(line, dict):
            blocks.append(_table(line["table"], T))
            continue
        role, text = classify(line, seen)
        seen = seen or role == "basis"
        blocks += _role_blocks(role, text, d, T)
    return blocks


def _role_blocks(role, text, d, T):
    if role == "basis":
        return [para([run(text, T["body"], italic=not d.get("basisPlain"))], "justify", role="Basis", **_body_format(T))]
    if role in ("authority", "resolve", "chapter", "chapterName"):
        return [para([run(text, T["body"], bold=True)], "center", role=role.capitalize(), spacing_before_pt=6 if role in ("authority", "resolve") else 0,
                     spacing_after_pt=T["paragraphSpacingPt"] if role in ("authority", "resolve", "chapterName") else 0, keep_with_next=True)]
    if role == "annex":
        return [para([run(text, T["body"], bold=True)], "center", role="AnnexTitle", spacing_after_pt=T["paragraphSpacingPt"], keep_with_next=True, new_section=True)]
    if role == "article":
        return [para(_article(text, T, d.get("articleTitleBold")), "justify", role="Article", **_body_format(T))]
    if role == "center":
        return [para([run(text, T["body"])], "center", role="CenterLine", **_text_format(T))]
    if role == "plain":
        return [para([run(text, T["body"])], "justify", role="Body", **_body_format(T, spacing_after_pt=2))]
    if role == "label":
        head, _, note = text.partition("|")
        return [para([run(head + " ", T["body"], bold=True), run(note, T["body"], italic=True)], "left", role="FormLabel", **_body_format(T, spacing_after_pt=2))]
    if role == "signRight":
        date, title, hint = text.split("|")
        common = {"indent_left_mm": 55, "keep_with_next": True}
        return [para([run(date, T["placeDate"], italic=True)], "center", role="FormSignDate", spacing_before_pt=12, **common),
                para([run(title, T["signerName"], bold=True)], "center", role="Signer", **common),
                para([run(hint, T["signerName"], italic=True)], "center", role="FormSignHint", indent_left_mm=55)]
    return [para([run(text, T["body"])], "justify", role="Body", **_body_format(T))]
