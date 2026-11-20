#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of Chuyển TeX ⇄ công thức (org.hst.office.vi:TexToggle) in a real HST Writer (headless, own profile).

Usage (Linux: start the office through tests/runtime/no-hst-telemetry.sh):
    python3 tests/runtime/check-tex-toggle.py --soffice PATH [--out DIR] [--port 2393]

A new document holds every snippet of tests/fixtures/tex-toggle/exam-snippets.json in a sentence ("Câu 1. Tính
$…$ với …"), some at 14 pt, a few as display math ($$…$$ alone and in a sentence, \\[…\\]), one in a table cell, and
the snippets that must fail. The command runs on the office's main thread, as from the menu, with nothing selected:
  - every snippet becomes a formula with the expected formula text, its span kept as its description, the
    paragraph's font size, its baseline on the text baseline; display math alone in a centred paragraph;
  - the text around keeps its font size in every paragraph; ^\\circ is a degree sign; inline \\int and \\sum keep
    their limits beside the sign (display math: above and below);
  - the failing snippets stay as they were, highlighted;
  - one undo step gives back the text exactly; redo converts again;
  - a selected formula turns back into its exact span;
  - saved as .docx, every formula is a Word equation (m:oMath) and no formula holds an error mark; reopened, the
    formulas are there and, all selected, turn back into LaTeX that converts again (the MathML path);
  - page 1 before and after as PNG, and the whole document as PDF, in --out (before.png/.pdf, after.png/.pdf).
Exit 1 when a check fails.
"""
import argparse
import faulthandler
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import headless_office  # noqa: E402
from tex_toggle_check_helpers import (CENTER, HIGHLIGHT, ROWS, body_text, build, corpus, dispatch, formulas,  # noqa: E402
                                      on_main, png, quit_office, record, text_sizes)
from hst_office import tex_to_starmath  # noqa: E402  (importable once the helpers set the path)


def check_converted(doc, expected, failing):
    found = formulas(doc)
    by_span = {f.Description: f for f in found}
    record("every snippet became a formula", len(found) == len(expected) + 1, (len(found), len(expected) + 1))
    wrong = [span for span, (starmath, _, _) in expected.items()
             if span.replace("\n", " ") not in by_span or by_span[span].getEmbeddedObject().Formula != starmath]
    record("formula text as expected", not wrong, wrong[:3])
    sizes = [span for span, (_, size, _) in expected.items()
             if span in by_span and by_span[span].getEmbeddedObject().BaseFontHeight != round(size)]
    record("formula keeps the paragraph font size", not sizes, sizes[:3])
    baseline = [f.Description for f in found
                if f.VertOrient != 0 or f.VertOrientPosition != -int(f.getEmbeddedObject().BaseLine)]
    record("formula on the text baseline", not baseline, baseline[:3])
    display = []
    for span, (_, _, is_display) in expected.items():
        if not is_display or span not in by_span:
            continue
        anchor = by_span[span].getAnchor()
        cursor = anchor.getText().createTextCursorByRange(anchor)
        cursor.gotoStartOfParagraph(False)
        cursor.gotoEndOfParagraph(True)
        if cursor.getString().strip() not in ("", "￼") or cursor.getPropertyValue("ParaAdjust") != CENTER:
            display.append(span)
    record("display math alone in a centred paragraph", not display, display)
    text = body_text(doc)
    kept = [span for span in failing if span not in text]
    record("failing snippets stay as text", not kept, kept)
    search = doc.createSearchDescriptor()
    unlit = []
    for span in failing:
        search.setSearchString(span)
        hit = doc.findFirst(search)
        if hit is None or hit.getPropertyValue("CharHighlight") != HIGHLIGHT:
            unlit.append(span)
    record("failing snippets highlighted", not unlit, unlit)
    rings = [f.Description for f in found if "^{circ}" in f.getEmbeddedObject().Formula]
    record("degrees are degree signs, not small rings", not rings and any(
        '"°"' in f.getEmbeddedObject().Formula for f in found), rings)
    inline_tall = []
    for f in found:
        formula, inline = f.getEmbeddedObject().Formula, not f.Description.startswith(("$$", "\\["))
        if inline and re.search(r"\b(int|sum|prod) from", formula):
            inline_tall.append(f.Description)
        height = f.getEmbeddedObject().BaseFontHeight * 2540 / 72
        if inline and re.search(r"\b(int|sum)_", formula) and not re.search(r"over|matrix|stack", formula) \
                and f.Size.Height > 2.2 * height:
            inline_tall.append((f.Description, f.Size.Height, round(height)))
    record("inline integrals and sums keep their limits beside the sign", not inline_tall, inline_tall)


def check_docx(office, doc, out, count):
    path = os.path.join(out, "tex-toggle.docx")
    doc.storeToURL(office.url(path), headless_office.props(FilterName="MS Word 2007 XML"))
    with zipfile.ZipFile(path) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    equations = len(re.findall(r"<m:oMath[ >]", xml))
    record("docx: every formula is a Word equation", equations == count, (equations, count))
    record("docx: no formula holds an error mark", "¿" not in xml)
    return path


def check_reopened(office, path, count, failing):
    doc = office.desktop.loadComponentFromURL(office.url(path), "_blank", 0,
                                              headless_office.props(Hidden=True, OnMainThread=True))
    try:
        found = len(on_main(office, lambda: formulas(doc)))
        record("docx reopened: formulas there", found == count, found)

        def select_all_and_toggle():
            cursor = doc.getCurrentController().getViewCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            dispatch(office, doc)
        on_main(office, select_all_and_toggle)
        left = len(on_main(office, lambda: formulas(doc)))
        record("docx reopened: all selected formulas turned into LaTeX", left == 0, left)
        text = on_main(office, lambda: body_text(doc))
        spans = [s for s in re.findall(r"\$\$.+?\$\$|\$[^$]+\$", text) if s not in failing]
        bad = []
        for span in spans:
            body = span.strip("$")
            try:
                tex_to_starmath.convert(body)
            except tex_to_starmath.TexError as error:
                bad.append((span, str(error)))
        record("docx reopened: LaTeX written back converts again", spans and not bad, (len(spans), bad[:3]))
    finally:
        on_main(office, lambda: doc.close(True))



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "tex-toggle"))
    parser.add_argument("--port", type=int, default=2393)
    args = parser.parse_args()
    faulthandler.dump_traceback_later(900, exit=True)  # a hang shows where it is
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    office = headless_office.Office(args.soffice, out, args.port)
    try:
        data = corpus()
        doc = office.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0,
                                                  headless_office.props(Hidden=True, OnMainThread=True))
        expected, failing, cell_span = on_main(office, lambda: build(doc, data))
        before = on_main(office, lambda: body_text(doc))
        sizes_before = on_main(office, lambda: text_sizes(doc))
        on_main(office, lambda: png(office, doc, os.path.join(out, "before.png")))
        undo = doc.getUndoManager()
        on_main(office, lambda: dispatch(office, doc))
        on_main(office, lambda: png(office, doc, os.path.join(out, "after.png")))
        sizes_after = on_main(office, lambda: text_sizes(doc))
        changed = {k: (sizes_before[k], sizes_after.get(k)) for k in sizes_before if sizes_after.get(k) != sizes_before[k]}
        record("text keeps its font size in every paragraph", len(sizes_before) >= 40 and not changed, changed)
        record("cell span converted", cell_span not in on_main(office, lambda: body_text(doc)))
        on_main(office, lambda: check_converted(doc, expected, failing))
        titles = undo.getAllUndoActionTitles()
        record("one undo step", titles[0] == "Chuyển TeX ⇄ công thức" and titles[1] != titles[0], titles[:2])
        on_main(office, undo.undo)
        record("undo gives the text back", on_main(office, lambda: body_text(doc)) == before
               and not on_main(office, lambda: formulas(doc)), "")
        on_main(office, undo.redo)
        count = len(on_main(office, lambda: formulas(doc)))
        record("redo converts again", count == len(expected) + 1, count)
        one = on_main(office, lambda: next(f for f in formulas(doc) if f.Description.startswith("$")
                                           and not f.Description.startswith("$$")))
        span = on_main(office, lambda: one.Description)

        def select_and_toggle():
            doc.getCurrentController().select(one)
            dispatch(office, doc)
        on_main(office, select_and_toggle)
        record("selected formula turns back into its span", len(on_main(office, lambda: formulas(doc))) == count - 1
               and span in on_main(office, lambda: body_text(doc)), span)
        on_main(office, undo.undo)
        path = on_main(office, lambda: check_docx(office, doc, out, count))
        on_main(office, lambda: doc.close(True))
        check_reopened(office, path, count, failing)
    finally:
        quit_office(office)
    failed = [name for name, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
