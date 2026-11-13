# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ "Hoàn tất và trộn" (mockup 04): what to do (edit, print, one PDF / DOCX per person, e-mail), which
recipients (all checked, the one shown, a range), the file-name pattern with its column picker and a live example,
the folder, and the e-mail column and subject. Returns a mail_merge_output.Request or None."""
import uno

from . import mail_merge_output as out
from . import mail_merge_table as mt
from .dialogs import Dialog

ACTIONS = (out.EDIT, out.PRINT, out.PDF, out.DOCX, out.MAIL)
FILES, MAILS = (out.PDF, out.DOCX), (out.MAIL,)


class FinishDialog:
    def __init__(self, ctx, texts, session, action=out.PDF):
        self.ctx, self.t, self.session, self.table = ctx, texts, session, session.table
        self.checked = session.checked()
        self.request = None
        meta = session.meta
        self.mail_columns = out.mail_columns(self.table)
        name_col = next((h for h, k in zip(self.table.headers, self.table.kinds) if k == "text"), self.table.headers[0])
        pattern = meta["pattern"] or texts["fin.pattern"] % name_col
        d = self.d = Dialog(ctx, texts["fin.title"], 300, 262)
        d.label("what", texts["fin.what"], 8, 6, 284)
        for i, name in enumerate(ACTIONS):
            d._add("RadioButton", "a_" + name, 14, 18 + i * 12, 278, 10, Label=texts["fin." + name],
                   State=1 if name == action else 0, HelpText=texts["fin." + name])
        d.label("who", texts["fin.who"], 8, 82, 284)
        count = len(self.checked)
        for i, (name, label) in enumerate((("all", texts["fin.all"] % count), ("current", texts["fin.current"]),
                                           ("range", texts["fin.range"]))):
            d._add("RadioButton", "w_" + name, 14, 94 + i * 12, 70 if name == "range" else 278, 10, Label=label,
                   State=1 if name == "all" else 0, HelpText=label)
        for name, x, value in (("from", 86, 1), ("to", 150, max(1, count))):
            d._add("NumericField", name, x, 117, 40, 12, Value=float(value), ValueMin=1.0, ValueMax=float(max(1, count)),
                   DecimalAccuracy=0, Spin=True, StrictFormat=True, HelpText=texts["fin.range"])
        d.label("toLabel", texts["fin.to"], 130, 119, 18)
        d.label("nameLabel", texts["fin.name"], 8, 136, 284)
        d.edit("pattern", 8, 148, 190, text=pattern, help_text=texts["fin.name"])
        d.listbox("addColumn", 202, 148, 90, [texts["fin.add-column"]] + list(self.table.headers), 0,
                  help_text=texts["fin.add-column"])
        d.label("example", "", 8, 163, 284)
        d.label("folderLabel", texts["fin.folder"], 8, 176, 284)
        d.edit("folder", 8, 188, 210, text=meta.get("folder") or _default_folder(meta), help_text=texts["fin.folder"])
        d.button("browse", texts["fin.browse"], 222, 187, 70, callback=self.browse)
        d.label("mailLabel", texts["fin.mail-column"], 8, 205, 70)
        d.listbox("mailColumn", 80, 203, 90, self.mail_columns or [""], 0, help_text=texts["fin.mail-column"])
        d.label("subjectLabel", texts["fin.subject"], 176, 205, 40)
        d.edit("subject", 216, 203, 76, help_text=texts["fin.subject"])
        d.check("attach", texts["fin.attach"], 80, 219, 212, False)
        d.button("run", texts["fin.run"], 176, 242, 56, default=True, callback=self.accept)
        d.button("cancel", texts["cancel"], 236, 242, 56, callback=lambda: d.end(0))
        d.on_change(["pattern"], self.update)
        d.on_change(["addColumn"], self.add_column)
        d.on_ready = self._ready

    def _ready(self):
        from .dialogs import _Changed
        listener = self._radio_listener = _Changed(self.update)
        for name in ACTIONS:
            self.d.dialog.getControl("a_" + name).addItemListener(listener)
        self.update()

    def action(self):
        return next(name for name in ACTIONS if self.d.model.getByName("a_" + name).State)

    def update(self):
        action = self.action()
        for name in ("nameLabel", "pattern", "addColumn", "example", "folderLabel", "folder", "browse"):
            self.d.model.getByName(name).Enabled = action in FILES
        for name in ("mailLabel", "mailColumn", "subjectLabel", "subject", "attach"):
            self.d.model.getByName(name).Enabled = action in MAILS
        if self.checked:
            row = self.table.rows[self.checked[0]]
            example = mt.file_name(self.d.get("pattern"), self.table, row) + (".docx" if action == out.DOCX else ".pdf")
            self.d.model.getByName("example").Label = self.t["fin.example"] % example

    def add_column(self):
        index = self.d.get("addColumn")
        if index > 0:
            self.d.set_text("pattern", self.d.get("pattern") + "{%s}" % self.table.headers[index - 1])
            self.d.select("addColumn", 0)

    def browse(self):
        picker = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FolderPicker", self.ctx)
        current = self.d.get("folder")
        try:
            if current:
                picker.setDisplayDirectory(uno.systemPathToFileUrl(current))
        except Exception:  # noqa: BLE001 - folder gone: the picker's own default
            pass
        if picker.execute() == 1:
            self.d.set_text("folder", uno.fileUrlToSystemPath(picker.getDirectory()))

    def _indexes(self):
        model = self.d.model
        if model.getByName("w_current").State:
            _row, position, total = self.session.current_row()
            return self.checked[position:position + 1] if total else []
        if model.getByName("w_range").State:
            first, last = int(model.getByName("from").Value), int(model.getByName("to").Value)
            return self.checked[max(1, first) - 1:max(first, last)]
        return list(self.checked)

    def accept(self):
        from .dialogs import message_box
        action, peer = self.action(), self.d.dialog.getPeer()
        folder = self.d.get("folder").strip()
        if action in FILES and not folder:
            return message_box(self.ctx, peer, self.t["title"], self.t["err.no-folder"])
        mail_index = self.d.get("mailColumn")
        if action in MAILS and not self.mail_columns:
            return message_box(self.ctx, peer, self.t["title"], self.t["err.no-mail-column"])
        indexes = self._indexes()
        if not indexes:
            return message_box(self.ctx, peer, self.t["title"], self.t["err.none-checked"])
        self.request = out.Request(action, indexes, self.d.get("pattern"), folder,
                                   self.mail_columns[mail_index] if self.mail_columns else "",
                                   self.d.get("subject"), self.d.get("attach"))
        self.d.end(1)

    def run(self, parent_peer):
        if self.d.execute(parent_peer) == 1 and self.request:
            if self.request.action in FILES:
                self.session.meta.update(pattern=self.request.pattern, folder=self.request.folder)
                self.session.save()
            return self.request
        return None


def _default_folder(meta):
    import os
    return os.path.dirname(meta["source"]) if meta["source"] else os.path.expanduser("~")
