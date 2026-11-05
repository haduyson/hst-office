# SPDX-License-Identifier: AGPL-3.0-only
"""Insert Table follows Word: AutoFit behaviour and Remember dimensions. Used by check-dialogs-writer.py."""
from hst_dialog_uitest import click, state, type_value


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
