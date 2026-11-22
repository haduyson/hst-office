# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức: where the LaTeX math spans are in a piece of text (no UNO here).

Delimiters, as AI tools and LaTeX write them:
  - inline: $…$ and \\(…\\);
  - display (its own paragraph, centred): $$…$$ and \\[…\\].
A backslash escapes the next character, so \\$ is a dollar sign and never opens or closes a span. A single $ follows
the usual Markdown/Pandoc rule, so prices such as "5$ và 7$" stay text: the opening $ is followed by a non-space,
the closing $ is preceded by a non-space and not followed by a digit. Inline spans end at the paragraph's end
("\\n"); display spans may run over several paragraphs. An opening delimiter without its closing one is no span.
"""
from collections import namedtuple

Span = namedtuple("Span", "start end body display")  # text[start:end] is the whole span, delimiters included

PAIRS = (("$$", "$$", True), ("\\[", "\\]", True), ("\\(", "\\)", False), ("$", "$", False))


def _closing(text, index, close, display):
    """Index of the closing delimiter at or after index, or -1. Backslash escapes are skipped."""
    while index < len(text):
        char = text[index]
        if char == "\n" and not display:
            return -1
        if text.startswith(close, index) and (close != "$" or _closes_dollar(text, index)):
            return index
        index += 2 if char == "\\" else 1
    return -1


def _closes_dollar(text, index):
    before = text[index - 1] if index else " "
    after = text[index + 1] if index + 1 < len(text) else " "
    return not before.isspace() and not after.isdigit() and after != "$"


def find_spans(text):
    """[Span] in text order; spans never overlap."""
    spans = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in "$\\":
            index += 1
            continue
        for open_, close, display in PAIRS:
            if not text.startswith(open_, index):
                continue
            body_start = index + len(open_)
            if open_ == "$" and (body_start >= len(text) or text[body_start].isspace() or text[body_start] == "$"):
                continue
            end = _closing(text, body_start, close, display)
            if end < 0 or end == body_start:
                continue
            spans.append(Span(index, end + len(close), text[body_start:end], display))
            index = end + len(close)
            break
        else:
            index += 2 if char == "\\" else 1
    return spans


def wrap(tex, display):
    """The text a formula turns back into: inline \\(…\\) is written as $…$, display as $$…$$ (the forms AI tools and
    MathType's TeX toggle write)."""
    return ("$$%s$$" if display else "$%s$") % tex
