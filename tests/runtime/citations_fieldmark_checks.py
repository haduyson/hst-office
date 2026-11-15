# SPDX-License-Identifier: AGPL-3.0-only
"""Checks on the sample document: result formatting, bibliography paragraphs, order, bulk update
in one Undo step, tracked changes, and what survives .docx/.odt save and reload."""
import json

import citations_docx_fields as docx_fields
import citations_fieldmark_sample as sample
from citations_fieldmark_uno import (BIBLIOGRAPHY_PREFIX, CITATION_PREFIX, paragraphs_of,
                                     portions_inside, reading_order, scan)


def by_id(fields):
    return {sample.citation_id(f.code): f for f in fields if f.code.startswith(CITATION_PREFIX)}


def check_formatting(rec, doc):
    """Results keep the font of the text around them; <i> and <sup> show; no paragraph added."""
    fields = by_id(scan(doc))
    for cid, _html, plain, italic, sup, _wrapper in sample.CITATIONS:
        field = fields.get(cid)
        if field is None:
            rec.check(f"format-{cid}", False, "field missing")
            continue
        parts = portions_inside(doc, field)
        surround, style = surrounding_font(doc, field.mark.getAnchor())
        fonts = {(p[1], p[2]) for p in parts}
        ok = "".join(p[0] for p in parts) == plain and fonts == {surround}
        ok = ok and (italic is None or any(p[0] == italic and p[3] == "ITALIC" for p in parts))
        ok = ok and (sup is None or any(p[0] == sup and p[4] > 0 for p in parts))
        rec.check(f"format-{cid}", ok, {"portions": parts, "surrounding": surround, "paragraph_style": style})
    styles = [p.ParaStyleName for p in paragraphs_of(doc.getText())]
    rec.check("format-paragraph-styles", styles[:2] == [sample.BODY_STYLE, "Standard"]
              and styles.count("Heading 1") == 1, styles)


def surrounding_font(doc, anchor):
    """(font, size) of the character before the field, or of the paragraph style when the field
    starts its paragraph (a footnote holding only the citation)."""
    cursor = anchor.getText().createTextCursorByRange(anchor.getStart())
    style = cursor.ParaStyleName
    if not cursor.isStartOfParagraph() and cursor.goLeft(1, True):
        return (cursor.CharFontName, cursor.CharHeight), style
    para_style = doc.getStyleFamilies().getByName("ParagraphStyles").getByName(style)
    return (para_style.CharFontName, para_style.CharHeight), style


def check_bibliography(rec, doc, set_style):
    bib = [f for f in scan(doc) if f.code.startswith(BIBLIOGRAPHY_PREFIX)]
    if len(bib) != 1:
        rec.check("bibliography-paragraphs", False, f"{len(bib)} bibliography fields")
        return
    paras = paragraphs_of(bib[0].mark.getAnchor())
    if set_style:  # the paste makes <p> "Text Body"; the extension sets its own style after it
        for para in paras:
            para.ParaStyleName = sample.BIB_STYLE
    styles = [p.ParaStyleName for p in paras]
    ok = bib[0].result == sample.bibliography_text() and len(paras) == len(sample.BIB_ENTRIES)
    rec.check("bibliography-paragraphs", ok and set(styles) == {sample.BIB_STYLE},
              {"result": bib[0].result, "styles": styles})


def check_order(rec, doc):
    fields = [f for f in scan(doc) if f.code.startswith(CITATION_PREFIX)]
    raw = [sample.citation_id(f.code) for f in fields]
    reading = [sample.citation_id(f.code) for f in reading_order(doc, fields)]
    rec.check("order-raw-footnote-first", raw[0] == "c5", raw)
    rec.check("order-reading", reading == sample.READING_ORDER, reading)


def check_bulk_update(rec, session):
    """All citations renumbered by one .uno:TextFormFields: one Undo step, which restores both
    results and codes; Redo brings the update back; formatting kept."""
    doc = session.doc
    before = [(f.code, f.result) for f in scan(doc, CITATION_PREFIX)]
    updates = [(code.replace('"v": 1', '"v": 1, "rev": 2', 1), "[9" + result[2:]) for code, result in before]
    undo_before = len(session.undo_titles())
    session.bulk_update(CITATION_PREFIX, updates)
    after = [(f.code, f.result) for f in scan(doc, CITATION_PREFIX)]
    rec.check("update-applied", after == updates, after[:2])
    rec.check("update-one-undo-step", len(session.undo_titles()) == undo_before + 1, session.undo_titles()[:2])
    fonts_ok = all(len({(p[1], p[2]) for p in portions_inside(doc, f)}) == 1 for f in scan(doc, CITATION_PREFIX))
    rec.check("update-keeps-font", fonts_ok, "")
    doc.getUndoManager().undo()
    undone = [(f.code, f.result) for f in scan(doc, CITATION_PREFIX)]
    rec.check("update-undo-results", [r for _, r in undone] == [r for _, r in before], [r for _, r in undone])
    rec.check("update-undo-codes", [c for c, _ in undone] == [c for c, _ in before],
              [c[:60] for c, _ in undone])
    doc.getUndoManager().redo()
    redone = [(f.code, f.result) for f in scan(doc, CITATION_PREFIX)]
    rec.check("update-redo", redone == updates, [c[:60] for c, _ in redone])
    doc.getUndoManager().undo()


def check_single_update(rec, session):
    """Editing the citation under the cursor: one Undo step restores code and result."""
    doc = session.doc
    field = by_id(scan(doc))["c2"]
    before = (field.code, field.result)
    session.view_cursor.gotoRange(field.mark.getAnchor().getStart(), False)
    session.view_cursor.goRight(3, False)
    new = (field.code.replace('"v": 1', '"v": 1, "edited": true', 1), "(Nguyễn Văn An, 2010, tr. 7)")
    count = len(session.undo_titles())
    session.update_at_cursor(CITATION_PREFIX, *new)
    after = (by_id(scan(doc))["c2"].code, by_id(scan(doc))["c2"].result)
    rec.check("single-update-applied", after == new and len(session.undo_titles()) == count + 1, after[1])
    doc.getUndoManager().undo()
    undone = (by_id(scan(doc))["c2"].code, by_id(scan(doc))["c2"].result)
    rec.check("single-update-undo-restores-code-and-result", undone == before, undone[1])


def check_tracked_changes(rec, session):
    """With change tracking on, the extension switches recording off around an update."""
    doc = session.doc
    doc.RecordChanges = True
    count = _redline_count(doc)
    fields = [(f.code, f.result.replace("[", "[0", 1)) for f in scan(doc, CITATION_PREFIX)]
    doc.RecordChanges = False
    session.bulk_update(CITATION_PREFIX, fields)
    doc.RecordChanges = True
    rec.check("tracked-changes-update-not-recorded", _redline_count(doc) == count, _redline_count(doc))
    session.bulk_update(CITATION_PREFIX, [(c, r.replace("[0", "[", 1)) for c, r in fields])
    rec.info("tracked-changes-update-if-recording-left-on", _redline_count(doc) - count)
    doc.getUndoManager().undo()
    doc.getUndoManager().undo()
    doc.RecordChanges = False


def _redline_count(doc):
    enum, count = doc.getRedlines().createEnumeration(), 0
    while enum.hasMoreElements():
        enum.nextElement()
        count += 1
    return count


def snapshot(doc):
    """{citationID: (code, result)} just before saving: what a reload must give back."""
    return {cid: (f.code, f.result) for cid, f in by_id(scan(doc)).items()}


def check_reloaded(rec, doc, label, reference):
    """After reload: every field with the same code (byte-exact) and the same result text."""
    fields = by_id(scan(doc))
    for cid, *_ in sample.CITATIONS:
        field = fields.get(cid)
        ok = field is not None and (field.code, field.result) == reference.get(cid)
        rec.check(f"{label}-{cid}", ok, None if field is None else {"result": field.result, "code_len": len(field.code)})
    check_bibliography(rec.prefixed(label), doc, set_style=False)


def check_docx_reader(rec, path, reference):
    """The .docx as another word processor reads it: codes, results, multi-paragraph field."""
    fields = docx_fields.docx_fields(path)
    got = {sample.citation_id(f["code"]): f for f in fields if f["code"].startswith(CITATION_PREFIX.strip())}
    for cid, _html, _plain, _i, _s, wrapper in sample.CITATIONS:
        field = got.get(cid)
        part = "word/footnotes.xml" if wrapper == "Footnote" else "word/document.xml"
        ok = field is not None and (field["code"], field["result"]) == reference.get(cid) and field["part"] == part
        rec.check(f"docx-xml-{cid}", ok, None if field is None else {k: field[k] for k in ("part", "result")})
    bib = [f for f in fields if f["code"].startswith(BIBLIOGRAPHY_PREFIX)]
    rec.check("docx-xml-bibliography", len(bib) == 1 and bib[0]["result"] == sample.bibliography_text()
              and bib[0]["paragraphs"] == len(sample.BIB_ENTRIES), bib[:1])
    visible = docx_fields.visible_text(path)
    rec.check("docx-xml-visible-text", "ADDIN" not in visible and "[1, tr. 314–315]" in visible
              and "(Nguyễn Văn An, 2010)" in visible, visible[:200])
    rec.info("docx-xml-code-bytes", json.dumps({cid: len(f["code"].encode()) for cid, f in got.items()}))
