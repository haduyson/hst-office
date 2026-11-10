# SPDX-License-Identifier: AGPL-3.0-only
"""Before a Sheets document is written as .xlsx/.xls: warn when cells use DOCSO, DOCTIEN, BODAU, TACHHO or TACHTEN,
which Microsoft Excel does not know (#NAME?).

Called by the core save code (hst-save-format-check.patch) as the service org.hst.office.vi.SaveFormatCheck, an XJob:
execute((Model, FilterName, Export)) returns False to cancel the save. Choices:
  - "Đổi thành chữ rồi lưu": the cells hold their results as plain values in the saved file; the open document gets
    its formulas back right after the save (or keeps the values, as one undo step, when the box is ticked);
  - "Vẫn lưu": unchanged; - "Hủy" (or closing the dialog): nothing is saved.
"""

import unohelper
from com.sun.star.document import XDocumentEventListener
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import utilities_texts as T
from .vietnamese_calc_logic import FUNCTION_NAMES, functions_used
from .undo import undo_locked, undo_step
from .vba_template import is_excel_filter
from . import diag_log

SERVICE_NAME = "org.hst.office.vi.SaveFormatCheck"
FORMULA = 16  # com.sun.star.sheet.CellFlags.FORMULA
CONVERT, KEEP, CANCEL = "convert", "keep", "cancel"
DONE_EVENTS = ("OnSaveDone", "OnSaveAsDone")
END_EVENTS = DONE_EVENTS + ("OnSaveToDone", "OnSaveFailed", "OnSaveAsFailed", "OnSaveToFailed")


def find_cells(doc):
    """[(cell, formula)] of every formula cell that calls an HST function, and the function names used."""
    cells, names = [], set()
    sheets = doc.getSheets()
    for index in range(sheets.getCount()):
        sheet = sheets.getByIndex(index)
        blocks = sheet.queryContentCells(FORMULA)
        for b in range(blocks.getCount()):
            block = blocks.getByIndex(b)
            a = block.getRangeAddress()
            for r, row in enumerate(block.getFormulaArray()):
                for c, text in enumerate(row):
                    used = functions_used([text])
                    if used:
                        names.update(used)
                        cells.append((sheet.getCellByPosition(a.StartColumn + c, a.StartRow + r), text))
    return cells, sorted(names, key=FUNCTION_NAMES.index)


def to_values(cells):
    """Each cell keeps its current result as a constant (text or number). A cell whose result is an error (more than
    15 digits) keeps its formula: Excel shows an error for it either way."""
    for cell, _ in cells:
        result = cell.getPropertyValue("FormulaResultType2")  # com.sun.star.sheet.FormulaResult: 2 STRING, 4 ERROR
        if result == 2:
            cell.setString(cell.getString())
        elif result != 4:
            cell.setValue(cell.getValue())


class _Restore(unohelper.Base, XDocumentEventListener):
    """Puts the formulas back once the save has ended (done or failed), without an undo entry."""

    def __init__(self, doc, cells, modified):
        self.doc, self.cells, self.modified = doc, cells, modified

    def documentEventOccured(self, event):
        if event.EventName not in END_EVENTS:
            return
        self.doc.removeDocumentEventListener(self)
        try:
            with undo_locked(self.doc):
                for cell, formula in self.cells:
                    cell.setFormula(formula)
            self.doc.setModified(False if event.EventName in DONE_EVENTS else self.modified)
        except Exception:  # noqa: BLE001 - never raise into the save
            diag_log.exception("save_format_check")

    def disposing(self, event):
        pass


def ask(ctx, doc, names, count):
    """(choice, also in the open document) from the warning dialog."""
    from .dialogs import Dialog
    dialog = Dialog(ctx, T.SAVE_TITLE, 300, 118)
    dialog.label("text", T.SAVE_TEXT % (", ".join(names), count), 8, 8, 284, 66, wrap=True)
    dialog.check("inDocument", T.SAVE_IN_DOCUMENT, 8, 76, 284, state=False)
    x = 300 - 8 - (110 + 60 + 50 + 8)
    # left to right is also the Tab order after the check box; Enter is "Đổi thành chữ rồi lưu", Esc is "Hủy"
    for result, label, width in zip((CONVERT, KEEP, CANCEL), T.SAVE_BUTTONS, (110, 60, 50)):
        dialog.button(result, label, x, 96, width, default=result == CONVERT,
                      callback=lambda result=result: chosen.append((result, dialog.get("inDocument"))) or dialog.end(1))
        x += width + 4
    chosen = []
    controller = doc.getCurrentController()
    peer = controller.getFrame().getContainerWindow() if controller else None
    dialog.execute(peer)
    return chosen[-1] if chosen else (CANCEL, False)  # the dialog is disposed: its state was read on the click


def check(ctx, doc, filter_name, ask=ask):
    """True to go on saving. Does nothing for other documents and formats."""
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument") or not is_excel_filter(filter_name):
        return True
    cells, names = find_cells(doc)
    if not cells:
        return True
    choice, in_document = ask(ctx, doc, names, len(cells))
    if choice == CANCEL:
        return False
    if choice == CONVERT:
        if in_document:
            with undo_step(doc, T.UNDO["toText"]):
                to_values(cells)
        else:
            modified = doc.isModified()
            with undo_locked(doc):
                to_values(cells)
            doc.addDocumentEventListener(_Restore(doc, cells, modified))
    return True


def _argument(arguments, name, default=None):
    return next((a.Value for a in arguments or () if a.Name == name), default)


class SaveFormatCheck(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return SERVICE_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (SERVICE_NAME,)

    def execute(self, arguments):
        try:
            return check(self.ctx, _argument(arguments, "Model"), _argument(arguments, "FilterName", ""))
        except Exception:  # noqa: BLE001 - a broken check must never block saving
            diag_log.exception("save_format_check")
            return True
