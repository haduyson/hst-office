# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Quy tắc: one dialog for the four rules (mail_merge_rules.py).
  if    Nếu…Thì…Khác: name, column, comparison, value, text when true, text when false ({Cột} allowed)
  skip  Bỏ qua bản ghi nếu: column, comparison, value; lists how many recipients it leaves out
  ask   Hỏi: name, question, default answer (asked once when merging)
  seq   Đặt số thứ tự: name, first number
Returns the rule (dict) or None."""
from . import mail_merge_rules as rules
from .dialogs import Dialog

HEIGHTS = {"if": 150, "skip": 104, "ask": 92, "seq": 76}


class RuleDialog:
    def __init__(self, ctx, texts, table, kind, count_skipped=None):
        self.t, self.table, self.kind, self.count_skipped = texts, table, kind, count_skipped
        self.result = None
        d = self.d = Dialog(ctx, texts["rule." + kind], 300, HEIGHTS[kind])
        y = 6
        if kind != "skip":
            default = texts["rule.seq-name"] if kind == "seq" else ""
            y = self._row("name", texts["rule.name"], y, lambda yy: d.edit("name", 100, yy, 192, text=default,
                                                                             help_text=texts["rule.name"]))
        if kind in ("if", "skip"):
            ops = [texts["op." + op] for op in rules.OPS]
            y = self._row("column", texts["rule.column"], y, lambda yy: d.listbox("column", 100, yy, 192, table.headers, 0))
            y = self._row("op", texts["rule.op"], y, lambda yy: d.listbox("op", 100, yy, 192, ops, 0))
            y = self._row("value", texts["rule.value"], y, lambda yy: d.edit("value", 100, yy, 192, help_text=texts["rule.value"]))
        if kind == "if":
            y = self._row("then", texts["rule.then"], y, lambda yy: d.edit("then", 100, yy, 192, help_text=texts["rule.then"]))
            y = self._row("else", texts["rule.else"], y, lambda yy: d.edit("else", 100, yy, 192, help_text=texts["rule.else"]))
            d.label("hint", texts["rule.hint"], 8, y, 284, 18, wrap=True)
        if kind == "ask":
            y = self._row("prompt", texts["rule.prompt"], y, lambda yy: d.edit("prompt", 100, yy, 192, help_text=texts["rule.prompt"]))
            y = self._row("answer", texts["rule.answer"], y, lambda yy: d.edit("answer", 100, yy, 192, help_text=texts["rule.answer"]))
        if kind == "seq":
            y = self._row("start", texts["rule.start"], y, lambda yy: d._add(
                "NumericField", "start", 100, yy, 60, 12, Value=1.0, ValueMin=0.0, ValueMax=1e9, DecimalAccuracy=0,
                Spin=True, StrictFormat=True, HelpText=texts["rule.start"]))
        if kind == "skip":
            d.label("count", "", 8, y + 2, 284)
            d.on_change(["column", "op", "value"], self._count)
            d.on_ready = self._count
        bottom = HEIGHTS[kind] - 18
        d.button("ok", texts["ok"], 176, bottom, 56, default=True, callback=self._accept)
        d.button("cancel", texts["cancel"], 236, bottom, 56, callback=lambda: d.end(0))

    def _row(self, name, label, y, make):
        self.d.label(name + "Label", label, 8, y + 2, 90)
        make(y)
        return y + 16

    def _condition(self):
        return {"column": self.table.headers[max(0, self.d.get("column"))], "op": rules.OPS[max(0, self.d.get("op"))],
                "value": self.d.get("value").strip()}

    def _count(self):
        if self.count_skipped:
            self.d.model.getByName("count").Label = self.t["rule.skip-count"] % self.count_skipped(self._condition())

    def _accept(self):
        from .dialogs import message_box
        if self.kind == "skip":
            self.result = self._condition()
            return self.d.end(1)
        name = self.d.get("name").strip()
        if not name:
            return message_box(self.d.ctx, self.d.dialog.getPeer(), self.t["title"], self.t["rule.need-name"])
        rule = {"type": self.kind, "name": name}
        if self.kind == "if":
            rule.update(self._condition(), then=self.d.get("then"), **{"else": self.d.get("else")})
        elif self.kind == "ask":
            rule.update(prompt=self.d.get("prompt").strip() or name, value=self.d.get("answer"))
        else:
            rule["start"] = int(self.d.model.getByName("start").Value)
        self.result = rule
        self.d.end(1)

    def run(self, parent_peer):
        self.d.execute(parent_peer)
        return self.result
