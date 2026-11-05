# SPDX-License-Identifier: AGPL-3.0-only
"""Insert Table and the Tabs command follow Word. Used by check-dialogs-writer.py."""
from dialogs_writer_border_cases import document_xml
from dialogs_writer_paragraph_font_cases import first_paragraph
from hst_dialog_uitest import click, state, type_value, visible


def check_insert_table(h, c):
    for radio, name, relative in (("hstautowindow", "window", True), ("hstautofixed", "fixed", False)):
        doc = h.new_document()
        dlg = h.open_dialog(".uno:InsertTable", "InsertTableDialog")
        click(dlg, radio)
        click(dlg, "ok")
        h.wait_idle()
        table = doc.getTextTables().getByIndex(0)
        c.equal(f"insert table: {name} width kind", table.HoriOrient == 6, relative)  # 6 = HoriOrientation.FULL
        h.close_document(doc)

    doc = h.new_document()
    dlg = h.open_dialog(".uno:InsertTable", "InsertTableDialog")
    type_value(dlg, "colspin", "4")
    click(dlg, "hstfixedauto")
    type_value(dlg, "hstfixedwidth", "2")
    click(dlg, "hstremember")
    click(dlg, "ok")
    h.wait_idle()
    table = doc.getTextTables().getByIndex(0)
    c.equal("insert table: fixed 2 cm columns", abs(table.Width - 8000) <= 20, True)
    h.close_document(doc)

    doc = h.new_document()
    dlg = h.open_dialog(".uno:InsertTable", "InsertTableDialog")
    c.equal("insert table: dimensions remembered", state(dlg.getChild("colspin")).get("Text"), "4")
    click(dlg, "hstremember")  # leave the next test a clean profile
    click(dlg, "cancel")
    h.close_document(doc)


def check_tabs(h, c):
    doc = h.new_document()
    dlg = h.open_dialog(".uno:ParagraphDialog?Page:string=tabs", "ParagraphPropertiesDialog")
    c.equal("tabs: the command opens the Tabs page", visible(dlg, "LB_TABPOS"), True)
    c.equal("tabs: default tab stop offered", visible(dlg, "hstdefaulttabs"), True)
    type_value(dlg, "hstdefaulttabs", "2")
    click(dlg, "ok")
    h.wait_idle()
    _, settings = document_xml(h, doc, "default-tabs.docx")
    c.equal("tabs: default tab stop in DOCX settings", 'w:defaultTabStop w:val="1134"' in settings, True)
    c.equal("tabs: paragraph untouched", len(first_paragraph(doc).ParaTabStops) <= 1, True)
    h.close_document(doc)
