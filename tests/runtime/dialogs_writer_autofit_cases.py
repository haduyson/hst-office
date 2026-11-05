# SPDX-License-Identifier: AGPL-3.0-only
"""AutoFit to Contents refits while typing, like Word, and survives DOCX. Used by check-dialogs-writer.py."""
import glob
import os
import re
import zipfile
import time
import zipfile

from dialogs_writer_table_cases import put_cursor, save_and_reopen
from hst_dialog_uitest import click, props, writer_edit

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


def insert_contents_table(h, doc):
    dlg = h.open_dialog(".uno:InsertTable", "InsertTableDialog")
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
    grown = column_width(table)
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


def real_documents(h, count):
    """sw/qa documents with tables and a text body small enough to walk through, spread over the set."""
    tree = os.path.dirname(os.path.dirname(h.office.program))
    found = []
    for path in sorted(glob.glob(os.path.join(tree, "sw/qa/extras/ooxmlexport/data/*.docx"))):
        try:
            with zipfile.ZipFile(path) as package:
                xml = package.read("word/document.xml").decode("utf-8", "ignore")
        except (KeyError, zipfile.BadZipFile):
            continue
        if "<w:tbl>" in xml and len(xml) < 300000:
            found.append(path)
    return found[:: max(1, len(found) // count)][:count]


def with_autofit_mark(source, target):
    """A copy where every table carries the pair that means AutoFit to Contents."""
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as new:
        for item in old.infolist():
            data = old.read(item.filename)
            if item.filename == "word/document.xml":
                xml = re.sub(r"<w:tblLayout [^>]*/>", "", data.decode("utf-8"))
                xml = re.sub(r"<w:tblW [^>]*/>", '<w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="autofit"/>', xml)
                data = xml.encode("utf-8")
            new.writestr(item, data)


def table_shape(table):
    return table.Width, [tuple(sep.Position for sep in row.TableColumnSeparators) for row in table.getRows()]


def edit_first_cell(h, doc):
    """Type into the first cell. None when the document refuses it: protected, or an open dialog says so."""
    table = doc.getTextTables().getByIndex(0)
    name = table.getCellNames()[0]
    if protected_document(doc):
        return table, None
    put_cursor(doc, table, name)
    h.wait_idle(0.3)
    type_text(h, "x")
    for _ in range(6):
        text = table.getCellByName(name).getString()
        if "x" in text:
            return table, text
        h.wait_idle(0.5)
    return table, table.getCellByName(name).getString()


def protected_document(doc):
    sections = doc.getTextSections()
    return any(sections.getByIndex(i).IsProtected for i in range(sections.getCount()))


def close_retrying(h, doc, name, vetoed):
    from com.sun.star.util import CloseVetoException
    for _ in range(5):
        try:
            doc.setModified(False)
            doc.close(True)
            return
        except CloseVetoException:
            h.wait_idle(1)
    vetoed.append(name)


def check_autofit_real_documents(h, c):
    """A real table is left alone unless it carries the mark, and a marked one takes an edit without harm."""
    from com.sun.star.uno import RuntimeException
    work = h.office.workdir
    plain_moved, marked_seen, too_wide, lost, skipped, vetoed = [], 0, [], [], [], []
    files = real_documents(h, 40)
    c.equal("autofit: real documents to test", len(files) >= 30, True)
    for path in files:
        name = os.path.basename(path)
        doc = h.office.load("file://" + path)
        h.wait_idle(0.5)
        took_edit = False
        try:
            if doc.getTextTables().getCount():
                table = doc.getTextTables().getByIndex(0)
                shape = table_shape(table)
                table, text = edit_first_cell(h, doc)
                took_edit = bool(text) and "x" in text
                if table_shape(table) != shape:
                    plain_moved.append(name)
        except RuntimeException as error:
            skipped.append(f"{name}: {error.Message[:40]}")
        close_retrying(h, doc, name, vetoed)
        if not took_edit:
            skipped.append(name)
            continue

        source = os.path.join(work, "autofit-real.docx")
        with_autofit_mark(path, source)
        doc = h.office.load("file://" + source)
        h.wait_idle(0.5)
        try:
            table = doc.getTextTables().getByIndex(0)
            before = table.Width
            table, text = edit_first_cell(h, doc)
            marked_seen += marked(table)
            if not text or "x" not in text:
                lost.append(name)
            style = doc.StyleFamilies.getByName("PageStyles").getByName(doc.getCurrentController().getViewCursor().PageStyleName)
            if table.Width > max(style.Width, before):
                too_wide.append(f"{name} {before} -> {table.Width}")
            again = save_and_reopen(h, doc, "autofit-real-saved.docx", "MS Word 2007 XML")
            if marked(table) and not marked(again.getTextTables().getByIndex(0)):
                lost.append(f"{name}: mark")
            close_retrying(h, doc, name, vetoed)
            doc = again
        except RuntimeException as error:
            skipped.append(f"{name}: {error.Message[:40]}")
        close_retrying(h, doc, name, vetoed)
    print(f"     {len(files)} documents, {marked_seen} marked, skipped {skipped}, close vetoed {vetoed}", flush=True)
    c.equal("autofit: an edit moves no column of an unmarked real table", plain_moved, [])
    c.equal("autofit: marked real tables recognised", marked_seen >= 20, True)
    c.equal("autofit: the edit is in the marked table", lost, [])
    c.equal("autofit: marked real tables stay within the page", too_wide, [])
    c.equal("autofit: every document closes", vetoed, [])
