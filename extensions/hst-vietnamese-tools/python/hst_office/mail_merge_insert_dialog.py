# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ "Chèn trường trộn" (mockup 03) and "Định dạng trường": the columns by their own (Vietnamese) header,
the ways a value can be shown for the selected column and a live example from the recipient shown. The insert
dialog stays open after each insertion, like the reference app's dialog; the format dialog returns one kind."""
from . import mail_merge_format as fmt
from . import mail_merge_table as mt
from .dialogs import Dialog, _Action


class InsertFieldDialog:
    def __init__(self, ctx, texts, table, row, words, on_insert=None, column=None, kind=None):
        """`on_insert(column, kind)`: insert mode; without it the dialog is the format dialog of `column`."""
        self.t, self.table, self.row, self.words, self.on_insert = texts, table, row, words, on_insert
        self.columns = mt.insertable(table.headers) if on_insert else [column]
        self.kinds = []
        self.result = None
        title = texts["ins.title"] if on_insert else texts["fmt.title"]
        d = self.d = Dialog(ctx, title, 300, 178)
        d.label("colLabel", texts["ins.columns"], 8, 6, 130)
        d.listbox("columns", 8, 18, 130, self.columns, 0, h=128, dropdown=False, help_text=texts["ins.columns"])
        d.label("kindLabel", texts["ins.kind"], 146, 6, 146)
        d.listbox("kind", 146, 18, 146, [], h=70, dropdown=False, help_text=texts["ins.kind"])
        d.label("exampleLabel", texts["ins.preview"], 146, 94, 146)
        d.edit("example", 146, 106, 146, readonly=True, help_text=texts["ins.preview"])
        d.label("hint", texts["ins.hint"] if on_insert else "", 8, 150, 284, 10)
        if on_insert:
            d.button("insert", texts["ins.insert"], 176, 160, 56, default=True, callback=self.insert)
            d.button("close", texts["close"], 236, 160, 56, callback=lambda: d.end(0))
            d._listeners.append(("columns", _Action(self.insert)))  # double-click on a column
        else:
            d.button("ok", texts["ok"], 176, 160, 56, default=True, callback=self._accept)
            d.button("cancel", texts["cancel"], 236, 160, 56, callback=lambda: d.end(0))
        d.on_change(["columns"], self._column_changed)
        d.on_change(["kind"], self._show_example)
        self._initial_kind = kind
        d.on_ready = self._column_changed

    def _column(self):
        index = self.d.get("columns")
        return self.columns[index] if 0 <= index < len(self.columns) else None

    def _kind(self):
        index = self.d.get("kind")
        return self.kinds[index] if 0 <= index < len(self.kinds) else fmt.TEXT

    def _column_changed(self):
        import uno
        column = self._column()
        if column is None:
            return
        column_kind = self.table.kind(column) if column in self.table.headers else fmt.COL_TEXT
        self.kinds = list(fmt.KINDS_FOR_COLUMN[column_kind])
        values = [r[self.table.column(column)] for r in self.table.rows] if column in self.table.headers else []
        wanted = self._initial_kind if self._initial_kind in self.kinds else fmt.default_kind(column_kind, values)
        self._initial_kind = None
        model = self.d.model.getByName("kind")
        uno.invoke(model, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(self.t["kind." + k] for k in self.kinds))))
        self.d.select("kind", self.kinds.index(wanted))
        self._show_example()

    def _show_example(self):
        column = self._column()
        if column is None or self.row is None or column not in self.table.headers:
            self.d.set_text("example", "")
            return
        self.d.set_text("example", fmt.render(self._kind(), self.table.value(self.row, column), self.words))

    def insert(self):
        column = self._column()
        if column is not None:
            self.on_insert(column, self._kind())

    def _accept(self):
        self.result = self._kind()
        self.d.end(1)

    def run(self, parent_peer):
        """Format mode: the chosen kind or None. Insert mode: None after Close."""
        self.d.execute(parent_peer)
        return self.result
