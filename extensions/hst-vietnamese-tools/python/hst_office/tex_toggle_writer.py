# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức in HST Writer: LaTeX math spans in the text become HST Công thức formulas, and formulas
become LaTeX text again.

Scope: the selected text, or the whole document (body, tables, text frames) when nothing is selected. In selected
text each piece toggles: LaTeX spans become formulas and the formulas already there become LaTeX; a selected formula
turns back into LaTeX. With nothing selected only LaTeX becomes formulas.
  - Each span is read from the paragraph's text portions; a field, footnote or object inside a span makes it fail.
  - $…$ and \\(…\\) become a formula anchored as a character, on the text baseline, at the paragraph's font size;
    $$…$$ and \\[…\\] become a formula in a paragraph of its own, centred.
  - A formula keeps the span it came from as its description (alternative text). Turned back, it gets exactly that
    text again when its formula is still what that text gives; otherwise (edited, or not made by the toggle) the
    LaTeX is written from the formula's MathML (mathml_to_tex).
  - A span that cannot be converted stays as it was, highlighted yellow, and is counted as failed.
Everything is one undo step; a progress bar shows on long documents."""
import time
from collections import namedtuple

from . import tex_to_starmath
from .tex_toggle_formula import highlight, insert_formula, make_display, revert_formula, settle
from .tex_toggle_scan import find_work, selection_scope

Result = namedtuple("Result", "converted failed reverted kept")
PROGRESS_SECONDS = 0.5
PROGRESS_FROM = 20  # spans or formulas: below this the work is quick enough without a bar


def _progress(doc, text, count):
    try:
        indicator = doc.getCurrentController().getFrame().createStatusIndicator()
        indicator.start(text, count)
        return indicator
    except Exception:  # noqa: BLE001 - hidden documents and tests work without a progress bar
        return None


def _each(items, indicator):
    shown = time.monotonic()
    for index, item in enumerate(items):
        yield item
        if indicator is not None and time.monotonic() - shown >= PROGRESS_SECONDS:
            indicator.setValue(index + 1)
            shown = time.monotonic()


def _convert_spans(doc, spans, indicator, made):
    converted = failed = 0
    for cursor, span in _each(list(reversed(spans)), indicator):  # from the end: earlier offsets stay right
        try:
            starmath = tex_to_starmath.convert(span.body, span.display)
        except tex_to_starmath.TexError:
            starmath = None
        if cursor is None or starmath is None:
            failed += 1
            if cursor is not None:
                highlight(cursor)
            continue
        whole = cursor.getString()
        obj = insert_formula(doc, cursor, starmath, whole.replace("\n", " ") if span.display else whole)
        if span.display:
            make_display(obj)
        made.append(obj)
        converted += 1
    return converted, failed


def toggle(ctx, doc, controller, undo_title):
    """Result of the TeX toggle on the selection or the whole document, as one undo step."""
    from .undo import undo_step
    mode, scope = selection_scope(doc, controller)
    if mode == "object":
        spans, formulas = [], [scope]
    else:
        spans, formulas = find_work(scope)
    if mode == "document":
        formulas = []  # formulas turn back only when selected
    work = len(spans) + len(formulas)
    if not work:
        return Result(0, 0, 0, 0)
    indicator = _progress(doc, undo_title, work) if work >= PROGRESS_FROM else None
    converted = failed = reverted = kept = 0
    made = []
    try:
        with undo_step(doc, undo_title):
            doc.lockControllers()
            try:
                converted, failed = _convert_spans(doc, spans, indicator, made)
                for obj in _each(formulas, indicator):
                    if revert_formula(ctx, obj):
                        reverted += 1
                    else:
                        kept += 1
            finally:
                doc.unlockControllers()
            settle(ctx, made)
    finally:
        if indicator is not None:
            indicator.end()
    return Result(converted, failed, reverted, kept)
