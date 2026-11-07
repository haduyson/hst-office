# SPDX-License-Identifier: AGPL-3.0-only
"""AutoFit to Contents refits while typing, like Word, and survives DOCX. Used by check-dialogs-writer.py."""
import os
import time
import zipfile

from dialogs_writer_table_cases import put_cursor, save_and_reopen
from hst_dialog_uitest import click, props, type_value, writer_edit

MAX_REFIT_SECONDS = 1.0  # a large table may lag behind typing by this much at most


def marked(table):
    return any(p.Name == "tblLayoutAutofit" for p in table.TableInteropGrabBag)


def type_text(h, text):
    writer_edit(h.ui).executeAction("TYPE", props(TEXT=text))
    h.wait_idle(0.6)


def column_width(table, row=0):
    """Width of the first column in 1/100 mm."""
    separators = table.getRows().getByIndex(row).TableColumnSeparators
    return separators[0].Position * table.Width / table.TableColumnRelativeSum


def refitted_width(table, before, seconds=5.0):
    """Width of the first column once the refit after typing landed: UITest delivers the keys asynchronously, so a
    busy office refits later than a fixed pause (the 1000 x 6 check times the refit itself)."""
    deadline = time.monotonic() + seconds
    width = column_width(table)
    while width == before and time.monotonic() < deadline:
        time.sleep(0.1)
        width = column_width(table)
    return width


def insert_contents_table(h, doc, columns=None):
    dlg = h.open_dialog(".uno:InsertTable", "InsertTableDialog")
    if columns:
        type_value(dlg, "colspin", str(columns))
    click(dlg, "hstautocontents")
    click(dlg, "ok")
    h.wait_idle()
    return doc.getTextTables().getByIndex(0)


def check_autofit_typing(h, c):
    doc = h.new_document()
    table = insert_contents_table(h, doc)
    c.equal("autofit: table is marked", marked(table), True)
    put_cursor(doc, table, "A1")
    before = column_width(table)
    type_text(h, "Một nội dung khá dài để cột phải rộng ra")
    grown = refitted_width(table, before)
    c.equal("autofit: the column grows while typing", grown > before, True)
    c.equal("autofit: the other column stays narrower", table.getRows().getByIndex(0).TableColumnSeparators[0].Position > 0, True)
    c.equal("autofit: typed text is all there", table.getCellByName("A1").getString().startswith("Một nội dung"), True)

    page_width = doc.StyleFamilies.getByName("PageStyles").getByName("Standard").Width
    type_text(h, " rồi thêm nữa " * 30)
    c.equal("autofit: never wider than the page", table.Width <= page_width, True)

    undo = doc.getUndoManager()
    c.equal("autofit: the refit adds no undo step of its own", "Bảng" not in (undo.getCurrentUndoActionTitle() or ""), True)
    # Writer's undo goes word by word; refits must neither add steps nor break that up.
    text = table.getCellByName("A1").getString()
    undo.undo()
    h.wait_idle(0.3)
    c.equal("autofit: one undo takes back the last word only", 0 < len(text) - len(table.getCellByName("A1").getString()) < 12, True)
    undo.redo()
    h.wait_idle(0.3)
    c.equal("autofit: redo restores it", table.getCellByName("A1").getString(), text)

    again = save_and_reopen(h, doc, "autofit.docx", "MS Word 2007 XML")
    copy = again.getTextTables().getByIndex(0)
    c.equal("autofit: survives DOCX", marked(copy), True)
    second = save_and_reopen(h, again, "autofit2.docx", "MS Word 2007 XML")
    c.equal("autofit: survives a second save in HST", marked(second.getTextTables().getByIndex(0)), True)
    with zipfile.ZipFile(os.path.join(h.office.workdir, "autofit2.docx")) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    c.equal("autofit: DOCX has w:tblLayout autofit", 'w:tblLayout w:type="autofit"' in xml, True)
    h.close_document(second)
    h.close_document(again)
    h.close_document(doc)
    check_autofit_columns(h, c)


def check_autofit_columns(h, c):
    """Tables of three and four columns refit too: the refit covers the whole table, whichever cells it holds."""
    for columns in (3, 4):
        doc = h.new_document()
        table = insert_contents_table(h, doc, columns)
        c.equal(f"autofit {columns} columns: table inserted", table.getColumns().getCount(), columns)
        put_cursor(doc, table, "A1")
        before = column_width(table)
        type_text(h, "Một nội dung khá dài để cột phải rộng ra")
        c.equal(f"autofit {columns} columns: the column grows while typing", refitted_width(table, before) > before, True)
        h.close_document(doc)


def check_autofit_large_table(h, c):
    """Performance: one refit of a large table, typed into its first cell."""
    doc = h.new_document()
    table = insert_contents_table(h, doc)
    table.getRows().insertByIndex(1, 998)
    table.getColumns().insertByIndex(1, 4)
    h.wait_idle(2)
    put_cursor(doc, table, "A1")
    before = column_width(table)
    start = time.monotonic()
    writer_edit(h.ui).executeAction("TYPE", props(TEXT="Nội dung cho bảng lớn"))
    while time.monotonic() - start < 30 and column_width(table) == before:
        time.sleep(0.05)
    elapsed = time.monotonic() - start
    print(f"     refit of 1000 x 6: {elapsed:.2f} s", flush=True)
    c.equal("autofit: 1000 x 6 refits in time", elapsed <= MAX_REFIT_SECONDS + 0.15, True)
    h.close_document(doc)
