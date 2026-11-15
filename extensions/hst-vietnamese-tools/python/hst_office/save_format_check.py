# SPDX-License-Identifier: AGPL-3.0-only
"""Before a Sheets document is written as .xlsx/.xls: warn when cells use DOCSO, DOCTIEN, BODAU, TACHHO or TACHTEN,
which other spreadsheet programs do not know (#NAME?).

Called by the core save code (hst-save-format-check.patch) as the service org.hst.office.vi.SaveFormatCheck, an XJob:
execute((Model, FilterName)) answers as save_format_rules.answer describes. Choices (save_format_dialog.py):
  - "Chuyển thành giá trị khi lưu": the saved file holds the current results of those cells. The core writes them in
    the export itself (hst-save-hst-functions-as-values.patch); the open document is not touched at all: no
    temporary conversion, no undo step, no modified flag, and no copy of the document (no extra memory);
  - "Vẫn lưu": the file keeps the formulas; - "Hủy" (or closing the dialog): nothing is saved.
With "Không hỏi lại" ticked, "Chuyển thành giá trị khi lưu" or "Vẫn lưu" is remembered per user
(save_format_prefs.py) and used without asking; Tùy chọn ▸ HST Office ▸ Đọc số và tiền turns the question back on.
"""

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .vietnamese_calc_logic import FUNCTION_NAMES, functions_used
from .save_format_rules import ASK, answer, file_extension, to_remember
from .vba_template import is_excel_filter
from . import diag_log

SERVICE_NAME = "org.hst.office.vi.SaveFormatCheck"
FORMULA = 16  # com.sun.star.sheet.CellFlags.FORMULA


def find_functions(doc):
    """(HST function names used, in FUNCTION_NAMES order; number of formula cells that call one of them)."""
    count, names = 0, set()
    sheets = doc.getSheets()
    for index in range(sheets.getCount()):
        blocks = sheets.getByIndex(index).queryContentCells(FORMULA)
        for b in range(blocks.getCount()):
            for row in blocks.getByIndex(b).getFormulaArray():
                for text in row:
                    used = functions_used([text])
                    if used:
                        names.update(used)
                        count += 1
    return sorted(names, key=FUNCTION_NAMES.index), count


def _ask(ctx, doc, names, count, extension):
    from .save_format_dialog import ask
    return ask(ctx, doc, names, count, extension)


def check(ctx, doc, filter_name, ask=_ask, prefs=None):
    """The answer for the core save code (True: save unchanged). Does nothing for other documents and formats."""
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument") or not is_excel_filter(filter_name):
        return True
    names, count = find_functions(doc)
    if not count:
        return True
    if prefs is None:
        from . import save_format_prefs as prefs
    choice = prefs.load(ctx)
    if choice == ASK:
        choice, dont_ask = ask(ctx, doc, names, count, file_extension(filter_name))
        remember = to_remember(choice, dont_ask)
        if remember:
            prefs.save(ctx, remember)
    return answer(choice)


def to_uno(result):
    """The answer as the core reads it: a boolean, or com.sun.star.beans.NamedValue structs (a tuple reaches the core
    as a sequence of any, which it reads as well as a typed sequence)."""
    if isinstance(result, bool):
        return result
    import uno
    values = []
    for name, value in result:
        named = uno.createUnoStruct("com.sun.star.beans.NamedValue")
        named.Name, named.Value = name, value
        values.append(named)
    return tuple(values)


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
            return to_uno(check(self.ctx, _argument(arguments, "Model"), _argument(arguments, "FilterName", "")))
        except Exception:  # noqa: BLE001 - a broken check must never block saving
            diag_log.exception("save_format_check")
            return True
