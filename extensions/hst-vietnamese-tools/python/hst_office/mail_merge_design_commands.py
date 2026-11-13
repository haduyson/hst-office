# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: Bắt đầu trộn thư ▾ (Thư, Phong bì, Nhãn, Thư điện tử, Văn bản thường), Khối địa chỉ, Dòng chào,
Quy tắc ▾ (Nếu…Thì…Khác, Bỏ qua bản ghi nếu, Hỏi, Đặt số thứ tự) and Chèn trường trộn ▾ <column>.
The block, the greeting and the rules are computed columns (mail_merge_rules.py): their settings go to the document,
the field is inserted, then the engine's copy is written again."""
from . import mail_merge_rules as rules
from . import mail_merge_table as mt

ENGINE = {"StartEnvelope": ".uno:InsertEnvelope", "StartLabels": ".uno:InsertLabels"}


def _dispatch(c, command):
    helper = c.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", c.ctx)
    helper.executeDispatch(c.frame, command, "", 0, ())


def start(c, kind):
    """Thư / Thư điện tử: remember the document type (Hoàn tất proposes e-mail for the latter); Văn bản thường:
    detach the recipient list (fields show their column names again)."""
    if kind == "normal":
        if not c.session.has_list or not c.say(c.t["start.normal-ask"], ask=True):
            return
        if c.session.preview:
            c.session.preview = False
            c.refresh_preview()
        c.session.meta.update(source="", excluded=[], sheet=None)
        c.session.table = None
    c.session.meta["type"] = kind
    c.session.save()


def insert_column(c):
    """Chèn trường trộn ▾ <column>: insert that column with its default format."""
    from . import mail_merge_format as fmt
    column = c.args.get("Column", "")
    if not column or not c.ready():
        return
    table = c.session.table
    if column in table.headers:
        values = [r[table.column(column)] for r in table.rows]
        kind = c.session.meta["kinds"].get(column) or fmt.default_kind(table.kind(column), values)
    else:
        kind = fmt.TEXT
    c.insert(column, kind)


def _address(c, greeting):
    from .mail_merge_address_dialog import AddressDialog
    if not c.ready():
        return
    key = "greeting" if greeting else "block"
    row = c.session.current_row()[0]
    conf = AddressDialog(c.ctx, c.t, c.session.table, row, c.session.meta[key], greeting).run(c.peer)
    if conf is None:
        return
    c.session.meta[key] = conf
    c.session.save()
    c.restage()
    c.insert(mt.computed_name(rules.GREETING_COLUMN if greeting else rules.BLOCK_COLUMN, c.session.table.headers))


def rule(c, kind):
    from .mail_merge_rule_dialog import RuleDialog
    if not c.ready():
        return
    table = c.session.table

    def count(condition):
        return sum(1 for i in c.session.checked() if rules.matches(table, table.rows[i], condition))
    result = RuleDialog(c.ctx, c.t, table, kind, count if kind == "skip" else None).run(c.peer)
    if result is None:
        return
    meta = c.session.meta
    if kind == "skip":
        meta["skip"] = list(meta["skip"]) + [result]
    else:
        meta["rules"] = rules.upsert(meta["rules"], result)
    c.session.save()
    c.restage()
    if kind != "skip":
        c.insert(mt.computed_name(rules.rule_column(result), table.headers))


COMMANDS = {"StartLetter": lambda c: start(c, "letter"), "StartEmail": lambda c: start(c, "email"),
            "StartNormal": lambda c: start(c, "normal"), "InsertColumn": insert_column,
            "AddressBlock": lambda c: _address(c, False), "Greeting": lambda c: _address(c, True),
            "RuleIf": lambda c: rule(c, "if"), "RuleSkip": lambda c: rule(c, "skip"),
            "RuleAsk": lambda c: rule(c, "ask"), "RuleSeq": lambda c: rule(c, "seq"),
            **{name: (lambda command: lambda c: _dispatch(c, command))(command) for name, command in ENGINE.items()}}
