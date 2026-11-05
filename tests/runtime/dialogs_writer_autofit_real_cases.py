# SPDX-License-Identifier: AGPL-3.0-only
"""AutoFit to Contents on real documents from sw/qa: an edit is harmless, unmarked tables never move. Used by check-dialogs-writer.py."""
import glob
import os
import re
import zipfile

from dialogs_writer_autofit_cases import marked, type_text
from dialogs_writer_table_cases import put_cursor, save_and_reopen


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
