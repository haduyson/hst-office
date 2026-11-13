# SPDX-License-Identifier: AGPL-3.0-only
"""HST citation fields in a Writer document (UNO): list them, insert them, write a refresh plan.

Fields are text fieldmarks of type UNHANDLED carrying their code as the parameter vnd.oasis.opendocument.field.code
(citation_codes). Proven on a build in tests/runtime/check-citations-fieldmarks.py (phase 01 of the plan):
- getTextFields() lists fieldmarks in raw node order: footnotes, endnotes, frames and headers come before the body.
  .uno:TextFormFields updates in that order, so updates are listed in it; numbering uses the reading order;
- every update gives every matching field both a code and a result (a missing code would wipe it);
- the update commands are one Undo step each (with hst-citation-fieldmarks.patch Undo restores codes too); two of
  them run inside one Undo context; tracked changes are paused around them (generated content, owner decision).
"""
import functools

from . import citation_codes as codes

UNHANDLED = "vnd.oasis.opendocument.field.UNHANDLED"
CODE_PARAM = "vnd.oasis.opendocument.field.code"
NOTE_SERVICES = ("com.sun.star.text.Footnote", "com.sun.star.text.Endnote", "com.sun.star.text.TextFrame")


def plain_html(text):
    """Plain text as field-result HTML (a field whose formatting is about to be rewritten anyway)."""
    import html
    return html.escape(text or "", quote=False)


def prop(name, value):
    import uno
    item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    item.Name, item.Value = name, value
    return item


def dispatch(ctx, doc, command, *args):
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    helper.executeDispatch(doc.getCurrentController().getFrame(), ".uno:" + command, "", 0, tuple(args))


def _code_of(mark):
    params = mark.getParameters()
    return params.getByName(CODE_PARAM) if params.hasByName(CODE_PARAM) else None


def scan(doc, foreign=False):
    """[{"index", "rank", "kind", "code", "result", "mark"}] of HST fields (and Zotero/Mendeley citations when
    ``foreign``) in raw order; ``rank`` is the reading position."""
    fields = []
    enum = doc.getTextFields().createEnumeration()
    while enum.hasMoreElements():
        mark = enum.nextElement()
        if mark.getImplementationName() != "SwXFieldmark" or mark.getFieldType() != UNHANDLED:
            continue
        code = _code_of(mark)
        kind = codes.kind_of(code)
        if kind in ("citation", "bibliography") or (foreign and kind == "foreign"):
            fields.append({"index": len(fields), "kind": kind, "code": code, "mark": mark,
                           "result": mark.getAnchor().getString()})
    for rank, field in enumerate(reading_order(doc, fields)):
        field["rank"] = rank
    return fields


def body_position(doc, rng):
    """A body text range standing for where a reader meets ``rng``: the range itself in body text and tables'
    anchors, the anchor of the footnote, endnote or frame holding it (nesting climbed); None in a header/footer."""
    body = doc.getText()
    for _ in range(8):
        text = rng.getText()
        if text is None or text == body:  # a footnote's anchor reports no text: it is in the body
            return rng
        if any(text.supportsService(name) for name in NOTE_SERVICES):
            rng = text.getAnchor()
            continue
        info = rng.getPropertySetInfo()
        table = rng.getPropertyValue("TextTable") if info.hasPropertyByName("TextTable") else None
        if table is None:
            return None
        rng = table.getAnchor()
    return None


def reading_order(doc, fields):
    text = doc.getText()
    keyed = [(body_position(doc, f["mark"].getAnchor()), f) for f in fields]

    def compare(a, b):
        if a[0] is None or b[0] is None:
            return (a[0] is not None) - (b[0] is not None) or a[1]["index"] - b[1]["index"]
        try:
            order = text.compareRegionStarts(a[0], b[0])  # 1: a first
        except Exception:  # noqa: BLE001 - not comparable: keep the raw order
            order = 0
        return -order if order else a[1]["index"] - b[1]["index"]
    return [f for _k, f in sorted(keyed, key=functools.cmp_to_key(compare))]


def insert_field(ctx, doc, code, html, wrapper=None):
    """A field at the view cursor through .uno:TextFormField (one Undo step); ``wrapper`` "Footnote" puts it in a
    new footnote (note styles)."""
    args = [prop("FieldType", UNHANDLED), prop("FieldCommand", code), prop("FieldResult", html)]
    if wrapper:
        args.append(prop("Wrapper", wrapper))
    dispatch(ctx, doc, "TextFormField", *args)


def _update_all(ctx, doc, prefix, updates):
    import uno
    seq = tuple((prop("FieldCommand", code), prop("FieldResult", html)) for code, html in updates)
    dispatch(ctx, doc, "TextFormFields", prop("FieldType", UNHANDLED), prop("FieldCommandPrefix", prefix),
             prop("Fields", uno.Any("[][]com.sun.star.beans.PropertyValue", seq)))


def apply_plan(ctx, doc, plan, undo_title, force=False):
    """Write a citation_refresh_plan result in one Undo step; returns True when something was written."""
    write_cites = plan["citations"] and (force or plan["citations_changed"])
    write_bib = plan["bibliography"] and (force or plan["bib_changed"])
    if not write_cites and not write_bib:
        return False
    from . import citation_doc_styles as styles
    undo = doc.getUndoManager()
    recording = doc.getPropertyValue("RecordChanges")
    undo.enterUndoContext(undo_title)
    try:
        if recording:
            doc.setPropertyValue("RecordChanges", False)
        if write_cites:
            _update_all(ctx, doc, codes.CITATION, plan["citations"])
        if write_bib:
            _update_all(ctx, doc, codes.BIBLIOGRAPHY, plan["bibliography"])
            for field in scan(doc):
                if field["kind"] == "bibliography":
                    styles.style_bibliography(doc, field["mark"], plan["bib_roles"], plan["hanging"])
    finally:
        if recording:
            doc.setPropertyValue("RecordChanges", True)
        undo.leaveUndoContext()
    return True


def field_at_cursor(doc, fields):
    """The field holding the view cursor strictly inside it (right before or after a field is not in it), or None."""
    cursor = doc.getCurrentController().getViewCursor()
    for field in fields:
        anchor = field["mark"].getAnchor()
        try:
            text = anchor.getText()
            if text.compareRegionStarts(anchor, cursor) > 0 and text.compareRegionEnds(anchor, cursor) < 0:
                return field
        except Exception:  # noqa: BLE001 - the cursor is in another text
            continue
    return None


def text_before_cursor(doc, fields=()):
    """The text typed before the view cursor: from the start of the paragraph, or from the end of the last of
    ``fields`` in that paragraph, so a citation result such as "[1]" is never read as typed ("" with a selection)."""
    cursor = doc.getCurrentController().getViewCursor()
    if not cursor.isCollapsed():
        return ""
    text = cursor.getText()
    probe = text.createTextCursorByRange(cursor.getStart())
    probe.gotoStartOfParagraph(True)
    typed = probe.getString()
    for field in fields:
        anchor = field["mark"].getAnchor()
        try:
            if text.compareRegionEnds(anchor, cursor) < 0:  # the field ends after the cursor
                continue
            after = text.createTextCursorByRange(anchor.getEnd())
            after.gotoRange(cursor.getStart(), True)
        except Exception:  # noqa: BLE001 - a field in another text (footnote, frame)
            continue
        between = after.getString()
        if "\n" not in between and len(between) < len(typed):
            typed = between
    return typed


def delete_before_cursor(doc, count):
    """Delete ``count`` characters before the view cursor (the typed "[3, tr. 15]")."""
    cursor = doc.getCurrentController().getViewCursor()
    probe = cursor.getText().createTextCursorByRange(cursor.getStart())
    probe.goLeft(count, True)
    probe.setString("")
