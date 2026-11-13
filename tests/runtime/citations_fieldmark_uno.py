# SPDX-License-Identifier: AGPL-3.0-only
"""UNO helpers for the citation fieldmark checks (tests/runtime/check-citations-fieldmarks.py).

A citation is a text fieldmark of type UNHANDLED whose code ("ADDIN HST_CITATION {json}") is the
fieldmark parameter vnd.oasis.opendocument.field.code; its result is the formatted text between
the separator and the end. These helpers insert, list, order and bulk-update such fields the way
the extension will (phase 04 of the citation plan), so the checks exercise the real commands.
"""
import functools

UNHANDLED = "vnd.oasis.opendocument.field.UNHANDLED"
CODE_PARAM = "vnd.oasis.opendocument.field.code"
CITATION_PREFIX = "ADDIN HST_CITATION "
BIBLIOGRAPHY_PREFIX = "ADDIN HST_BIBLIOGRAPHY"
MARKER = "¤"  # placeholder where a field goes; removed after insertion


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


class Session:
    """A Writer document plus what dispatching to it needs."""

    def __init__(self, ctx, doc):
        self.ctx, self.doc = ctx, doc
        self.helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        self.frame = doc.getCurrentController().getFrame()
        self.view_cursor = doc.getCurrentController().getViewCursor()

    def dispatch(self, command, *args):
        self.helper.executeDispatch(self.frame, ".uno:" + command, "", 0, tuple(args))

    def insert_field(self, where, code, html, wrapper=None):
        """Insert a fieldmark at the start of the text range `where` with the real command."""
        self.view_cursor.gotoRange(where.getStart(), False)
        args = [prop("FieldType", UNHANDLED), prop("FieldCommand", code), prop("FieldResult", html)]
        if wrapper:
            args.append(prop("Wrapper", wrapper))
        self.dispatch("TextFormField", *args)

    def markers(self):
        search = self.doc.createSearchDescriptor()
        search.SearchString = MARKER
        found = self.doc.findAll(search)
        return [found.getByIndex(i) for i in range(found.getCount())]

    def drop_markers(self):
        replace = self.doc.createReplaceDescriptor()
        replace.SearchString, replace.ReplaceString = MARKER, ""
        self.doc.replaceAll(replace)

    def bulk_update(self, prefix, fields):
        """One .uno:TextFormFields call; `fields` = [(code, html)] in raw mark order (see scan)."""
        import uno
        seq = tuple((prop("FieldCommand", code), prop("FieldResult", html)) for code, html in fields)
        self.dispatch("TextFormFields", prop("FieldType", UNHANDLED), prop("FieldCommandPrefix", prefix),
                      prop("Fields", uno.Any("[][]com.sun.star.beans.PropertyValue", seq)))

    def update_at_cursor(self, prefix, code, html):
        """.uno:UpdateTextFormField: the field holding the view cursor gets a new code and result."""
        import uno
        field = (prop("FieldCommand", code), prop("FieldResult", html))
        self.dispatch("UpdateTextFormField", prop("FieldType", UNHANDLED), prop("FieldCommandPrefix", prefix),
                      prop("Field", uno.Any("[]com.sun.star.beans.PropertyValue", field)))

    def undo_titles(self):
        return list(self.doc.getUndoManager().getAllUndoActionTitles())


class Field:
    """One HST fieldmark as listed by scan(): raw index, code, result text and UNO object."""

    def __init__(self, index, mark, code):
        self.index, self.mark, self.code = index, mark, code

    @property
    def result(self):
        return self.mark.getAnchor().getString()

    def __repr__(self):
        return f"Field({self.index}, {self.code[:40]!r})"


def field_code(mark):
    params = mark.getParameters()
    return params.getByName(CODE_PARAM) if params.hasByName(CODE_PARAM) else None


def scan(doc, prefix="ADDIN HST_"):
    """HST fieldmarks in raw mark order: getTextFields() lists fieldmarks by node position, and
    footnote, endnote, frame and header text comes before the body in the node array. This is the
    order .uno:TextFormFields walks, so updates must be listed in it."""
    out = []
    enum = doc.getTextFields().createEnumeration()
    while enum.hasMoreElements():
        mark = enum.nextElement()
        if mark.getImplementationName() != "SwXFieldmark" or mark.getFieldType() != UNHANDLED:
            continue
        code = field_code(mark)
        if code is not None and code.startswith(prefix):
            out.append(Field(len(out), mark, code))
    return out


NOTE_SERVICES = ("com.sun.star.text.Footnote", "com.sun.star.text.Endnote", "com.sun.star.text.TextFrame")


def body_position(doc, mark):
    """A body text range standing for the field's reading position: the field itself in body
    text; the anchor of the footnote, endnote, frame or table holding it otherwise (climbing
    through nesting); None in a header or footer."""
    body, rng = doc.getText(), mark.getAnchor()
    for _ in range(8):  # nesting depth guard (a table in a frame in a footnote, ...)
        text = rng.getText()
        if text is None or text == body:  # a footnote's anchor range may report no text: it is body
            return rng
        if any(text.supportsService(name) for name in NOTE_SERVICES):
            rng = text.getAnchor()
            continue
        table = rng.TextTable if rng.getPropertySetInfo().hasPropertyByName("TextTable") else None
        if table is None:
            return None  # header or footer text
        rng = table.getAnchor()
    return None


def reading_order(doc, fields):
    """Fields sorted as a reader meets them (header fields first, then body order; fields at
    the same body position, e.g. in one table, keep their raw order)."""
    text = doc.getText()
    keyed = [(body_position(doc, f.mark), f) for f in fields]

    def compare(a, b):
        if a[0] is None or b[0] is None:
            return (a[0] is not None) - (b[0] is not None) or a[1].index - b[1].index
        order = text.compareRegionStarts(a[0], b[0])  # 1: a first, -1: b first
        return -order if order else a[1].index - b[1].index

    return [f for _, f in sorted(keyed, key=functools.cmp_to_key(compare))]


def portions_inside(doc, field):
    """[(text, font, height, italic, escapement)] of the result portions of one field."""
    out, inside = [], False
    enum = field.mark.getAnchor().getText().createEnumeration()
    while enum.hasMoreElements():
        para = enum.nextElement()
        if not para.supportsService("com.sun.star.text.Paragraph"):
            continue
        portions = para.createEnumeration()
        while portions.hasMoreElements():
            part = portions.nextElement()
            kind = part.TextPortionType
            if kind == "TextFieldStart" and _same_mark(part, field.mark):
                inside = True
            elif kind == "TextFieldEnd" and _same_mark(part, field.mark):
                return out
            elif inside and kind == "Text":
                out.append((part.getString(), part.CharFontName, part.CharHeight,
                            part.CharPosture.value, part.CharEscapement))
    return out


def _same_mark(portion, mark):
    other = portion.Bookmark
    return other is not None and other.getName() == mark.getName()


def paragraphs_of(rng):
    """Paragraph objects a text range touches (for the multi-paragraph bibliography)."""
    cursor = rng.getText().createTextCursorByRange(rng)
    enum = cursor.createEnumeration()
    out = []
    while enum.hasMoreElements():
        para = enum.nextElement()
        if para.supportsService("com.sun.star.text.Paragraph"):
            out.append(para)
    return out
