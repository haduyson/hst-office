# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 administrative-document wizard dialog for Writer (fields, live preview, validation). Writes nothing itself.

Layout (Map AppFont units): a form column on the left, labels in their own 96-unit column (long hints wrap onto
a second line instead of being cut off), and on the right a monospace page preview that is redrawn on every
change of a field or of the document type (nd30_preview).
"""
import datetime

from . import nd30, nd30_layout, nd30_preview
from .dialogs import Dialog

WIDTH, HEIGHT = 600, 300  # about 675 px high with common Linux fonts: fits a 1366x768 screen
LABEL_X, LABEL_W = 8, 84
FIELD_X, FIELD_W = 96, 200
PREVIEW_X = FIELD_X + FIELD_W + 10
PREVIEW_W = WIDTH - PREVIEW_X - 8
PREVIEW_CHARS = 70
MONO = "Liberation Mono;Consolas;Menlo;DejaVu Sans Mono;Courier New"  # all carry precomposed Vietnamese
ERROR_COLOR = 0xC5221F


class Nd30Wizard:
    def __init__(self, ctx, strings):
        self.s, self.s_nd = strings, strings["nd30"]
        self.data = nd30.rules()
        self.types = [t["id"] for t in self.data["documentTypes"]]
        self.d = Dialog(ctx, self.s_nd["title"], WIDTH, HEIGHT)
        self._build()
        self.refresh()

    def _label(self, key, y, h=10):
        self.d.label("l_" + key, self.s_nd[key], LABEL_X, y + 2, LABEL_W, h, wrap=h > 10)

    def _row(self, key, y, h=12, multiline=False, label_h=10):
        self._label(key, y, label_h)
        return self.d.edit(key, FIELD_X, y, FIELD_W, h, multiline=multiline, help_text=self.s_nd.get(key + "Help", self.s_nd[key]))

    def _build(self):
        d, s = self.d, self.s_nd
        self._label("type", 8)
        d.listbox("type", FIELD_X, 6, FIELD_W, [s["types"][t] for t in self.types], help_text=s["type"])
        self._row("parentAgency", 22)
        self._row("agency", 38)
        self._label("number", 54)
        d.edit("number", FIELD_X, 54, 40, help_text=s["numberHelp"])
        d.label("l_symbol", s["symbol"], FIELD_X + 46, 56, 38)
        d.edit("symbol", FIELD_X + 86, 54, FIELD_W - 86, help_text=s["symbolHelp"])
        self._label("place", 70)
        d.edit("place", FIELD_X, 70, 90, help_text=s["place"])
        d.label("l_date", s["date"], FIELD_X + 96, 72, 22)
        d.edit("date", FIELD_X + 120, 70, FIELD_W - 120, text=datetime.date.today().strftime("%d/%m/%Y"), help_text=s["dateHelp"])
        self._row("summary", 86, 18, True)
        self._row("kinhGui", 108, 22, True, label_h=20)
        self._row("body", 134, 34, True, label_h=20)
        self._row("signerAuthority", 172, label_h=20)
        self._row("signerTitle", 194)
        self._row("signerName", 210)
        self._row("recipients", 226, 22, True, label_h=20)
        check = d.check("applyPage", s["applyPage"], LABEL_X, 252, FIELD_X + FIELD_W - LABEL_X, h=12)
        check.MultiLine = True  # wraps instead of being cut off when a translation is longer
        d.check("pageNumbers", s["pageNumbers"], LABEL_X + 10, 266, FIELD_X + FIELD_W - LABEL_X - 10)
        d.label("legal", s["legal"], LABEL_X, 280, FIELD_X + FIELD_W - LABEL_X, 16, wrap=True)
        heading = d.label("l_preview", s["previewHeading"], PREVIEW_X, 8, PREVIEW_W, 10)
        heading.FontWeight = 150
        preview = d.edit("preview", PREVIEW_X, 20, PREVIEW_W, 228, multiline=True, readonly=True, help_text=self.s["common"]["preview"])
        font = preview.FontDescriptor
        font.Name, font.Height = MONO, 8
        preview.FontDescriptor = font
        status = d.label("status", "", PREVIEW_X, 250, PREVIEW_W, 24, wrap=True)  # room for several errors
        status.TextColor = ERROR_COLOR
        d.button("btnOk", s["insert"], WIDTH - 8 - 64 - 4 - 64, HEIGHT - 22, 64, callback=self._accept, default=True)
        d.button("btnCancel", self.s["common"]["cancel"], WIDTH - 8 - 64, HEIGHT - 22, 64, kind=2)
        d.on_change(("type",) + nd30.FIELD_KEYS, self.refresh)

    def read(self):
        """(type_id, fields) from the form; date is normalised later by nd30.format_issue_date."""
        fields = {k: self.d.get(k) for k in nd30.FIELD_KEYS}
        return self.types[max(0, self.d.get("type"))], fields

    def set_fields(self, type_id=None, fields=None):
        if type_id:
            self.d.select("type", self.types.index(type_id))
        for key, value in (fields or {}).items():
            self.d.set_text(key, value)
        self.refresh()

    def errors(self):
        type_id, fields = self.read()
        result = nd30.validate_fields(type_id, fields, self.data)
        codes = self.s_nd["codes"]
        return ["%s (%s)" % (e["field"], codes.get(e["code"], e["code"])) for e in result["errors"]]

    def _error_text(self):
        """Errors for the user: field labels instead of internal keys."""
        type_id, fields = self.read()
        codes, s = self.s_nd["codes"], self.s_nd
        return ["%s: %s" % (s.get(e["field"], e["field"]).split("\n")[0], codes.get(e["code"], e["code"]))
                for e in nd30.validate_fields(type_id, fields, self.data)["errors"]]

    def refresh(self):
        """Redraw the preview; on invalid input keep the last good preview and show what to fix. True if valid."""
        errs = self._error_text()
        self.d.model.getByName("status").Label = (self.s_nd["errors"] % "; ".join(errs)) if errs else ""
        self.d.model.getByName("btnOk").Enabled = not errs
        if errs:
            return False
        type_id, fields = self.read()
        layout = nd30_layout.build_layout(type_id, fields, data=self.data)
        self.d.set_text("preview", nd30_preview.layout_to_preview(layout, PREVIEW_CHARS).replace("\n", "\r\n"))
        return True

    def outcome(self):
        type_id, fields = self.read()
        return {"type": type_id, "fields": fields, "apply_page": self.d.get("applyPage"), "page_numbers": self.d.get("pageNumbers")}

    def _accept(self):
        if self.refresh():
            self.accepted = self.outcome()  # read before the dialog (and its models) is disposed
            self.d.end(1)

    def run(self, parent_peer=None):
        """Show modally. Returns None on Cancel, else {'type','fields','apply_page','page_numbers'}."""
        self.accepted = None
        self.d.execute(parent_peer)
        return self.accepted
