# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: what each command of the Gửi thư tab does (org.hst.office.mailmerge:<Command>, mail_merge_handler.py).
Every command works on the document of the frame; errors are told in a message, never raised into the office."""
from . import mail_merge_fields as fields
from . import mail_merge_session as sessions
from . import mail_merge_source as source
from . import mail_merge_store as store
from .dialogs import message_box
from .mail_merge_texts import texts


class Context:
    def __init__(self, ctx, frame):
        self.ctx, self.frame = ctx, frame
        self.doc = frame.getController().getModel()
        self.peer = frame.getContainerWindow()
        self.t = texts(ctx)
        self.session = sessions.get(self.doc)

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
        if not registered.hasByName(store.source_name(self.session.meta)):
            self.session.stage(self.ctx)
        fields.adopt(self.doc, store.source_name(self.session.meta), self.session.meta)
        return True

    def remember(self, column, kind):
        """The format last chosen for a column (restores formats a DOCX round trip dropped)."""
        self.session.meta["kinds"][column] = kind
        self.session.save()

    def words(self):
        return sessions.words_settings(self.ctx, self.doc)

    def refresh_preview(self):
        row = self.session.current_row()[0] if self.session.preview else None
        name = store.source_name(self.session.meta)
        fields.show_values(self.doc, name, self.session.table, row, self.words())


def recipients(c):
    """Chọn danh sách người nhận: file picker, sheet choice, connect, then the recipient list."""
    from .mail_merge_small_dialogs import choose_sheet, pick_file
    import os
    path = pick_file(c.ctx, c.t, os.path.dirname(c.session.meta["source"]))
    if not path:
        return
    try:
        table, sheets, first = source.read(c.ctx, path)
        sheet = choose_sheet(c.ctx, c.t, sheets, c.peer) if sheets else None
        if sheets and sheet is None:
            return
        c.session.choose(c.ctx, path, sheet, table if sheet == first else None, sheets)
    except source.SourceError as exc:
        return c.source_error(exc)
    c.session.stage(c.ctx)
    edit_recipients(c)


def edit_recipients(c):
    from .mail_merge_recipients_dialog import CHANGE, OK, REFRESH, RecipientsDialog
    if not c.session.has_list:
        return recipients(c)
    force = False
    while True:
        try:
            c.session.load(c.ctx, force)
        except source.SourceError as exc:
            return c.source_error(exc)
        result = RecipientsDialog(c.ctx, c.t, c.session).run(c.peer)
        if result == CHANGE:
            return recipients(c)
        force = result == REFRESH
        if not force:
            break
    if result == OK:
        c.session.stage(c.ctx)
        if c.session.preview:
            c.refresh_preview()


def insert_field(c):
    from .mail_merge_insert_dialog import InsertFieldDialog
    if not c.ready():
        return
    name, words = store.source_name(c.session.meta), c.words()

    def insert(column, kind):
        try:
            fields.insert(c.doc, name, column, kind)
            c.remember(column, kind)
        except Exception:  # noqa: BLE001 - protected section or read-only document
            return c.say(c.t["err.readonly"])
        if c.session.preview:
            c.refresh_preview()
    InsertFieldDialog(c.ctx, c.t, c.session.table, c.session.current_row()[0], words, insert).run(c.peer)


def field_format(c):
    from .mail_merge_insert_dialog import InsertFieldDialog
    if not c.ready():
        return
    name = store.source_name(c.session.meta)
    field, column = fields.selected_field(c.doc, name)
    if field is None:
        return c.say(c.t["err.no-field"])
    base, kind = fields.field_kind(c.doc, field, column)
    dialog = InsertFieldDialog(c.ctx, c.t, c.session.table, c.session.current_row()[0], c.words(), column=base, kind=kind)
    chosen = dialog.run(c.peer)
    if chosen and chosen != kind:
        fields.change_kind(c.doc, name, field, column, chosen)
        c.remember(base, chosen)
        if c.session.preview:
            c.refresh_preview()


def preview(c):
    if not c.ready():
        return
    c.session.preview = not c.session.preview
    c.refresh_preview()


def move(c, where):
    """First / Prev / Next / Last: show that recipient (turns the preview on)."""
    if not c.ready():
        return
    _row, position, count = c.session.current_row()
    if not count:
        return c.say(c.t["err.none-checked"])
    c.session.position = {"First": 0, "Prev": position - 1, "Next": position + 1, "Last": count - 1}[where]
    c.session.preview = True
    c.refresh_preview()


def find(c):
    from . import mail_merge_table as mt
    from .mail_merge_small_dialogs import ask_find
    if not c.ready():
        return
    needle = ask_find(c.ctx, c.t, c.peer, getattr(c.session, "last_find", ""))
    if not needle:
        return
    c.session.last_find = needle
    indexes = c.session.checked()
    start = c.session.position + 1 if c.session.preview else 0
    for step in range(len(indexes)):
        position = (start + step) % len(indexes)
        if mt.matches(c.session.table, c.session.table.rows[indexes[position]], needle):
            c.session.position, c.session.preview = position, True
            return c.refresh_preview()
    c.say(c.t["msg.not-found"] % needle)


def finish(c):
    from . import mail_merge_output as out
    from .mail_merge_finish_dialog import FinishDialog
    if not c.ready():
        return
    if not c.session.checked():
        return c.say(c.t["err.none-checked"])
    if not fields.merge_fields(c.doc, store.source_name(c.session.meta)) and not c.say(c.t["msg.no-fields"], ask=True):
        return
    request = FinishDialog(c.ctx, c.t, c.session).run(c.peer)
    if request is None:
        return
    if request.action == out.MAIL and not out.mail_server_set(c.ctx):
        return c.say(c.t["err.mail-not-set"])
    try:
        _merged, count = out.run(c.ctx, c.doc, c.session, request, c.words())
    except Exception as exc:  # noqa: BLE001 - engine errors (disk full, SMTP refused, ...) are shown, not raised
        from .diag_log import exception
        exception("mail merge finish")
        return c.say(c.t["err.failed"] % (getattr(exc, "Message", "") or str(exc)))
    if request.action in (out.PDF, out.DOCX):
        c.say(c.t["msg.files"] % (count, request.folder))
    elif request.action == out.MAIL:
        c.say(c.t["msg.mails"] % count)


COMMANDS = {"Recipients": recipients, "EditRecipients": edit_recipients, "InsertField": insert_field,
            "FieldFormat": field_format, "Preview": preview, "Find": find, "Finish": finish, "Record": find,
            **{name: (lambda where: lambda c: move(c, where))(name) for name in ("First", "Prev", "Next", "Last")}}
