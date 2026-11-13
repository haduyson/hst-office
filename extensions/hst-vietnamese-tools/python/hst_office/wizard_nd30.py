# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 administrative-document wizard dialog for Writer (fields, live preview, validation). Writes nothing itself.

Layout (Map AppFont units): a form column on the left, labels in their own 96-unit column (long hints wrap onto
a second line instead of being cut off), and on the right a monospace page preview that is redrawn on every
change of a field or of the document type (nd30_preview).
"""
import datetime

from . import nd30, nd30_layout, nd30_prefs, nd30_preview, nd30_rule_length, wizard_scroll_band as scroll_band
from .dialogs import Dialog, palette
from .wizard_nd30_rule import NAMES as RULE_NAMES, AgencyRuleRow
from .wizard_type_picker import TypePicker

TOP = 14  # height of the description line above the form
WIDTH, HEIGHT = 570, 316 + TOP  # about 730 px high with common Linux fonts; smaller screens: _compact
LABEL_X, LABEL_W = 8, 84
FIELD_X, FIELD_W = 96, 200
PREVIEW_X = FIELD_X + FIELD_W + 10
PREVIEW_W = WIDTH - PREVIEW_X - 8
PREVIEW_CHARS = 66
MONO = "Liberation Mono;Consolas;Menlo;DejaVu Sans Mono;Courier New"  # all carry precomposed Vietnamese


class Nd30Wizard:
    def __init__(self, ctx, strings):
        self.ctx, self.s, self.s_nd = ctx, strings, strings["nd30"]
        self.data = nd30.rules()
        self.compact, self.band = False, None
        self.colours = palette(ctx)  # muted/error text readable on light and dark dialogs
        self.d = Dialog(ctx, self.s_nd["title"], WIDTH, HEIGHT)
        self.picker = TypePicker(self.d, self.data["documentTypes"], self.s_nd["groups"], self.refresh,
                                 self.s_nd["typeSearchHelp"])
        self._build()
        self.refresh()

    def _label(self, key, y, h=10):
        self.d.label("l_" + key, self.s_nd[key], LABEL_X, y + 2 + TOP, LABEL_W, h, wrap=h > 10)

    def _row(self, key, y, h=12, multiline=False, label_h=10):
        self._label(key, y, label_h)
        return self.d.edit(key, FIELD_X, y + TOP, FIELD_W, h, multiline=multiline, help_text=self.s_nd.get(key + "Help", self.s_nd[key]))

    def _build(self):
        d, s = self.d, self.s_nd
        self.d.label("description", s["description"], LABEL_X, 4, WIDTH - 2 * LABEL_X, 10, wrap=True).TextColor = self.colours["muted"]
        self._label("type", 8)
        d.edit("type", FIELD_X, 6 + TOP, FIELD_W - 14, text=self.picker.label_of(self.picker.current), help_text=s["typeSearchHelp"])
        # The arrow is for the mouse (Down opens the list from the field): not a Tab stop, so Tab goes from the type
        # straight to the next field instead of to a button that swallows what the user types next.
        d.button("typeOpen", "▾", FIELD_X + FIELD_W - 13, 6 + TOP, 13, h=12, callback=self.picker.toggle).Tabstop = False
        self._row("parentAgency", 22)
        self._row("agency", 38)
        self._label("number", 54)
        d.edit("number", FIELD_X, 54 + TOP, 40, help_text=s["numberHelp"])
        d.label("l_symbol", s["symbol"], FIELD_X + 46, 56 + TOP, 38)
        d.edit("symbol", FIELD_X + 86, 54 + TOP, FIELD_W - 86, help_text=s["symbolHelp"])
        self._label("place", 70)
        d.edit("place", FIELD_X, 70 + TOP, 90, help_text=s["place"])
        d.label("l_date", s["date"], FIELD_X + 96, 72 + TOP, 22)
        d.edit("date", FIELD_X + 120, 70 + TOP, FIELD_W - 120, text=datetime.date.today().strftime("%d/%m/%Y"), help_text=s["dateHelp"])
        self._row("summary", 86, 18, True)
        self._row("kinhGui", 108, 22, True, label_h=20)
        self._row("body", 134, 22, True, label_h=20)
        self._row("signerAuthority", 160, label_h=20)
        self._row("signerTitle", 182)
        self._label("signerName", 198)
        d.edit("signerName", FIELD_X, 198 + TOP, 90, help_text=s["signerName"])
        d.label("l_secretaryName", s["secretaryName"], FIELD_X + 96, 200 + TOP, 22)
        d.edit("secretaryName", FIELD_X + 120, 198 + TOP, FIELD_W - 120, help_text=s["secretaryNameHelp"])
        self._row("recipients", 214, 20, True, label_h=20)
        self._row("contact", 236)  # 16 units to the next row: room for the macOS edit frame (dialog_edit_heights)
        # the user's last choice (ND30 II.2b: 1/3 to 1/2 of the agency line), remembered per user (nd30_prefs)
        self.rule = AgencyRuleRow(d, s, nd30_prefs.load_agency_rule(self.ctx), LABEL_X, LABEL_W, FIELD_X, FIELD_W, 252 + TOP)
        check = d.check("applyPage", s["applyPage"], LABEL_X, 268 + TOP, FIELD_X + FIELD_W - LABEL_X, h=12)
        check.MultiLine = True  # wraps instead of being cut off when a translation is longer
        d.check("pageNumbers", s["pageNumbers"], LABEL_X + 10, 282 + TOP, 208)
        # two-sided: Party documents mirror their margins (05-HD/VPTW IV.4.2); ND30 types keep them (nd30_duplex)
        d.check("duplex", s["duplex"], LABEL_X + 222, 282 + TOP, FIELD_X + FIELD_W - LABEL_X - 222, state=False).HelpText = s["duplexHelp"]
        d.label("legal", s["legal"], LABEL_X, 296 + TOP, FIELD_X + FIELD_W - LABEL_X, 16, wrap=True)
        heading = d.label("l_preview", s["previewHeading"], PREVIEW_X, 8 + TOP, PREVIEW_W, 10)
        heading.FontWeight = 150
        preview = d.edit("preview", PREVIEW_X, 20 + TOP, PREVIEW_W, 244, multiline=True, readonly=True, help_text=self.s["common"]["preview"])
        font = preview.FontDescriptor
        font.Name, font.Height = MONO, 8
        preview.FontDescriptor = font
        status = d.label("status", "", PREVIEW_X, 266 + TOP, PREVIEW_W, 24, wrap=True)  # room for several errors
        status.TextColor = self.colours["error"]
        d.button("btnOk", s["insert"], WIDTH - 8 - 64 - 4 - 64, HEIGHT - 22, 64, callback=self._accept, default=True)
        d.button("btnCancel", self.s["common"]["cancel"], WIDTH - 8 - 64, HEIGHT - 22, 64, kind=2)
        d.on_change(nd30.FIELD_KEYS + RULE_NAMES, self.refresh)
        d.on_oversize = self._compact
        d.on_ready, d.on_closed = self.picker.attach, self.picker.detach

    def _compact(self):
        """Screen too small for the side-by-side layout (about 1200 px wide at 100% on Windows): drop the preview column.

        The error line takes the place of the legal note (see refresh), the buttons sit directly under it; a dialog
        still taller than the work area scrolls its form (wizard_scroll_band)."""
        m, width = self.d.model, FIELD_X + FIELD_W + 8
        self.compact = True
        m.getByName("description").Width = width - 2 * LABEL_X
        for name in ("l_preview", "preview"):
            m.getByName(name).EnableVisible = False
        legal = m.getByName("legal")
        status = m.getByName("status")
        status.PositionX, status.PositionY, status.Width, status.Height = LABEL_X, legal.PositionY, width - 2 * LABEL_X, legal.Height
        row = legal.PositionY + legal.Height + 2
        m.Width, m.Height = width, row + 14 + 6
        for name, x in (("btnOk", width - 8 - 64 - 4 - 64), ("btnCancel", width - 8 - 64)):
            button = m.getByName(name)
            button.PositionX, button.PositionY = x, row
        # still taller than the work area (1366x768 at 125 %): the form scrolls, check boxes and buttons stay in view
        below = ("applyPage", "pageNumbers", "duplex", "legal", "status", "btnOk", "btnCancel")
        form = [n for n in m.ElementNames if n not in below + ("description", "l_preview", "preview")]
        bar_x = FIELD_X + FIELD_W + 2
        self.band = scroll_band.fit(self.d, form, TOP + 4, m.getByName("applyPage").PositionY - 2, below,
                                    scroll_band.max_height(self.d), bar_x)
        if self.band:
            m.Width = bar_x + scroll_band.BAR_WIDTH + 4

    def read(self):
        """(type_id, fields) from the form; date is normalised later by nd30.format_issue_date."""
        fields = {k: self.d.get(k) for k in nd30.FIELD_KEYS}
        if self.rule.value():
            fields[nd30_rule_length.FIELD] = self.rule.value()
        return self.picker.current, fields

    def set_fields(self, type_id=None, fields=None):
        if type_id:
            self.picker.current = type_id
            self.d.set_text("type", self.picker.label_of(type_id))
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
                for e in nd30.validate_fields(type_id, fields, self.data)["errors"]] + ([self.rule.error()] if self.rule.error() else [])

    def refresh(self):
        """Redraw the preview; on invalid input keep the last good preview and show what to fix. True if valid."""
        errs = self._error_text()
        status = self.d.model.getByName("status")
        status.Label, status.TextColor = (self.s_nd["errors"] % "; ".join(errs)) if errs else "", self.colours["error"]
        self.d.model.getByName("btnOk").Enabled = not errs
        if self.compact:  # the error line and the legal note share one row
            self.d.model.getByName("legal").EnableVisible = not errs
        if errs:
            return False
        type_id, fields = self.read()
        kind = nd30.get_type(type_id, self.data)
        self.rule.sync(kind["profile"] != "dang" and kind.get("module") != "sheets")  # Party forms: a star, no rule
        self.d.model.getByName("description").Label = self.s_nd["descriptions"][kind["profile"]]
        register = kind.get("module") == "sheets"
        self.d.model.getByName("btnOk").Label = self.s_nd["openSheet" if register else "insert"]
        if register:
            self.d.set_text("preview", self.s_nd["registerNote"])
            return True
        layout = nd30_layout.build_layout(type_id, fields, data=self.data)
        self.d.set_text("preview", nd30_preview.layout_to_preview(layout, PREVIEW_CHARS).replace("\n", "\r\n"))
        if nd30_rule_length.out_of_range(layout):  # a gentle note: the user may want it so
            status.Label, status.TextColor = self.s_nd["agencyRuleWarning"], self.colours["muted"]
            self.d.model.getByName("legal").EnableVisible = not self.compact  # compact: the note takes its row
        return True

    def outcome(self):
        type_id, fields = self.read()
        return {"type": type_id, "fields": fields, "apply_page": self.d.get("applyPage"), "page_numbers": self.d.get("pageNumbers"),
                "duplex": self.d.get("duplex")}

    def _accept(self):
        if self.refresh():
            self.accepted = self.outcome()  # read before the dialog (and its models) is disposed
            nd30_prefs.save_agency_rule(self.ctx, self.rule.value())
            self.d.end(1)

    def run(self, parent_peer=None):
        """Show modally. Returns None on Cancel, else {'type','fields','apply_page','page_numbers','duplex'}."""
        self.accepted = None
        self.d.execute(parent_peer)
        return self.accepted
