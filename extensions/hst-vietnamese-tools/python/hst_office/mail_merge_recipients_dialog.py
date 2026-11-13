# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ "Sửa danh sách người nhận" (mockup 02): the recipients in a table with a ☑/☐ column, search without
diacritics, sort by a column or by given name, select all / none / only the matches. OK stores the choice in the
document (mail_merge_store meta); "Đổi danh sách" and "Làm mới" end the dialog with their own result code."""
import unohelper
from com.sun.star.awt import XMouseListener

from . import mail_merge_table as mt
from .dialogs import Dialog

OK, CHANGE, REFRESH = 1, 3, 4
ON, OFF = "☑", "☐"


class _DoubleClick(unohelper.Base, XMouseListener):
    def __init__(self, callback):
        self.callback = callback

    def mousePressed(self, event):
        if event.ClickCount == 2:
            self.callback()

    def mouseReleased(self, event):
        pass

    def mouseEntered(self, event):
        pass

    def mouseExited(self, event):
        pass

    def disposing(self, event):
        pass


class RecipientsDialog:
    def __init__(self, ctx, texts, session):
        self.t, self.session, self.table = texts, session, session.table
        self.excluded = set(session.meta["excluded"])
        self.sorts = [mt.SORT_FILE, mt.SORT_GIVEN_NAME] + list(self.table.headers)
        labels = [texts["rec.sort.file"], texts["rec.sort.given"]] + [texts["rec.sort.column"] % h for h in self.table.headers]
        d = self.d = Dialog(ctx, texts["rec.title"], 440, 262)
        d.label("source", "", 8, 8, 300, 10)
        d.button("change", texts["rec.change"], 316, 5, 58, callback=lambda: d.end(CHANGE))
        d.button("refresh", texts["rec.refresh"], 378, 5, 54, callback=lambda: d.end(REFRESH))
        d.label("searchLabel", texts["rec.search"], 8, 26, 30)
        d.edit("search", 40, 24, 150, help_text=texts["rec.search"])
        d.label("sortLabel", texts["rec.sort"], 200, 26, 34)
        current = session.meta["sort"] if session.meta["sort"] in self.sorts else mt.SORT_FILE
        d.listbox("sort", 236, 24, 130, labels, self.sorts.index(current), help_text=texts["rec.sort"])
        d.check("desc", texts["rec.descending"], 372, 25, 64, session.meta["descending"])
        grid = d.model.createInstance("com.sun.star.awt.grid.UnoControlGridModel")
        grid.PositionX, grid.PositionY, grid.Width, grid.Height = 8, 42, 424, 160
        grid.ShowRowHeader, grid.ShowColumnHeader, grid.HelpText = False, True, texts["rec.title"]
        from com.sun.star.view.SelectionType import SINGLE
        grid.SelectionModel = SINGLE
        columns = grid.ColumnModel
        for title, width in [(texts["rec.check"], 22)] + [(h, 70) for h in self.table.headers]:
            column = columns.createColumn()
            column.Title, column.ColumnWidth, column.MinWidth = title, width, width
            column.Flexibility = 0 if width == 22 else 1  # the ☑ column keeps its width
            columns.addColumn(column)
        d.model.insertByName("grid", grid)
        d.button("toggle", texts["rec.toggle"], 8, 208, 80, callback=self.toggle)
        d.button("all", texts["rec.all"], 92, 208, 80, callback=lambda: self.set_all(True))
        d.button("none", texts["rec.none"], 176, 208, 80, callback=lambda: self.set_all(False))
        d.button("found", texts["rec.found"], 260, 208, 100, callback=self.only_found)
        d.label("hint", texts["rec.hint"], 8, 226, 424, 10)
        d.button("ok", texts["ok"], 314, 242, 56, default=True, callback=self._accept)
        d.button("cancel", texts["cancel"], 376, 242, 56, callback=lambda: d.end(0))
        d.on_change(["search", "sort", "desc"], self.fill)
        self.visible = []
        d.on_ready = self._ready

    def _ready(self):
        self.control = self.d.dialog.getControl("grid")
        self.control.addMouseListener(_DoubleClick(self.toggle))
        self.fill()

    def _order(self):
        index = self.d.get("sort")
        return self.sorts[index if index >= 0 else 0], self.d.get("desc")

    def fill(self):
        by, descending = self._order()
        needle = self.d.get("search")
        self.visible = [i for i in mt.order(self.table, by, descending) if mt.matches(self.table, self.table.rows[i], needle)]
        data = self.d.model.getByName("grid").GridDataModel
        data.removeAllRows()
        for index in self.visible:
            mark = OFF if self.table.keys[index] in self.excluded else ON
            data.addRow(index, tuple([mark] + [self.table.text(self.table.rows[index], h) for h in self.table.headers]))
        self._count()

    def _count(self):
        total = len(self.table.rows)
        checked = total - len([k for k in self.table.keys if k in self.excluded])
        self.d.model.getByName("source").Label = self.t["rec.source"] % (self.session.meta["source"], total, checked)

    def _mark(self, position):
        key = self.table.keys[self.visible[position]]
        data = self.d.model.getByName("grid").GridDataModel
        data.updateCellData(0, position, OFF if key in self.excluded else ON)

    def toggle(self):
        rows = self.control.getSelectedRows()
        for position in rows:
            key = self.table.keys[self.visible[position]]
            self.excluded.symmetric_difference_update({key})
            self._mark(position)
        self._count()

    def set_all(self, checked):
        self.excluded = set() if checked else set(self.table.keys)
        self.fill()

    def only_found(self):
        shown = {self.table.keys[i] for i in self.visible}
        self.excluded = set(self.table.keys) - shown
        self.fill()

    def _accept(self):
        by, descending = self._order()
        self.chosen = dict(excluded=sorted(self.excluded), sort=by, descending=bool(descending))
        self.d.end(OK)

    def run(self, parent_peer):
        """OK (choice stored in the session meta), CHANGE, REFRESH or 0 (cancel)."""
        result = self.d.execute(parent_peer)
        if result == OK:
            self.session.meta.update(self.chosen)
            self.session.save()
        return result
