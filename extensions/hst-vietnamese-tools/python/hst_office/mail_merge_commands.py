# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the recipient list, field and preview commands of the Gửi thư tab (org.hst.office.mailmerge:<Command>,
mail_merge_handler.py; finish: mail_merge_finish_commands.py, design: mail_merge_design_commands.py). Every command
gets a mail_merge_context.Context; errors are told in a message, never raised into the office."""
from . import mail_merge_fields as fields
from . import mail_merge_source as source
from . import mail_merge_table as mt


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
    effective, row = c.session.preview_row(c.words())
    InsertFieldDialog(c.ctx, c.t, effective, row, c.words(), c.insert).run(c.peer)


def field_format(c):
    from .mail_merge_insert_dialog import InsertFieldDialog
    if not c.ready():
        return
    name = c.source_name
    field, column = fields.selected_field(c.doc, name)
    if field is None:
        return c.say(c.t["err.no-field"])
    base, kind = fields.field_kind(c.doc, field, column)
    effective, row = c.session.preview_row(c.words())
    dialog = InsertFieldDialog(c.ctx, c.t, effective, row, c.words(), column=base, kind=kind)
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


COMMANDS = {"Recipients": recipients, "EditRecipients": edit_recipients, "InsertField": insert_field,
            "FieldFormat": field_format, "Preview": preview, "Find": find, "Record": find,
            **{name: (lambda where: lambda c: move(c, where))(name) for name in ("First", "Prev", "Next", "Last")}}
