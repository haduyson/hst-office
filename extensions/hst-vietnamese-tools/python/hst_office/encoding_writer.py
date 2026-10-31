# SPDX-License-Identifier: AGPL-3.0-only
"""Convert legacy-encoded Writer text to Unicode per text portion (formatting run), as ONE undo step.

Only portions of type "Text" are rewritten; fields, footnote anchors, redline markers, bookmarks and other
portion types are skipped and counted. The new text is inserted at the end of the old portion, inheriting its
character attributes, and the old text is then deleted (setString would reset bold/italic/size). Runs whose
font is a legacy one (.VnTime, VNI-Times ...) get a Unicode font so the result is legible. Refused before
any write: read-only documents, tracked changes, no/multiple/non-text selections, protected sections.
"""
from .encoding import Converter, font_policy
from .undo import undo_step


def check_selection(doc, selection):
    """Return (range_or_None, reasons). Reasons are machine-readable strings."""
    reasons = []
    if doc.isReadonly():
        reasons.append("read-only")
    if doc.RecordChanges or doc.getRedlines().hasElements():
        reasons.append("tracked-changes")
    rng = None
    if selection is None or not selection.supportsService("com.sun.star.text.TextRanges"):
        reasons.append("unsupported-selection")
    elif selection.getCount() != 1:
        reasons.append("multiple-selections")
    else:
        rng = selection.getByIndex(0)
        if not rng.getString():
            reasons.append("no-selection")
    return (rng if not reasons else None), reasons


def _paragraphs(rng):
    enum = rng.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def collect(rng):
    """Snapshot of convertible portions: ({'range','text','font'}...), skipped counts, protected flag."""
    items, skipped, protected = [], {"fields": 0, "tables": 0, "other": 0}, False
    for para in _paragraphs(rng):
        if not para.supportsService("com.sun.star.text.Paragraph"):
            skipped["tables"] += 1
            continue
        section = para.TextSection if para.supportsService("com.sun.star.text.TextContent") and para.TextSection else None
        protected = protected or bool(section is not None and section.IsProtected)
        portions = para.createEnumeration()
        while portions.hasMoreElements():
            portion = portions.nextElement()
            kind = portion.TextPortionType
            if kind == "Text":
                items.append({"range": portion, "text": portion.getString(), "font": portion.CharFontName})
            elif kind in ("TextField", "Footnote", "Annotation", "ReferenceMark", "DocumentIndexMark", "InContentMetadata"):
                skipped["fields"] += 1
            else:
                skipped["other"] += 1
    return items, skipped, protected


def plan(items, encoding_key, honour_upper_font=True):
    """Compute replacements without touching the document. Returns (rows, totals)."""
    conv = Converter(encoding_key)
    rows, totals = [], {"converted": 0, "unmapped": 0, "skipped_unicode": 0}
    for it in items:
        upper, new_font = font_policy(encoding_key, it["font"])
        new_text, stats = conv.convert(it["text"], upper=upper and honour_upper_font)
        totals["converted"] += stats["converted"]
        totals["unmapped"] += stats["unmapped"]
        totals["skipped_unicode"] += 1 if stats["skipped_unicode"] else 0
        rows.append({**it, "new": new_text, "new_font": new_font})
    return rows, totals


def snapshot(items):
    return [(i["text"], i["font"]) for i in items]


def rewrite_portion(row):
    """Replace one planned portion in place, keeping its character attributes; swap a legacy font for a Unicode one."""
    text = row["range"].getText()
    if row["new"] == row["text"]:  # same text: only swap the legacy font for a Unicode one
        same = text.createTextCursorByRange(row["range"])
        same.CharFontName = row["new_font"]
        return
    end = text.createTextCursorByRange(row["range"].getEnd())
    text.insertString(end, row["new"], False)  # inherits the old run's character attributes
    old = text.createTextCursorByRange(row["range"].getStart())
    old.goRight(len(row["text"]), True)
    old.setString("")
    if row["new_font"]:
        fresh = text.createTextCursorByRange(old.getStart())
        fresh.goRight(len(row["new"]), True)
        fresh.CharFontName = row["new_font"]


def apply(doc, rng, encoding_key, expected_snapshot, undo_title=None):
    """Re-collect, verify the selection still matches the previewed snapshot, then convert in one undo step."""
    items, _, protected = collect(rng)
    if protected:
        return {"blockers": ["protected-section"]}
    if snapshot(items) != expected_snapshot:
        return {"blockers": ["content-changed"]}
    rows, totals = plan(items, encoding_key)
    changed = [r for r in rows if r["new"] != r["text"] or r["new_font"]]
    with undo_step(doc, undo_title or "Convert %s to Unicode" % encoding_key):
        for row in reversed(changed):  # back to front: earlier ranges are unaffected by later replacements
            rewrite_portion(row)
    return {"blockers": [], "changed_portions": sum(r["new"] != r["text"] for r in changed), **totals}
