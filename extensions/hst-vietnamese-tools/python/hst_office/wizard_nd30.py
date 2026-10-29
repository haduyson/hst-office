# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 administrative-document wizard dialog for Writer (fields, preview, validation). Writes nothing itself."""
from . import nd30, nd30_layout
from .dialogs import Dialog

SINGLE = ("parentAgency", "agency", "summary", "signerAuthority", "signerTitle", "signerName")
MULTI = {"kinhGui": 26, "body": 50, "recipients": 26}


class Nd30Wizard:
    def __init__(self, ctx, strings):
        self.s, self.s_nd = strings, strings["nd30"]
        self.data = nd30.rules()
        self.types = [t["id"] for t in self.data["documentTypes"]]
        self.d = Dialog(ctx, self.s_nd["title"], 520, 340)
        self._build()

    def _row(self, key, y, h=12, multiline=False, x=78, w=170, label_w=70):
        self.d.label("l_" + key, self.s_nd[key], 6, y + 2, label_w)
        return self.d.edit(key, x, y, w, h, multiline=multiline, help_text=self.s_nd[key])

    def _build(self):
        d = self.d
        d.label("l_type", self.s_nd["type"], 6, 8, 70)
        d.listbox("type", 78, 6, 170, [self.s_nd["types"][t] for t in self.types], help_text=self.s_nd["type"])
        self._row("parentAgency", 22)
        self._row("agency", 38)
        self._row("number", 54, x=78, w=40)
        d.label("l_symbol", self.s_nd["symbol"], 124, 56, 30)
        d.edit("symbol", 156, 54, 92, help_text=self.s_nd["symbol"])
        self._row("place", 70, x=78, w=70)
        d.label("l_date", self.s_nd["date"], 152, 72, 54)
        d.edit("date", 208, 70, 40, help_text=self.s_nd["date"])
        self._row("summary", 86)
        self._row("kinhGui", 102, 26, True)
        self._row("body", 132, 50, True)
        self._row("signerAuthority", 186)
        self._row("signerTitle", 202)
        self._row("signerName", 218)
        self._row("recipients", 234, 26, True)
        d.check("applyPage", self.s_nd["applyPage"], 6, 266, 244)
        d.check("pageNumbers", self.s_nd["pageNumbers"], 16, 278, 234)
        d.label("legal", self.s_nd["legal"], 6, 292, 244, 22, wrap=True)
        d.edit("preview", 256, 6, 258, 308, multiline=True, readonly=True, help_text=self.s["common"]["preview"])
        d.button("btnPreview", self.s["common"]["preview"], 6, 320, 60, callback=self.refresh)
        d.button("btnOk", self.s["common"]["ok"], 392, 320, 60, callback=self._accept, default=True)
        d.button("btnCancel", self.s["common"]["cancel"], 454, 320, 60, kind=2)

    def read(self):
        """(type_id, fields) from the form; date is normalised later by nd30.format_issue_date."""
        fields = {k: self.d.get(k) for k in nd30.FIELD_KEYS}
        return self.types[max(0, self.d.get("type"))], fields

    def set_fields(self, type_id=None, fields=None):
        if type_id:
            self.d.select("type", self.types.index(type_id))
        for key, value in (fields or {}).items():
            self.d.set_text(key, value)

    def errors(self):
        type_id, fields = self.read()
        result = nd30.validate_fields(type_id, fields, self.data)
        codes = self.s_nd["codes"]
        return ["%s (%s)" % (e["field"], codes.get(e["code"], e["code"])) for e in result["errors"]]

    def refresh(self):
        errs = self.errors()
        if errs:
            self.d.set_text("preview", self.s_nd["errors"] % ", ".join(errs))
            return False
        type_id, fields = self.read()
        self.d.set_text("preview", nd30_layout.layout_to_text(nd30_layout.build_layout(type_id, fields, data=self.data)).replace("\n", "\r\n"))
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
