# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Chọn người nhận ▾: "Nhập danh sách mới" (type a list, save it as .xlsx or .ods, use it) and "Chọn từ
danh bạ" (a data source registered in the office). "Dùng danh sách có sẵn" is mail_merge_commands.recipients."""
import os

from . import mail_merge_addressbook as book
from . import mail_merge_format as fmt
from . import mail_merge_source as source
from .mail_merge_commands import edit_recipients

FILTERS = {".xlsx": "Calc MS Excel 2007 XML", ".ods": "calc8"}


def typed(value):
    """A typed value as the sheet should keep it: numbers and dd/mm/yyyy dates become values, the rest text
    (0901234567 stays text)."""
    kind, parsed = source.csv_cell(value)
    return (kind, parsed) if kind in (fmt.COL_NUMBER, fmt.COL_DATE) else (fmt.COL_TEXT, value.strip())


def save_sheet(ctx, path, headers, rows):
    """Write the list as a spreadsheet (format from the extension); raises on write errors."""
    import uno
    from com.sun.star.beans import PropertyValue
    from com.sun.star.lang import Locale
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (PropertyValue(Name="Hidden", Value=True),))
    try:
        sheet = doc.Sheets.getByIndex(0)
        sheet.Name = "Danh sách"
        cells = [[typed(v) for v in row] for row in rows]
        data = [tuple(headers)] + [tuple("" if v is None else v for _, v in row) for row in cells]
        sheet.getCellRangeByPosition(0, 0, len(headers) - 1, len(data) - 1).setDataArray(tuple(data))
        key = doc.NumberFormats.queryKey("DD/MM/YYYY", Locale("vi", "VN", ""), False)
        key = key if key >= 0 else doc.NumberFormats.addNew("DD/MM/YYYY", Locale("vi", "VN", ""))
        for r, row in enumerate(cells, 1):
            for c, (kind, _) in enumerate(row):
                if kind == fmt.COL_DATE:
                    sheet.getCellByPosition(c, r).NumberFormat = key
        extension = os.path.splitext(path)[1].lower()
        doc.storeToURL(uno.systemPathToFileUrl(path), (PropertyValue(Name="FilterName", Value=FILTERS[extension]),))
    finally:
        doc.close(True)


def _save_path(c):
    """Where to save the new list (.xlsx unless .ods is chosen); None on Cancel."""
    import uno
    picker = c.ctx.ServiceManager.createInstanceWithArgumentsAndContext(
        "com.sun.star.ui.dialogs.FilePicker", (1,), c.ctx)  # TemplateDescription.FILESAVE_SIMPLE
    picker.setTitle(c.t["new.save-title"])
    for label, pattern in ((c.t["new.xlsx"], "*.xlsx"), (c.t["new.ods"], "*.ods")):
        picker.appendFilter(label, pattern)
    picker.setCurrentFilter(c.t["new.xlsx"])
    picker.setDefaultName("danh-sach-nguoi-nhan.xlsx")
    if picker.execute() != 1 or not picker.getSelectedFiles():
        return None
    path = uno.fileUrlToSystemPath(picker.getSelectedFiles()[0])
    if os.path.splitext(path)[1].lower() not in FILTERS:
        path += ".ods" if picker.getCurrentFilter() == c.t["new.ods"] else ".xlsx"
    return path


def new_list(c):
    from .mail_merge_list_editor import ListEditor
    result = ListEditor(c.ctx, c.t).run(c.peer)
    if result is None:
        return
    path = _save_path(c)
    if path is None:
        return
    try:
        save_sheet(c.ctx, path, *result)
        c.session.choose(c.ctx, path)
    except source.SourceError as exc:
        return c.source_error(exc)
    except Exception as exc:  # noqa: BLE001 - folder not writable, disk full
        return c.say(c.t["err.save"] % (getattr(exc, "Message", "") or str(exc)))
    c.session.stage(c.ctx)
    edit_recipients(c)


def address_book(c):
    from .mail_merge_small_dialogs import choose_item
    found = book.entries(c.ctx)
    if not found:
        return c.say(c.t["book.none"])
    index = choose_item(c.ctx, c.t, c.peer, c.t["book.title"], c.t["book.label"], ["%s – %s" % e for e in found])
    if index is None:
        return
    try:
        c.session.choose(c.ctx, book.encode(*found[index]))
    except source.SourceError as exc:
        return c.source_error(exc)
    c.session.stage(c.ctx)
    edit_recipients(c)


COMMANDS = {"NewList": new_list, "AddressBook": address_book}
