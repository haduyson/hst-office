# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Hoàn tất và trộn (its ▾ items preselect the action) and Xem trước kết quả ▸ Kiểm tra lỗi.
Before merging, every "Hỏi" rule used in the document asks its question once; the answer goes to every copy."""
from . import mail_merge_check as check
from . import mail_merge_fields as fields
from . import mail_merge_output as out
from . import mail_merge_rules as rules

ACTIONS = {"FinishEdit": out.EDIT, "FinishPrint": out.PRINT, "FinishMail": out.MAIL, "FinishPdf": out.PDF,
           "FinishDocx": out.DOCX}


def used_columns(c):
    return [column for _field, column in fields.merge_fields(c.doc, c.source_name)]


def ask_questions(c):
    """Ask each "Hỏi" rule the document uses; False when the user cancels."""
    from .mail_merge_small_dialogs import ask_text
    used = set(used_columns(c))
    changed = False
    for rule in rules.valid_rules(c.session.meta["rules"]):
        if rule["type"] != "ask" or rules.rule_column(rule) not in used:
            continue
        answer = ask_text(c.ctx, c.t, c.peer, c.t["ask.title"], rule.get("prompt") or rule["name"], rule.get("value", ""))
        if answer is None:
            return False
        rule["value"], changed = answer, True
    if changed:
        c.session.save()
    return True


def finish(c, action=None):
    from .mail_merge_finish_dialog import FinishDialog
    if not c.ready():
        return
    if not c.session.checked():
        return c.say(c.t["err.none-checked"])
    if not used_columns(c) and not c.say(c.t["msg.no-fields"], ask=True):
        return
    default = action or (out.MAIL if c.session.meta.get("type") == "email" else out.PDF)
    request = FinishDialog(c.ctx, c.t, c.session, default).run(c.peer)
    if request is None or not ask_questions(c):
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


def check_errors(c):
    """Simulate the merge and list the problems (Kiểm tra lỗi)."""
    from .mail_merge_small_dialogs import show_lines
    if not c.ready():
        return
    meta = c.session.meta
    effective = c.session.effective(pattern=meta["pattern"], words=c.words())
    mail = ""
    if meta.get("type") == "email":
        mail = next(iter(out.mail_columns(c.session.table)), "")
    names = [r[-1] for r in effective.rows] if meta["pattern"] else []
    found = check.problems(effective, used_columns(c), mail, names)
    if not found:
        return c.say(c.t["chk.none"] % len(effective.rows))
    from .mail_merge_address import guess_roles
    name_column = guess_roles(c.session.table.headers)["name"] or next(
        (h for h, k in zip(effective.headers, effective.kinds) if k == "text"), None)

    def who(position):
        return effective.text(effective.rows[position - 1], name_column) if name_column else ""
    title = c.t["chk.title"] % (len(found), len(effective.rows))
    show_lines(c.ctx, c.t, c.peer, c.t["chk.dialog"], title, check.lines(found, c.t, who))


COMMANDS = {"Finish": finish, "Check": check_errors,
            **{name: (lambda action: lambda c: finish(c, action))(action) for name, action in ACTIONS.items()}}
