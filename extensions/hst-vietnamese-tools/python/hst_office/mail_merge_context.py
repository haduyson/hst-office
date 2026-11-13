# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: what every command gets (mail_merge_handler.py): the office context, the frame and its document, the
texts in the UI language, the document's session, the dispatch arguments, and the shared steps (ready, insert a
field, refresh the preview, messages)."""
from . import mail_merge_fields as fields
from . import mail_merge_session as sessions
from . import mail_merge_source as source
from . import mail_merge_store as store
from .dialogs import message_box
from .mail_merge_texts import texts


class Context:
    def __init__(self, ctx, frame, args=None):
        self.ctx, self.frame = ctx, frame
        self.doc = frame.getController().getModel()
        self.peer = frame.getContainerWindow()
        self.t = texts(ctx)
        self.session = sessions.get(self.doc)
        self.args = dict(args or {})

    @property
    def source_name(self):
        return store.source_name(self.session.meta)

    def say(self, text, ask=False):
        buttons = (self.t["yes"], self.t["no"]) if ask else None
        return message_box(self.ctx, self.peer, self.t["title"], text, ask=ask, buttons=buttons)

    def source_error(self, exc):
        text = self.t.get("err." + exc.code, self.t["err.unreadable"])
        return self.say(text % (exc.detail or exc.code) if "%s" in text else text)

    def ready(self):
        """The recipient list loaded and the data source registered on this computer; False after telling why."""
        if not self.session.has_list:
            return self.say(self.t["err.no-list"]) and False
        try:
            self.session.load(self.ctx)
        except source.SourceError as exc:
            return self.source_error(exc) and False
        registered = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", self.ctx)
        if not registered.hasByName(self.source_name):
            self.session.stage(self.ctx)
        fields.adopt(self.doc, self.source_name, self.session.meta)
        if not self.session.preview:
            fields.show_names(self.doc, self.source_name)
        return True

    def remember(self, column, kind):
        """The format last chosen for a column (restores formats a DOCX round trip dropped)."""
        self.session.meta["kinds"][column] = kind
        self.session.save()

    def words(self):
        return sessions.words_settings(self.ctx, self.doc)

    def insert(self, column, kind="text"):
        """Insert a merge field at the cursor; False after telling the user why not."""
        try:
            fields.insert(self.doc, self.source_name, column, kind)
        except Exception:  # noqa: BLE001 - protected section or read-only document
            return self.say(self.t["err.readonly"]) and False
        self.remember(column, kind)
        self.refresh_preview()  # a new field reads the connected source at once: empty unless shown again
        return True

    def restage(self):
        """After a change of computed columns: the engine's copy and the preview follow."""
        self.session.stage(self.ctx, words=self.words())
        if self.session.preview:
            self.refresh_preview()

    def refresh_preview(self):
        effective, row = self.session.preview_row(self.words())
        fields.show_values(self.doc, self.source_name, effective, row if self.session.preview else None, self.words())
