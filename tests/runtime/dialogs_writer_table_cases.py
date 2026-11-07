# SPDX-License-Identifier: AGPL-3.0-only
"""Table Properties follows Word: Table, Row, Column, Cell, Alt Text. Used by check-dialogs-writer.py."""
import os
import threading
import time

from hst_dialog_uitest import click, has_child, props, select_entry, select_tab, tab_titles, type_value, visible, writer_edit

TOP, CENTER, BOTTOM = 0, 2, 3  # com.sun.star.text.VertOrientation: NONE counts as the top of a cell


def new_table(doc, rows=3, cols=3):
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(rows, cols)
    doc.getText().insertTextContent(doc.getText().getEnd(), table, False)
    return table


def put_cursor(doc, table, cell):
    doc.getCurrentController().getViewCursor().gotoRange(table.getCellByName(cell).getStart(), False)


def alt_text(table):
    return {p.Name: p.Value for p in table.TableInteropGrabBag if p.Name in ("tblCaption", "tblDescription")}


def save_and_reopen(h, doc, name, filter_name):
    path = os.path.join(h.office.workdir, name)
    doc.storeToURL("file://" + path, props(FilterName=filter_name))
    return h.office.load("file://" + path)


def check_table_properties(h, c):
    doc = h.new_document()
    table = new_table(doc)
    put_cursor(doc, table, "B2")
    dlg = h.open_dialog(".uno:TableDialog", "TablePropertiesDialog")
    titles = tab_titles(dlg)
    c.equal("table: Word's tabs come first", titles[:5], ["Bảng", "Hàng", "Cột", "Ô", "Văn bản thay thế"])
    c.equal("table: nothing removed, Advanced last", titles[5:], ["Viền", "Tô bóng", "Nâng cao"])

    select_tab(dlg, 1)
    c.equal("table: row height field shown", visible(dlg, "hstrowheight"), True)
    click(dlg, "hstrowheighton")
    type_value(dlg, "hstrowheight", "2")
    select_entry(dlg, "hstrowrule", 1)
    click(dlg, "splitrow")
    click(dlg, "headline")
    select_tab(dlg, 3)
    select_entry(dlg, "vertorient", 2)
    type_value(dlg, "hstcellleft", "0,5")  # the vi_VN decimal comma
    select_tab(dlg, 4)
    type_value(dlg, "hstalttitle", "Doanh thu")
    type_value(dlg, "hstaltdesc", "Doanh thu theo quý")
    click(dlg, "ok")
    h.wait_idle()

    rows = table.getRows()
    c.equal("table: row 2 has exactly 2 cm", (rows.getByIndex(1).Height, rows.getByIndex(1).IsAutoHeight), (2000, False))
    c.equal("table: row 1 keeps its height rule", rows.getByIndex(0).IsAutoHeight, True)
    c.equal("table: row 2 cannot break", rows.getByIndex(1).IsSplitAllowed, False)
    c.equal("table: row 1 can still break", rows.getByIndex(0).IsSplitAllowed, True)
    c.equal("table: header row repeats", (table.RepeatHeadline, table.HeaderRowCount), (True, 1))
    cell = table.getCellByName("B2")
    c.equal("table: cell aligned to the bottom", cell.VertOrient, BOTTOM)
    c.equal("table: other cell not aligned", table.getCellByName("A1").VertOrient, TOP)
    c.equal("table: left margin of the cell", abs(cell.LeftBorderDistance - 500) <= 2, True)
    c.equal("table: margin of the other cell unchanged", abs(table.getCellByName("A1").LeftBorderDistance - 500) > 2, True)
    c.equal("table: alt text stored", alt_text(table), {"tblCaption": "Doanh thu", "tblDescription": "Doanh thu theo quý"})

    dlg = h.open_dialog(".uno:TableDialog", "TablePropertiesDialog")
    select_tab(dlg, 3)
    type_value(dlg, "hstcellwidth", "3")
    click(dlg, "ok")
    h.wait_idle()
    separators = table.getRows().getByIndex(1).TableColumnSeparators
    cell_width = (separators[1].Position - separators[0].Position) * table.Width / table.TableColumnRelativeSum
    print(f"     cell B2 width {cell_width:.0f}", flush=True)
    c.equal("table: cell width applied", abs(cell_width - 3000) < 60, True)

    for name, filter_name in (("table-alt.docx", "MS Word 2007 XML"), ("table-alt.odt", "writer8")):
        again = save_and_reopen(h, doc, name, filter_name)
        copy = again.getTextTables().getByIndex(0)
        c.equal(f"table: {name} keeps the alt text", alt_text(copy), {"tblCaption": "Doanh thu", "tblDescription": "Doanh thu theo quý"})
        row = copy.getRows().getByIndex(1)
        c.equal(f"table: {name} keeps the row height", (abs(row.Height - 2000) <= 20, row.IsAutoHeight, row.IsSplitAllowed), (True, False, False))
        c.equal(f"table: {name} keeps the cell", copy.getCellByName("B2").VertOrient, BOTTOM)
        c.equal(f"table: {name} keeps the header row", copy.HeaderRowCount, 1)
        c.equal(f"table: {name} keeps the left margin", abs(copy.getCellByName("B2").LeftBorderDistance - 500) <= 20, True)
        h.close_document(again)
    h.close_document(doc)


def check_table_row_navigation(h, c):
    """Previous Row and Next Row: edits wait for OK, reach each row, and Cancel leaves the rows alone."""
    doc = h.new_document()
    table = new_table(doc)
    put_cursor(doc, table, "A1")
    dlg = h.open_dialog(".uno:TableDialog", "TablePropertiesDialog")
    select_tab(dlg, 1)
    click(dlg, "hstnextrow")
    click(dlg, "hstrowheighton")
    type_value(dlg, "hstrowheight", "3")
    click(dlg, "cancel")
    h.wait_idle()
    c.equal("row nav: Cancel leaves row 2", table.getRows().getByIndex(1).IsAutoHeight, True)

    dlg = h.open_dialog(".uno:TableDialog", "TablePropertiesDialog")
    select_tab(dlg, 1)
    click(dlg, "hstrowheighton")
    type_value(dlg, "hstrowheight", "1")
    click(dlg, "hstnextrow")
    click(dlg, "hstnextrow")
    click(dlg, "hstrowheighton")
    type_value(dlg, "hstrowheight", "3")
    click(dlg, "hstprevrow")
    click(dlg, "splitrow")
    click(dlg, "ok")
    h.wait_idle()
    rows = table.getRows()
    c.equal("row nav: row 1 height", abs(rows.getByIndex(0).Height - 1000) <= 2, True)
    c.equal("row nav: row 3 height", abs(rows.getByIndex(2).Height - 3000) <= 2, True)
    c.equal("row nav: row 2 keeps its height, cannot break", (rows.getByIndex(1).IsAutoHeight, rows.getByIndex(1).IsSplitAllowed), (True, False))
    h.close_document(doc)


def ok_with_wrap_prompt(h, dlg, button, required=True):
    """OK on Text Wrapping asks before it clears the undo history, when there is history to clear.
    The question runs inside the click, so the click has its own thread."""
    clicker = threading.Thread(target=click, args=(dlg, "ok"), daemon=True)
    clicker.start()
    answer_wrap_prompt(h, button, required)
    clicker.join(30)


def answer_wrap_prompt(h, button, required=True):
    for _ in range(20):
        top = h.ui.getTopFocusWindow()
        if has_child(top, button):
            click(top, button)
            h.wait_idle()
            return
        time.sleep(0.25)
    assert not required, "the undo history prompt did not appear"


def table_tab(h):
    """Table Properties on its Table tab: the dialog reopens on the tab used last (Row, after the row checks),
    and Text Wrapping set on a tab that was never shown is not applied."""
    dlg = h.open_dialog(".uno:TableDialog", "TablePropertiesDialog")
    select_tab(dlg, 0)
    return dlg


def check_table_text_wrapping(h, c):
    """Text Wrapping on the Table tab: Around floats the table, survives DOCX, None brings it back."""
    doc = h.new_document()
    table = new_table(doc)
    put_cursor(doc, table, "A1")
    writer_edit(h.ui).executeAction("TYPE", props(TEXT="Có lịch sử hoàn tác"))
    h.wait_idle()
    dlg = table_tab(h)
    click(dlg, "hsttablewraparound")
    ok_with_wrap_prompt(h, dlg, "no")
    c.equal("wrap: answering No leaves the table in the text", doc.getTextFrames().getCount(), 0)
    undo_title = doc.getUndoManager().getCurrentUndoActionTitle()
    dlg = table_tab(h)
    click(dlg, "hsttablewraparound")
    ok_with_wrap_prompt(h, dlg, "yes")
    h.wait_idle(2)
    c.equal("wrap: there was history to warn about", bool(undo_title), True)
    c.equal("wrap: Around makes one frame", doc.getTextFrames().getCount(), 1)
    frame = doc.getTextFrames().getByIndex(0)
    c.equal("wrap: the frame can split and wraps text", (frame.IsSplitAllowed, frame.TextWrap.value), (True, "PARALLEL"))
    c.equal("wrap: the table is still there", doc.getTextTables().getCount(), 1)

    again = save_and_reopen(h, doc, "table-wrap.docx", "MS Word 2007 XML")
    c.equal("wrap: DOCX keeps it floating", again.getTextFrames().getCount(), 1)
    h.close_document(again)

    put_cursor(doc, doc.getTextTables().getByIndex(0), "A1")
    dlg = table_tab(h)
    click(dlg, "hsttablewrapnone")
    ok_with_wrap_prompt(h, dlg, "yes", required=False)
    h.wait_idle(2)
    c.equal("wrap: None removes the frame", doc.getTextFrames().getCount(), 0)
    c.equal("wrap: None keeps the table", doc.getTextTables().getCount(), 1)
    h.close_document(doc)
