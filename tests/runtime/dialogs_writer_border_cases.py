# SPDX-License-Identifier: AGPL-3.0-only
"""Borders and Shading, Insert Table and Tabs follow Word. Used by check-dialogs-writer.py."""
import os
import zipfile

from dialogs_writer_paragraph_font_cases import first_paragraph
from dialogs_writer_table_cases import save_and_reopen
from hst_dialog_uitest import click, select_entry, select_tab, tab_titles, type_value, visible


def document_xml(h, doc, name):
    path = os.path.join(h.office.workdir, name)
    again = save_and_reopen(h, doc, name, "MS Word 2007 XML")
    h.close_document(again)
    with zipfile.ZipFile(path) as package:
        return package.read("word/document.xml").decode("utf-8"), package.read("word/settings.xml").decode("utf-8")


def check_borders(h, c):
    doc = h.new_document()
    doc.getText().setString("Một đoạn văn để thử viền")
    dlg = h.open_dialog(".uno:BorderDialog", "HstBordersDialog")
    c.equal("borders: Word's three tabs", tab_titles(dlg), ["Viền", "Viền trang", "Tô bóng"])
    c.equal("borders: no selection, no Apply to Text", visible(dlg, "hstapplyto"), False)
    click(dlg, "cancel")
    h.wait_idle()
    dlg = h.open_dialog(".uno:BackgroundDialog", "HstBordersDialog")
    click(dlg, "cancel")
    h.wait_idle()

    cursor = doc.getCurrentController().getViewCursor()
    cursor.gotoStart(False)
    cursor.goRight(3, True)
    dlg = h.open_dialog(".uno:BorderDialog", "HstBordersDialog")
    c.equal("borders: selected text offers Apply to", visible(dlg, "hstapplyto"), True)
    # Selected text starts on Apply to: Text. The second preset draws a box.
    select_tab(dlg, 0)  # the dialog opens on the tab used last
    dlg.getChild("presets").getChild("1").executeAction("SELECT", ())
    click(dlg, "ok")
    h.wait_idle()
    portion = first_paragraph(doc).createEnumeration().nextElement()
    c.equal("borders: Apply to Text borders the characters", portion.CharTopBorder.LineWidth > 0, True)
    c.equal("borders: the paragraph is left alone", first_paragraph(doc).TopBorder.LineWidth, 0)
    xml, _ = document_xml(h, doc, "text-border.docx")
    c.equal("borders: DOCX has w:bdr on the run", "<w:bdr " in xml, True)

    cursor.gotoEnd(False)
    dlg = h.open_dialog(".uno:BorderDialog", "HstBordersDialog")
    select_tab(dlg, 0)  # the dialog opens on the tab used last
    dlg.getChild("presets").getChild("1").executeAction("SELECT", ())
    click(dlg, "ok")
    h.wait_idle()
    c.equal("borders: no selection borders the paragraph", first_paragraph(doc).TopBorder.LineWidth > 0, True)
    xml, _ = document_xml(h, doc, "para-border.docx")
    c.equal("borders: DOCX has w:pBdr", "<w:pBdr>" in xml, True)
    h.close_document(doc)


def page_style(doc):
    return doc.StyleFamilies.getByName("PageStyles").getByName("Standard")


def check_page_border(h, c):
    from com.sun.star.table import BorderLine2
    for pos, label, display in ((1, "this section", 'w:display="allPages"'),
                                (2, "first page only", 'w:display="firstPage"'),
                                (3, "all except first", 'w:display="notFirstPage"')):
        doc = h.new_document()
        doc.getText().setString("Trang có viền")
        style = page_style(doc)
        line = BorderLine2()
        line.Color, line.LineWidth, line.OuterLineWidth, line.LineStyle = 0, 50, 50, 0
        style.TopBorder, style.BottomBorder, style.LeftBorder, style.RightBorder = line, line, line, line
        h.wait_idle()
        dlg = h.open_dialog(".uno:BorderDialog", "HstBordersDialog")
        select_tab(dlg, 1)
        select_entry(dlg, "hstpageapplyto", pos)
        click(dlg, "ok")
        h.wait_idle()
        xml, _ = document_xml(h, doc, f"page-border-{pos}.docx")
        c.equal(f"page border: {label} in DOCX", display in xml, True)
        again = save_and_reopen(h, doc, f"page-border-{pos}b.docx", "MS Word 2007 XML")
        second, _ = document_xml(h, again, f"page-border-{pos}c.docx")
        c.equal(f"page border: {label} survives reopening", display in second, True)
        h.close_document(again)
        h.close_document(doc)
