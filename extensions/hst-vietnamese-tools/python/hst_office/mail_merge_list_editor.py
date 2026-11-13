# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Chọn người nhận ▸ Nhập danh sách mới: type a recipient list without opening Sheets. The columns are
editable (up to MAX_COLUMNS, Vietnamese defaults); the table shows every person, the form below edits the selected
one; "Thêm người" / "Xóa người" add and remove. Returns (headers, rows of str) or None; the caller saves it as
.xlsx or .ods (mail_merge_list_commands.py)."""
import unohelper
from com.sun.star.awt import XTextListener

from .dialogs import Dialog

MAX_COLUMNS = 8
DEFAULT_COLUMNS = ("Danh xưng", "Họ và tên", "Chức vụ", "Đơn vị", "Địa chỉ", "Email")


class _Typed(unohelper.Base, XTextListener):
    def __init__(self, callback, index):
        self.callback, self.index = callback, index

    def textChanged(self, event):
        self.callback(self.index)

    def disposing(self, event):
        pass


def parse_columns(text):
    """Column names from "Họ và tên; Đơn vị; ..." (empty and repeated names dropped, at most MAX_COLUMNS)."""
    names = []
    for part in (text or "").replace(",", ";").split(";"):
        name = " ".join(part.split())
        if name and name not in names:
            names.append(name)
    return names[:MAX_COLUMNS]


class ListEditor:
    def __init__(self, ctx, texts, columns=DEFAULT_COLUMNS, rows=None):
        self.t, self.columns = texts, list(columns)[:MAX_COLUMNS]
        self.rows = [list(r) for r in rows or [[""] * len(self.columns)]]
        self.current, self.result, self.loading = 0, None, False
        d = self.d = Dialog(ctx, texts["new.title"], 420, 262)
        d.label("colLabel", texts["new.columns"], 8, 8, 60)
        d.edit("columns", 70, 6, 276, text="; ".join(self.columns), help_text=texts["new.columns"])
        d.button("apply", texts["new.apply"], 350, 5, 62, callback=self.apply_columns)
        grid = d.model.createInstance("com.sun.star.awt.grid.UnoControlGridModel")
        grid.PositionX, grid.PositionY, grid.Width, grid.Height = 8, 24, 404, 96
        grid.ShowRowHeader, grid.HelpText = True, texts["new.title"]
        from com.sun.star.view.SelectionType import SINGLE
        grid.SelectionModel = SINGLE
        d.model.insertByName("grid", grid)
        for i in range(MAX_COLUMNS):
            x, y = 8 + (i % 2) * 206, 126 + (i // 2) * 16
            d.label("l%d" % i, "", x, y + 2, 70)
            d.edit("e%d" % i, x + 72, y, 126, help_text="")
        d.button("add", texts["new.add"], 8, 194, 80, callback=self.add_row)
        d.button("remove", texts["new.remove"], 92, 194, 80, callback=self.remove_row)
        d.label("hint", texts["new.hint"], 8, 214, 404, 18, wrap=True)
        d.button("ok", texts["new.save"], 296, 242, 56, default=True, callback=self._accept)
        d.button("cancel", texts["cancel"], 356, 242, 56, callback=lambda: d.end(0))
        d.on_ready = self._ready

    def _ready(self):
        self.listeners = [_Typed(self._typed, i) for i in range(MAX_COLUMNS)]
        for i, listener in enumerate(self.listeners):
            self.d.dialog.getControl("e%d" % i).addTextListener(listener)
        self.grid_control = self.d.dialog.getControl("grid")
        from .mail_merge_recipients_dialog import _Selected
        self.grid_control.addSelectionListener(_Selected(self._selected))
        self._layout()

    def _layout(self):
        """Columns of the table and labels of the form follow self.columns."""
        model = self.d.model.getByName("grid").ColumnModel
        while model.getColumnCount():
            model.removeColumn(0)
        for name in self.columns:
            column = model.createColumn()
            column.Title, column.ColumnWidth, column.MinWidth, column.Flexibility = name, 60, 30, 1
            model.addColumn(column)
        for i in range(MAX_COLUMNS):
            visible = i < len(self.columns)
            self.d.model.getByName("l%d" % i).Label = self.columns[i] if visible else ""
            self.d.model.getByName("e%d" % i).HelpText = self.columns[i] if visible else ""  # screen readers
            self.d.dialog.getControl("e%d" % i).setVisible(visible)
        self.rows = [(r + [""] * len(self.columns))[:len(self.columns)] for r in self.rows]
        self._fill()

    def _fill(self):
        data = self.d.model.getByName("grid").GridDataModel
        data.removeAllRows()
        for number, row in enumerate(self.rows, 1):
            data.addRow(str(number), tuple(row))
        self._load(min(self.current, len(self.rows) - 1))

    def _load(self, index):
        self.current, self.loading = max(0, index), True
        try:
            for i in range(len(self.columns)):
                self.d.set_text("e%d" % i, self.rows[self.current][i] if self.rows else "")
        finally:
            self.loading = False
        if self.rows:
            self.grid_control.selectRow(self.current)

    def _selected(self):
        rows = self.grid_control.getSelectedRows()
        if rows and rows[0] != self.current:
            self._load(rows[0])

    def _typed(self, index):
        if self.loading or not self.rows or index >= len(self.columns):
            return
        value = self.d.get("e%d" % index)
        self.rows[self.current][index] = value
        self.d.model.getByName("grid").GridDataModel.updateCellData(index, self.current, value)

    def apply_columns(self):
        names = parse_columns(self.d.get("columns"))
        if names:
            self.columns = names
            self._layout()

    def add_row(self):
        self.rows.append([""] * len(self.columns))
        self.current = len(self.rows) - 1
        self._fill()

    def remove_row(self):
        if len(self.rows) > 1:
            del self.rows[self.current]
            self.current = min(self.current, len(self.rows) - 1)
            self._fill()

    def _accept(self):
        rows = [r for r in self.rows if any(v.strip() for v in r)]
        if not rows:
            from .dialogs import message_box
            return message_box(self.d.ctx, self.d.dialog.getPeer(), self.t["title"], self.t["err.empty"])
        self.result = (list(self.columns), rows)
        self.d.end(1)

    def run(self, parent_peer):
        self.d.execute(parent_peer)
        return self.result
