# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư, Word documents in the office.

- Opening (job on OnLoad, mail_merge_word_job): a Word mail-merge document (.docx with w:mailMerge) or an HST one
  whose list moved is connected to its recipient list again, as Word does: the path it names, the path relative to
  the document, the list's name next to the document. When none is there the user is asked to find the file (a
  network path is confirmed first, since opening it may send the user's credentials).
- The staging copy gets a computed column for each Word field the document holds: a MERGEFIELD with switches or an
  IF (column = the Word instruction, mail_merge_word_fields) and a Word name such as "Họ_và_tên" for the header
  "Họ và tên". The engine merges Word's results; preview and output agree.
- The document names its list in its InteropGrabBag "HSTMailMergeSource", which the Word export writes as Word's own
  w:mailMerge link (sw/source/filter/ww8/hst/hstwordmergeexport.cxx), so Word reconnects too."""
import os

from . import mail_merge_addressbook as book
from . import mail_merge_format as fmt
from . import mail_merge_word_fields as wf
from . import mail_merge_word_source as word_source

DB_FIELD = "com.sun.star.text.TextField.Database"
GRAB_BAG = "HSTMailMergeSource"


def field_columns(doc):
    """Column names of every database field of the document, in order, once each."""
    columns = []
    enum = doc.TextFields.createEnumeration()
    while enum.hasMoreElements():
        field = enum.nextElement()
        if field.supportsService(DB_FIELD):
            column = field.TextFieldMaster.DataColumnName
            if column not in columns:
                columns.append(column)
    return columns


def word_column_names(columns, headers):
    """The columns that need a computed Word column: instructions, and Word names of a header ("Họ_và_tên")."""
    keys = {wf.name_key(h) for h in headers}
    return [c for c in columns if c not in headers and (wf.is_word_code(c) or wf.name_key(c) in keys)]


def extra_columns(table, columns, language="vi"):
    """[(column, function(row, position))] for mail_merge_table.staging."""
    def function(column):
        code = column if wf.is_word_code(column) else 'MERGEFIELD "%s"' % column.replace('"', "")
        return lambda row, position: wf.evaluate_code(code, wf.Record(wf.table_lookup(table, row), position, language))
    return [(column, function(column)) for column in word_column_names(columns, table.headers)]


def word_kind(table, column, kinds):
    """The kind an adopted Word field gets: the last chosen for its column, else dd/mm/yyyy for a date column,
    else the value as it is (numbers as typed, like Word)."""
    if column in kinds:
        return kinds[column]
    if column in table.headers and table.kind(column) == fmt.COL_DATE:
        return fmt.DATE
    return fmt.TEXT


def set_link(doc, path, sheet):
    """Name the list in the document's InteropGrabBag (no undo step, the modified state kept)."""
    from com.sun.star.beans import PropertyValue
    if not path or path.startswith(book.PREFIX):
        return
    modified = doc.isModified()
    try:
        bag = [p for p in doc.getPropertyValue("InteropGrabBag") if p.Name != GRAB_BAG]
        link = (PropertyValue(Name="Path", Value=path), PropertyValue(Name="Sheet", Value=sheet or ""))
        import uno
        bag.append(PropertyValue(Name=GRAB_BAG, Value=uno.Any("[]com.sun.star.beans.PropertyValue", link)))
        uno.invoke(doc, "setPropertyValue", ("InteropGrabBag", uno.Any("[]com.sun.star.beans.PropertyValue",
                                                                         tuple(bag))))
    except Exception:  # noqa: BLE001 - a document without a grab bag: Word keeps its own link only
        from .diag_log import exception
        exception("mail merge link")
    finally:
        if not modified:
            doc.setModified(False)


def _document_path(doc):
    import uno
    url = doc.getURL()
    return uno.fileUrlToSystemPath(url) if url.startswith("file:") else ""


def link_of(doc):
    """The Link a Word document on disk names, or None."""
    path = _document_path(doc)
    return word_source.read(path) if path.lower().endswith(word_source.WORD_PACKAGES) else None


def connect_on_load(ctx, doc):
    """Connect a just-opened mail-merge document to its list; returns True when connected."""
    from . import mail_merge_session as sessions
    session = sessions.get(doc)
    folder = os.path.dirname(_document_path(doc))
    if session.has_list and not session.meta["source"].startswith(book.PREFIX):
        wanted, sheet = session.meta["source"], session.meta["sheet"]
        if os.path.isfile(wanted):
            set_link(doc, wanted, sheet)
            return False  # connected lazily by the Gửi thư commands, as before
    elif session.has_list:
        return False
    else:
        link = link_of(doc)
        if link is None:
            return False
        wanted, sheet = link.path, link.sheet
    found = word_source.locate(wanted, folder) or _ask(ctx, doc, wanted, folder)
    if not found:
        return False
    return _connect(ctx, doc, session, found, sheet)


def _ask(ctx, doc, wanted, folder):
    from .dialogs import message_box
    from .mail_merge_small_dialogs import pick_file
    from .mail_merge_texts import texts
    t = texts(ctx)
    peer = doc.getCurrentController().getFrame().getContainerWindow()
    if word_source.is_remote(wanted):
        if message_box(ctx, peer, t["title"], t["word.remote"] % wanted, ask=True,
                       buttons=(t["word.connect"], t["word.skip"])):
            return wanted if os.path.isfile(wanted) else pick_file(ctx, t, folder)
        return None
    if not message_box(ctx, peer, t["title"], t["word.missing"] % wanted, ask=True,
                       buttons=(t["word.find"], t["word.skip"])):
        return None
    return pick_file(ctx, t, folder)


def _connect(ctx, doc, session, path, sheet):
    """Read the list, connect the fields and show their names, leaving the document unmodified."""
    from . import mail_merge_fields as fields
    from . import mail_merge_source as source
    from . import mail_merge_store as store
    modified = doc.isModified()
    undo = doc.UndoManager
    undo.lock()
    try:
        table, sheets, used = source.read(ctx, path, sheet)  # a renamed sheet: the first one
        session.choose(ctx, path, used, table, sheets)
        name = session.stage(ctx)
        fields.adopt(doc, name, session.meta, session.table)
        fields.show_names(doc, store.source_name(session.meta))
        set_link(doc, path, used)
        return True
    except Exception:  # noqa: BLE001 - never stop a document from opening
        from .diag_log import exception
        exception("mail merge reconnect")
        return False
    finally:
        undo.unlock()
        if not modified:
            doc.setModified(False)
