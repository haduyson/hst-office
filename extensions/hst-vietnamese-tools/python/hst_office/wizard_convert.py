# SPDX-License-Identifier: AGPL-3.0-only
"""TCVN3/VNI -> Unicode dialog: explicit encoding choice, suggestion text, original/result preview."""
from . import encoding, encoding_detect, encoding_writer
from .dialogs import Dialog

PREVIEW_CHARS = 4000


class ConvertWizard:
    def __init__(self, ctx, strings, items, calc=None):
        """`calc` (Calc only): {'single': bool, 'sample': callable(whole_sheet) -> items}; adds the whole-sheet and
        names/notes check boxes."""
        self.s, self.s_cv, self.items, self.calc = strings, strings["convert"], items, calc
        self.whole = self.names_notes = False
        dy = 26 if calc else 0
        self.keys = list(encoding.encodings())
        labels = encoding.encodings()
        self.d = Dialog(ctx, self.s_cv["title"], 420, 250 + dy)
        d = self.d
        d.label("l_src", self.s_cv["source"], 6, 8, 70)
        d.listbox("source", 80, 6, 150, ["-"] + [labels[k] for k in self.keys], selected=0, help_text=self.s_cv["source"])
        joined = "".join(i["text"] + "\n" for i in items)[:PREVIEW_CHARS]
        sug = encoding_detect.suggest(joined)
        best = sug["best"]
        level = sug["candidates"][0]["confidence"] if best else ""
        note = (self.s_cv["suggest"] % (labels[best], self.s_cv["confidence"].get(level, level))) if best else self.s_cv["noSuggest"]
        d.label("suggestion", note, 6, 24, 408, 12, wrap=True)
        d.label("l_orig", self.s_cv["original"], 6, 40, 150)
        d.edit("original", 6, 52, 200, 150, text=joined.replace("\n", "\r\n"), multiline=True, readonly=True, help_text=self.s_cv["original"])
        d.label("l_res", self.s_cv["result"], 212, 40, 150)
        d.edit("result", 212, 52, 202, 150, multiline=True, readonly=True, help_text=self.s_cv["result"])
        if calc:
            if calc["single"]:
                d.check("whole", self.s_cv["wholeSheet"], 6, 206, 408, state=False)
            d.check("namesNotes", self.s_cv["namesNotes"], 6, 218, 408, state=False)
        d.label("status", "", 6, 206 + dy, 408, 22, wrap=True)
        d.button("btnPreview", self.s["common"]["preview"], 6, 232 + dy, 60, callback=self.refresh)
        d.button("btnOk", self.s_cv["apply"], 290, 232 + dy, 60, callback=self._accept, default=True)
        d.button("btnCancel", self.s["common"]["cancel"], 354, 232 + dy, 60, kind=2)

    def chosen(self):
        index = self.d.get("source")
        return self.keys[index - 1] if index > 0 else None

    def refresh(self):
        key = self.chosen()
        if key is None:
            self.d.model.getByName("status").Label = self.s_cv["source"]
            return False
        if self.calc and self.calc["single"]:
            self.items = self.calc["sample"](self.d.get("whole"))
            self.d.set_text("original", "".join(i["text"] + "\n" for i in self.items)[:PREVIEW_CHARS].replace("\n", "\r\n"))
        rows, totals = encoding_writer.plan(self.items, key)
        self.d.set_text("result", "".join(r["new"] + "\n" for r in rows)[:PREVIEW_CHARS].replace("\n", "\r\n"))
        status = self.s_cv["summary"] % (totals["converted"], totals["unmapped"], 0)
        if totals["skipped_unicode"]:
            status += " " + self.s_cv["unicodeSkipped"] % totals["skipped_unicode"]
        self.d.model.getByName("status").Label = status
        return True

    def _accept(self):
        if self.refresh():
            self.accepted = self.chosen()
            if self.calc:
                self.whole = bool(self.calc["single"] and self.d.get("whole"))
                self.names_notes = self.d.get("namesNotes")
            self.d.end(1)

    def run(self, parent_peer=None):
        """Returns the explicitly chosen encoding key, or None when cancelled."""
        self.accepted = None
        self.d.execute(parent_peer)
        return self.accepted
