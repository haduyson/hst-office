# SPDX-License-Identifier: AGPL-3.0-only
"""Command org.hst.office.vi:NumberToWords. Sheets: dialog "Đọc số thành chữ" writes the words (plain text, which
Excel keeps) or a DOCSO/DOCTIEN formula into the target cell. Writer: the selected number is replaced by its words."""
import re

from . import number_words
from . import utilities_texts as T
from .number_words_choice import error_text, formula, words
from .number_words_dialog import NumberWordsDialog
from .undo import undo_step

TEXT_RESULT = 2  # com.sun.star.sheet.FormulaResult.STRING (FormulaResultType2)
_ADDRESS = re.compile(r"^(?:\$?'?([^.']+)'?\.)?(\$?[A-Za-z]{1,3}\$?[0-9]{1,7})$")


def _address(cell):
    a = cell.getCellAddress()
    column = cell.getSpreadsheet().getColumns().getByIndex(a.Column).getName()
    return "%s%d" % (column, a.Row + 1)


def find_cell(doc, sheet, address):
    """The single cell at `address` ("B2", "$B$2", "Sheet2.B2"); ValueError with the user message otherwise."""
    match = _ADDRESS.match((address or "").strip())
    if not match:
        raise ValueError(T.MESSAGES["bad-cell"] % address)
    try:
        if match.group(1):
            sheet = doc.getSheets().getByName(match.group(1))
        return sheet.getCellRangeByName(match.group(2).replace("$", ""))
    except Exception:  # noqa: BLE001 - unknown sheet or address outside the sheet
        raise ValueError(T.MESSAGES["bad-cell"] % address) from None


def cell_value(cell):
    """None (empty), the text of a text cell or text result, else the number."""
    kind = cell.getType().value  # com.sun.star.table.CellContentType
    if kind == "EMPTY":
        return None
    if kind == "TEXT" or (kind == "FORMULA" and cell.getPropertyValue("FormulaResultType2") == TEXT_RESULT):
        return cell.getString()
    return cell.getValue()


def run(host):
    if host.is_calc():
        return _calc(host)
    if host.is_writer():
        return _writer(host)


def _calc(host):
    selection = host.controller.getSelection()
    sheet = host.controller.getActiveSheet()
    if selection is None or not hasattr(selection, "getRangeAddress"):
        return host.say(T.MESSAGES["no-cells"], error=True)
    if sheet.isProtected():
        return host.say(T.MESSAGES["protected"], error=True)
    a = selection.getRangeAddress()
    source = sheet.getCellByPosition(a.StartColumn, a.StartRow)
    right = sheet.getCellByPosition(min(a.StartColumn + 1, sheet.getColumns().getCount() - 1), a.StartRow)
    dialog = NumberWordsDialog(host.ctx, True, _address(source), _address(right))
    dialog.read_cell = lambda address: cell_value(find_cell(host.doc, sheet, address))
    choice = dialog.run(host.peer)
    if choice is None:
        return
    try:
        source_cell = find_cell(host.doc, sheet, choice["source"])
        target = find_cell(host.doc, sheet, choice["target"])
        value = cell_value(source_cell)
        if value is None:
            raise ValueError(T.MESSAGES["empty-cell"] % choice["source"])
        text = words(value, choice)  # also checks the value when a formula is written
    except number_words.NumberWordsError as exc:
        return host.say(error_text(exc), error=True)
    except ValueError as exc:
        return host.say(str(exc), error=True)
    with undo_step(host.doc, T.UNDO["words"]):
        if choice["formula"]:
            target.setFormula(formula(choice, choice["source"].upper()))
        else:
            target.setString(text)


def _writer(host):
    selection = host.controller.getSelection()
    if selection is None or not hasattr(selection, "getCount") or selection.getCount() != 1:
        return host.say(T.MESSAGES["writer-selection"], error=True)
    rng = selection.getByIndex(0)
    selected = rng.getString() if hasattr(rng, "getString") else ""
    if not selected.strip():
        return host.say(T.MESSAGES["writer-selection"], error=True)
    try:
        value = number_words.parse_number_text(selected)
    except number_words.NumberWordsError as exc:
        return host.say(error_text(exc), error=True)
    choice = NumberWordsDialog(host.ctx, False, selected.strip(), sample=value).run(host.peer)
    if choice is None:
        return
    try:
        text = words(value, choice)
    except number_words.NumberWordsError as exc:
        return host.say(error_text(exc), error=True)
    try:
        with undo_step(host.doc, T.UNDO["words"]):
            # keep the spaces around the number, replace only the number itself
            lead = selected[:len(selected) - len(selected.lstrip())]
            trail = selected[len(selected.rstrip()):]
            rng.setString(lead + text + trail)
    except Exception:  # noqa: BLE001 - protected section, read-only document
        host.say(T.MESSAGES["writer-protected"], error=True)
