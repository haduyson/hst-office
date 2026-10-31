# SPDX-License-Identifier: AGPL-3.0-only
"""User-facing HST commands: gather UI input, call the logic modules, report results. One function per command."""
import unohelper

from . import convert_calc_action, csv_calc, encoding_writer, fonts, nd30_layout, nd30_writer, sheets
from .dialogs import message_box
from .wizard_convert import ConvertWizard
from .wizard_csv import CsvWizard
from .wizard_nd30 import Nd30Wizard


class Host:
    """Per-dispatch context: component context, frame, controller, document, strings."""

    def __init__(self, ctx, frame, strings):
        self.ctx, self.frame, self.s = ctx, frame, strings
        self.controller = frame.getController()
        self.doc = self.controller.getModel()
        self.peer = frame.getContainerWindow()

    def say(self, text, error=False):
        message_box(self.ctx, self.peer, self.s["common"]["error"], text, error=error)

    def refuse(self, reasons):
        self.say("\n".join(self.s["blockers"].get(r, r) for r in reasons), error=True)

    def is_writer(self):
        return self.doc.supportsService("com.sun.star.text.TextDocument")

    def is_calc(self):
        return self.doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")


def nd30_wizard(host):
    if not host.is_writer():
        return
    cursor = host.controller.getViewCursor()
    reasons = nd30_writer.check_insertion_point(host.doc, cursor)
    if reasons:
        return host.refuse(reasons)
    choice = Nd30Wizard(host.ctx, host.s).run(host.peer)
    if choice is None:
        return  # Cancel: nothing was written
    layout = nd30_layout.build_layout(choice["type"], choice["fields"])
    result = nd30_writer.insert_layout(host.doc, cursor, layout, apply_page=choice["apply_page"], page_numbers=choice["page_numbers"],
                                       undo_title=host.s["undo"]["nd30"])
    if result["blockers"]:
        return host.refuse(result["blockers"])
    note = host.s["nd30"]["inserted"]
    if result["page"] and result["page"]["headerSkipped"]:
        note += "\n" + host.s["nd30"]["headerSkipped"]
    if fonts.is_font_missing(host.ctx, "Times New Roman"):
        note += "\n" + host.s["nd30"]["fontMissing"] % "Times New Roman"
    host.say(note)


def convert_encoding(host):
    if host.is_calc():
        return convert_calc_action.run(host)
    if not host.is_writer():
        return
    rng, reasons = encoding_writer.check_selection(host.doc, host.controller.getSelection())
    if reasons:
        return host.refuse(reasons)
    items, skipped, protected = encoding_writer.collect(rng)
    if protected:
        return host.refuse(["protected-section"])
    if not items:
        return host.say(host.s["convert"]["nothing"])
    key = ConvertWizard(host.ctx, host.s, items).run(host.peer)
    if key is None:
        return
    result = encoding_writer.apply(host.doc, rng, key, encoding_writer.snapshot(items),
                                   undo_title=host.s["undo"]["convert"] % key.upper())
    if result["blockers"]:
        return host.refuse(result["blockers"])
    host.say(host.s["convert"]["done"] % result["changed_portions"])


def _cell_selection(host):
    selection = host.controller.getSelection()
    ok = selection is not None and any(selection.supportsService("com.sun.star.sheet." + n)
                                       for n in ("SheetCell", "SheetCellRange", "SheetCellRanges"))
    return selection if ok else None


def apply_format(host, kind):
    if not host.is_calc():
        return
    selection = _cell_selection(host)
    reasons = sheets.sheet_blockers(host.controller.getActiveSheet().isProtected(), selection is not None)
    if reasons:
        return host.refuse(["no-selection-cells" if r == "no-selection" else r for r in reasons])
    summary = sheets.apply_format(host.doc, selection, kind)
    note = host.s["sheet"]["formatted"]
    if summary["text_cells"]:
        note += "\n" + host.s["sheet"]["textCells"] % summary["text_cells"]
    host.say(note)


def _pick_csv(host):
    picker = host.ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", host.ctx)
    picker.initialize((0,))  # FILEOPEN_SIMPLE
    picker.setTitle(host.s["csv"]["choose"])
    picker.appendFilter("CSV", "*.csv;*.txt")
    picker.appendFilter("*", "*.*")
    try:
        return unohelper.fileUrlToSystemPath(picker.getSelectedFiles()[0]) if picker.execute() == 1 else None
    finally:
        picker.dispose()


def import_csv(host):
    if not host.is_calc():
        return
    selection = _cell_selection(host)
    if selection is None:
        return host.refuse(["no-selection-cells"])
    address = selection.getRangeAddress() if hasattr(selection, "getRangeAddress") else selection.getRangeAddresses()[0]
    sheet = host.controller.getActiveSheet()
    choice = CsvWizard(host.ctx, host.s, lambda: _pick_csv(host)).run(host.peer)
    if choice is None:
        return
    column, row = address.StartColumn, address.StartRow
    result = csv_calc.write_rows(host.doc, sheet, column, row, choice["rows"], choice["mode"],
                                 undo_title=host.s["undo"]["csv"])
    if result["blockers"] == ["overwrite-needed"]:
        if not message_box(host.ctx, host.peer, host.s["common"]["error"], host.s["csv"]["overwrite"], ask=True):
            return
        result = csv_calc.write_rows(host.doc, sheet, column, row, choice["rows"], choice["mode"], overwrite_ok=True,
                                     undo_title=host.s["undo"]["csv"])
    if result["blockers"]:
        return host.refuse(result["blockers"])
    host.say(host.s["csv"]["imported"] % (result["cells"], result["range"]))


COMMANDS = {
    "Nd30Wizard": nd30_wizard,
    "ConvertEncoding": convert_encoding,
    "FormatDate": lambda h: apply_format(h, "date"),
    "FormatVnd": lambda h: apply_format(h, "vnd"),
    "FormatPercent": lambda h: apply_format(h, "percent"),
    "ImportCsv": import_csv,
}
