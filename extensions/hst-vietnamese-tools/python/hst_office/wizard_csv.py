# SPDX-License-Identifier: AGPL-3.0-only
"""CSV import dialog for Calc: file, strict-UTF-8 decode, delimiter choice, cell-type choice, preview."""
import re

from . import csv_import
from .dialogs import Dialog


class CsvWizard:
    def __init__(self, ctx, strings, picker):
        self.s, self.s_csv, self.ctx, self.picker = strings, strings["csv"], ctx, picker
        self.delims = [",", ";", "\t"]
        self.text = None
        d = self.d = Dialog(ctx, self.s_csv["title"], 400, 210)
        d.label("l_file", self.s_csv["file"], 6, 8, 40)
        d.edit("path", 48, 6, 270, help_text=self.s_csv["file"], readonly=True)
        d.button("btnBrowse", self.s_csv["choose"], 322, 5, 72, callback=self.browse)
        d.label("l_delim", self.s_csv["delimiter"], 6, 26, 60)
        d.listbox("delim", 68, 24, 100, [self.s_csv["delims"][x] for x in self.delims], help_text=self.s_csv["delimiter"])
        d.label("l_mode", self.s_csv["mode"], 176, 26, 40)
        d.listbox("mode", 218, 24, 176, [self.s_csv["modeText"], self.s_csv["modeGeneral"]], help_text=self.s_csv["mode"])
        d.label("status", "", 6, 42, 388, 22, wrap=True)
        d.edit("preview", 6, 66, 388, 112, multiline=True, readonly=True, help_text=self.s["common"]["preview"])
        d.button("btnLoad", self.s_csv["load"], 6, 188, 70, callback=self.load)
        d.button("btnOk", self.s["common"]["ok"], 262, 188, 60, callback=self._accept, default=True)
        d.button("btnCancel", self.s["common"]["cancel"], 326, 188, 60, kind=2)

    def _status(self, text):
        self.d.model.getByName("status").Label = text

    def browse(self):
        path = self.picker()
        if not path:
            return
        self.d.set_text("path", path)
        try:
            with open(path, "rb") as handle:
                raw = handle.read(csv_import.limits()["maxBytes"] + 1)
            self.text, bom = csv_import.decode_bytes(raw)
        except (OSError, csv_import.CsvError) as exc:
            self.text = None
            self._status(self.s["csvErrors"].get(getattr(exc, "code", ""), str(exc)))
            return
        suggested = csv_import.suggest_delimiter(self.text)
        self.d.select("delim", self.delims.index(suggested))
        self._status((self.s_csv["bom"] + ". " if bom else "") + self.s_csv["suggested"] % self.s_csv["delims"][suggested])
        self.load()

    def load(self):
        """Parse with the chosen delimiter and show up to 10 rows; returns the rows or None."""
        if self.text is None:
            return None
        try:
            rows = csv_import.parse(self.text, self.delims[max(0, self.d.get("delim"))])
        except csv_import.CsvError as exc:
            self.d.set_text("preview", self._error_text(exc))
            return None
        shown = csv_import.preview(rows)
        self.d.set_text("preview", "\r\n".join(" | ".join(c.replace("\n", "↵").replace("\t", "→") for c in r[:12]) for r in shown))
        return rows

    def _error_text(self, exc):
        """Localized message; for malformed files only the row number of the parser detail is shown
        (Python's csv message is English)."""
        text = self.s["csvErrors"].get(exc.code, exc.code)
        row = re.match(r"row (\d+):", exc.detail or "")
        if exc.code == "malformed":
            return text + (" " + self.s["csvErrors"]["malformedRow"] % int(row.group(1)) if row else "")
        return (text + " " + exc.detail).strip()

    def _accept(self):
        rows = self.load()
        if rows:
            self.accepted = {"rows": rows, "mode": ("text", "general")[max(0, self.d.get("mode"))]}
            self.d.end(1)

    def run(self, parent_peer=None):
        self.accepted = None
        self.d.execute(parent_peer)
        return self.accepted
