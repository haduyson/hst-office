# SPDX-License-Identifier: AGPL-3.0-only
"""What the Trợ lý AI reads from and writes to the document. Reading happens only to prefill the dialog (the user
sees and can edit the text before anything is sent); writing happens only when the user presses an insert button,
inside one undo step named "Trợ lý AI"."""
from . import diag_log
from .ai_texts import TEXT


def kind(model):
    if model is None:
        return None
    for service, name in (("com.sun.star.sheet.SpreadsheetDocument", "calc"), ("com.sun.star.text.TextDocument", "writer"),
                          ("com.sun.star.presentation.PresentationDocument", "impress"),
                          ("com.sun.star.drawing.DrawingDocument", "draw")):
        if model.supportsService(service):
            return name
    return None


def active_cell(controller):
    """The cell with the cursor in Sheets (the top-left cell of a selected range), or None."""
    selection = controller.getSelection()
    if selection is None or not hasattr(selection, "getCellAddress") and not hasattr(selection, "getRangeAddress"):
        return None
    if hasattr(selection, "getCellAddress"):
        return selection
    address = selection.getRangeAddress()
    return controller.getActiveSheet().getCellByPosition(address.StartColumn, address.StartRow)


def cell_name(cell):
    return cell.AbsoluteName.split(".")[-1].replace("$", "") if cell is not None else ""


MAX_COLUMNS = 40


def _address(sheet, start_col, start_row, end_col, end_row):
    return cell_name(sheet.getCellRangeByPosition(start_col, start_row, end_col, end_row))


def data_region(controller, cell):
    """(address, [(column letter, name)]) of the data a new formula in `cell` is about: the cell's current region,
    or the sheet's used area when the cell stands alone. Only text cells of the region's first row (the column
    names) are read; no data value ever leaves the sheet. None without a header row or outside Sheets."""
    try:
        sheet = controller.getActiveSheet()
        cursor = sheet.createCursorByRange(cell)
        cursor.collapseToCurrentRegion()
        area = cursor.getRangeAddress()
        if area.StartColumn == area.EndColumn and area.StartRow == area.EndRow:
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            area = cursor.getRangeAddress()
        if area.EndRow <= area.StartRow:
            return None
        headers = []
        for col in range(area.StartColumn, min(area.EndColumn, area.StartColumn + MAX_COLUMNS - 1) + 1):
            header = sheet.getCellByPosition(col, area.StartRow)
            if header.getType().value == "TEXT" and header.getString().strip():
                headers.append((cell_name(header).rstrip("0123456789"), header.getString().strip()[:60]))
        if not headers:
            return None
        return _address(sheet, area.StartColumn, area.StartRow, area.EndColumn, area.EndRow), headers
    except Exception:  # noqa: BLE001 - no context: the description alone is sent
        diag_log.exception("ai_document")
        return None


def _text_target(controller):
    """(read, write) of the selected text: a Writer text range, the text of one selected shape, or a Sheets cell."""
    selection = controller.getSelection()
    if selection is None:
        return None
    if selection.supportsService("com.sun.star.text.TextRanges") and selection.getCount() >= 1:
        rng = selection.getByIndex(0)
        if rng.getString():
            return rng.getString, rng.setString, rng
    if hasattr(selection, "getCellAddress"):
        return selection.getString, selection.setString, selection
    if selection.supportsService("com.sun.star.drawing.ShapeCollection") and selection.getCount() == 1:
        shape = selection.getByIndex(0)
        if hasattr(shape, "getString"):
            return shape.getString, shape.setString, shape
    if hasattr(selection, "getString") and hasattr(selection, "setString"):
        return selection.getString, selection.setString, selection
    return None


def selected_text(controller):
    target = _text_target(controller)
    try:
        return target[0]() if target else ""
    except Exception:  # noqa: BLE001 - selection that has no text
        return ""


def _undo(model, action):
    manager = model.getUndoManager()
    manager.enterUndoContext(TEXT["undo"])
    try:
        action()
    finally:
        manager.leaveUndoContext()


def replace_selection(model, controller, text):
    target = _text_target(controller)
    if target is None:
        return False
    _undo(model, lambda: target[1](text))
    return True


def insert_after_selection(model, controller, text):
    """Writer: a new paragraph after the selection; elsewhere the text is appended after a line break."""
    target = _text_target(controller)
    if target is None:
        return False
    obj = target[2]
    if hasattr(obj, "getText") and hasattr(obj, "getEnd") and kind(model) == "writer":
        def run():
            from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
            body = obj.getText()
            cursor = body.createTextCursorByRange(obj.getEnd())
            body.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            body.insertString(cursor, text, False)
        _undo(model, run)
        return True
    current = target[0]()
    _undo(model, lambda: target[1](current + "\n" + text))
    return True


def excel_to_api(formula):
    """Excel separators to the Calc API grammar of XCell.setFormula: ',' -> ';' between arguments; in an inline
    array {…} ',' -> ';' (columns) and ';' -> '|' (rows); nothing changes inside "string" literals."""
    out, quoted, depth = [], False, 0
    for char in formula:
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
            elif char == ";" and depth:
                char = "|"
            elif char == ",":
                char = ";"
        out.append(char)
    return "".join(out)


def _parse_excel(model, cell, formula):
    """Formula tokens of `formula` in Excel English A1 syntax, through the document's own formula parser."""
    import uno
    from com.sun.star.sheet import FormulaMapGroup
    from com.sun.star.sheet.FormulaLanguage import XL_ENGLISH
    parser = model.createInstance("com.sun.star.sheet.FormulaParser")
    mapper = model.createInstance("com.sun.star.sheet.FormulaOpCodeMapper")
    parser.CompileEnglish = True  # before OpCodeMap (FormulaParser.idl)
    parser.FormulaConvention = uno.getConstantByName("com.sun.star.sheet.AddressConvention.XL_A1")
    parser.OpCodeMap = mapper.getAvailableMappings(XL_ENGLISH, FormulaMapGroup.ALL_EXCEPT_SPECIAL)
    return parser.parseFormula(formula, cell.getCellAddress())


def insert_formula(model, cell, formula):
    """Write an Excel-syntax formula into `cell` (one undo step). Returns True when the cell holds a formula."""
    def run():
        try:
            cell.setTokens(_parse_excel(model, cell, formula))
        except Exception:  # noqa: BLE001 - parser unavailable: the separators-only conversion
            diag_log.exception("ai_document")
            cell.setFormula(excel_to_api(formula))
    try:
        from com.sun.star.table.CellContentType import FORMULA
        _undo(model, run)
        return cell.getType() == FORMULA
    except Exception:  # noqa: BLE001
        diag_log.exception("ai_document")
        return False
