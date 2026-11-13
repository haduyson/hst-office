# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the state of one document while the office runs: its settings (mail_merge_store meta), the recipient
list read from the source file (re-read when the file changed on disk), the preview switch and the recipient shown.
Sessions are kept per document (RuntimeUID) and forgotten when the document closes or another list is chosen."""
import os

from . import mail_merge_source as source
from . import mail_merge_store as store
from . import mail_merge_addressbook as book
from . import mail_merge_rules as rules
from . import mail_merge_table as mt

_SESSIONS = {}


class Session:
    def __init__(self, doc):
        self.doc = doc
        self.meta = store.read_meta(doc)
        self.table, self.mtime = None, None
        self.sheets = []
        self.preview, self.position = False, 0  # position in the checked recipients

    @property
    def has_list(self):
        return bool(self.meta["source"])

    def load(self, ctx, force=False):
        """The Table of the source file; re-read when the file changed. Raises source.SourceError."""
        path = self.meta["source"]
        if not path:
            raise source.SourceError("no-list")
        if path.startswith(book.PREFIX):  # Chọn từ danh bạ: a registered address book, read once per session
            if force or self.table is None:
                self.table = book.read(ctx, path)
            return self.table
        try:
            mtime = os.path.getmtime(path)
        except OSError as exc:
            raise source.SourceError("missing", path) from exc
        if force or self.table is None or mtime != self.mtime:
            self.table, self.sheets, sheet = source.read(ctx, path, self.meta["sheet"])
            self.meta["sheet"], self.mtime = sheet, mtime
        return self.table

    def choose(self, ctx, path, sheet=None, table=None, sheets=()):
        """Use another recipient list (keeps the id: fields already inserted stay valid when headers match).
        `table`: that sheet already read by the caller."""
        if table is None and path.startswith(book.PREFIX):
            table, sheets = book.read(ctx, path), []
        elif table is None:
            table, sheets, sheet = source.read(ctx, path, sheet)
        self.meta.update(source=path, sheet=sheet, excluded=[], sort="", descending=False)
        self.meta["id"] = self.meta["id"] or store.new_id()
        self.table, self.sheets = table, list(sheets)
        self.mtime = None if path.startswith(book.PREFIX) else os.path.getmtime(path)
        self.position = 0
        self.save()
        return table

    def save(self):
        store.write_meta(self.doc, self.meta)

    def checked(self):
        """Indexes of the recipients that take part, in order: checked and not left out by "Bỏ qua bản ghi nếu"."""
        indexes = mt.checked_indexes(self.table, self.meta["excluded"], self.meta["sort"], self.meta["descending"])
        skip = self.meta["skip"]
        return [i for i in indexes if not rules.skipped(self.table, self.table.rows[i], skip)] if skip else indexes

    def current_row(self):
        """(row, position, count) of the recipient shown, or (None, 0, 0) without checked recipients."""
        indexes = self.checked()
        if not indexes:
            return None, 0, 0
        self.position = max(0, min(self.position, len(indexes) - 1))
        return self.table.rows[indexes[self.position]], self.position, len(indexes)

    def effective(self, indexes=None, pattern="", words=None):
        """The rows the engine merges (default: all checked) with every computed column, as a Table."""
        rows = self.checked() if indexes is None else indexes
        return mt.Table(*mt.staging(self.table, rows, pattern, words, rules.extra_columns(self.meta, self.table)))

    def preview_row(self, words=None):
        """(effective table, row shown or None): what the preview writes into the fields."""
        effective = self.effective(words=words)
        if not effective.rows:
            return effective, None
        self.position = max(0, min(self.position, len(effective.rows) - 1))
        return effective, effective.rows[self.position]

    def stage(self, ctx, indexes=None, pattern="", words=None):
        """Write the engine's copy of the given rows (default: all checked) and connect the document to it;
        returns the data source name."""
        effective = self.effective(indexes, pattern, words)
        folder = store.work_dir(ctx, self.meta)
        path = store.write_staging(ctx, folder, effective.headers, effective.kinds, effective.rows)
        name = store.register(ctx, self.meta, folder, path)
        store.set_current_source(self.doc, name)
        return name


def _prune():
    for key, session in list(_SESSIONS.items()):
        try:
            session.doc.getCurrentController()
        except Exception:  # noqa: BLE001 - DisposedException: the document was closed
            del _SESSIONS[key]


def get(doc):
    _prune()
    key = doc.RuntimeUID
    session = _SESSIONS.get(key)
    if session is None:
        session = _SESSIONS[key] = Session(doc)
    return session


def forget(doc):
    _SESSIONS.pop(doc.RuntimeUID, None)


def words_settings(ctx, doc):
    """Number-words settings as "Đọc số thành chữ" uses them: the file's default, else the user's."""
    from . import number_words_defaults as defaults
    from . import number_words_file_default as file_default
    from . import number_words_prefs as prefs
    try:
        return defaults.resolve(file_default.read(doc), prefs.load(ctx))
    except Exception:  # noqa: BLE001 - unreadable settings: program defaults
        return defaults.resolve()
