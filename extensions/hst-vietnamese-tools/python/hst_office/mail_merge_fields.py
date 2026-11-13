# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the merge fields of the document. A field is a LibreOffice database field of the document's data source
(mail_merge_store); its kind (mail_merge_format) is kept in the field itself: a vi-VN number format for numbers and
dates, a computed column for the two word kinds. The engine merges with exactly that, and the preview writes the
same text into the fields (property Content) without an undo step or a "modified" mark."""
from . import mail_merge_format as fmt
from . import mail_merge_store as store

DB_FIELD = "com.sun.star.text.TextField.Database"
DB_MASTER = "com.sun.star.text.FieldMaster.Database"


def _locale():
    from com.sun.star.lang import Locale
    return Locale("vi", "VN", "")


def format_key(doc, code):
    formats = doc.NumberFormats
    key = formats.queryKey(code, _locale(), False)
    return key if key >= 0 else formats.addNew(code, _locale())


def merge_fields(doc, source_name):
    """[(field, column)] of the document's fields that read `source_name`."""
    found = []
    enum = doc.TextFields.createEnumeration()
    while enum.hasMoreElements():
        field = enum.nextElement()
        if field.supportsService(DB_FIELD):
            master = field.TextFieldMaster
            if master.DataBaseName == source_name:
                found.append((field, master.DataColumnName))
    return found


def field_kind(doc, field, column):
    """(base column, kind) of a field in the document."""
    code = ""
    if not field.DataBaseFormat:
        try:
            code = doc.NumberFormats.getByKey(field.NumberFormat).FormatString
        except Exception:  # noqa: BLE001 - unknown key: shown as text
            code = ""
    return fmt.kind_of_field(column, code, field.DataBaseFormat)


def _new_field(doc, source_name, column, kind):
    master = doc.createInstance(DB_MASTER)
    master.DataBaseName, master.DataTableName, master.DataCommandType = source_name, store.TABLE, 0
    master.DataColumnName = target_column(column, kind)
    field = doc.createInstance(DB_FIELD)
    field.attachTextFieldMaster(master)
    return field


def apply_kind(doc, field, kind):
    """Number format of an inserted field (word kinds and text read the column as it is)."""
    if kind in fmt.CODES:
        field.DataBaseFormat = False
        field.NumberFormat = format_key(doc, fmt.CODES[kind])
    else:
        field.DataBaseFormat = True


def insert(doc, source_name, column, kind):
    """Insert a field at the cursor (replacing a selection); returns it."""
    cursor = doc.CurrentController.ViewCursor
    field = _new_field(doc, source_name, column, kind)
    cursor.getText().insertTextContent(cursor, field, True)
    apply_kind(doc, field, kind)
    return field


def selected_field(doc, source_name):
    """(field, column) of the merge field at the cursor or in the selection, else (None, None)."""
    cursor = doc.CurrentController.ViewCursor
    candidates = []
    try:
        candidates.append(cursor.TextField)
    except Exception:  # noqa: BLE001 - no field at the cursor
        pass
    try:
        selection = doc.CurrentSelection
        for index in range(selection.getCount()):
            paragraphs = selection.getByIndex(index).createEnumeration()
            while paragraphs.hasMoreElements():
                portions = paragraphs.nextElement().createEnumeration()
                while portions.hasMoreElements():
                    portion = portions.nextElement()
                    if portion.TextPortionType == "TextField":
                        candidates.append(portion.TextField)
    except Exception:  # noqa: BLE001 - a frame, a shape or a table selection: only the cursor counts
        pass
    for field in candidates:
        if field is not None and field.supportsService(DB_FIELD) and field.TextFieldMaster.DataBaseName == source_name:
            return field, field.TextFieldMaster.DataColumnName
    return None, None


def target_column(column, kind):
    base = fmt.split_word_column(column)[0]
    return fmt.word_column(base, kind) if kind in fmt.WORD_SUFFIX else base


def change_kind(doc, source_name, field, column, kind):
    """Give an existing field another kind; when the kind reads another column (the word kinds) the field is
    replaced in its place. Returns the field now in the document."""
    if target_column(column, kind) != column:
        anchor = field.getAnchor()
        replacement = _new_field(doc, source_name, fmt.split_word_column(column)[0], kind)
        anchor.getText().insertTextContent(anchor, replacement, True)
        field = replacement
    apply_kind(doc, field, kind)
    return field


def show_names(doc, source_name):
    """Every merge field shows "<Cột>" (a field evaluated against the connected source would show nothing)."""
    show_values(doc, source_name, None, None)


def show_values(doc, source_name, table, row, words=None):
    """Preview: every merge field shows the value of `row` (None = the column names, as without preview)."""
    modified = doc.isModified()
    undo = doc.UndoManager
    undo.lock()
    try:
        for field, column in merge_fields(doc, source_name):
            base, kind = field_kind(doc, field, column)
            if row is None or table is None or base not in table.headers:
                field.Content = "<%s>" % base
            else:
                field.Content = fmt.render(kind, table.value(row, base), words)
            field.update()
    finally:
        undo.unlock()
        if not modified:
            doc.setModified(False)


def adopt(doc, source_name, meta):
    """Fields of this list that came back from a DOCX file: Word files keep neither the number formats nor always
    the whole data source name. Such fields are pointed at the document's data source again and get the format last
    chosen for their column (meta "kinds"). Returns the number of fields changed."""
    changed = 0
    enum = doc.TextFields.createEnumeration()
    while enum.hasMoreElements():
        field = enum.nextElement()
        if not field.supportsService(DB_FIELD):
            continue
        master = field.TextFieldMaster
        column, name = master.DataColumnName, master.DataBaseName
        if master.DataTableName != store.TABLE or not meta["id"] or not name.endswith(meta["id"]):
            continue
        base, kind = fmt.split_word_column(column)
        kind = kind or meta["kinds"].get(base, fmt.TEXT)
        if name != source_name:
            anchor = field.getAnchor()
            field = _new_field(doc, source_name, base, kind)
            anchor.getText().insertTextContent(anchor, field, True)
        elif not (field.DataBaseFormat and kind in fmt.CODES):
            continue
        apply_kind(doc, field, kind)
        changed += 1
    return changed
