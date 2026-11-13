# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic Writer documents with the cursor or selection in each place an HST Writer command can start from (used by
check-nd30-insertion-point.py): text, table cell, selected cells, nested table, picture, shape, frame, header, footer,
footnote, selections, protected section, comment being edited, read-only file."""
import os

import uno
from com.sun.star.awt import Size
from com.sun.star.beans import PropertyValue

BREAK = 0  # PARAGRAPH_BREAK


def _doc(office):
    return office.load("private:factory/swriter")


def _body(doc, text="Đoạn văn bản thường."):
    t = doc.getText()
    t.insertString(t.getEnd(), text, False)
    return t


def _header_table(doc):
    t = doc.getText()
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(2, 2)
    t.insertTextContent(t.getStart(), table, False)
    table.getCellByName("A1").setString("BỘ TÀI CHÍNH")
    table.getCellByName("B1").setString("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM")
    return table


def table_cell(office):
    doc = _doc(office); _body(doc); table = _header_table(doc)
    doc.getCurrentController().getViewCursor().gotoRange(table.getCellByName("B1").getText().getEnd(), False)
    return doc


def table_cell_text_selected(office):
    doc = _doc(office); _body(doc); table = _header_table(doc)
    vc = doc.getCurrentController().getViewCursor()
    vc.gotoRange(table.getCellByName("A1").getText().getStart(), False)
    vc.gotoRange(table.getCellByName("A1").getText().getEnd(), True)
    return doc


def table_cells_selected(office):
    doc = _doc(office); _body(doc); table = _header_table(doc)
    tc = table.createCursorByCellName("A1")
    tc.goRight(1, True)
    doc.getCurrentController().select(tc)
    return doc


def nested_table_cell(office):
    doc = _doc(office); _body(doc); table = _header_table(doc)
    cell = table.getCellByName("A2")
    inner = doc.createInstance("com.sun.star.text.TextTable")
    inner.initialize(1, 1)
    cell.getText().insertTextContent(cell.getText().getStart(), inner, False)
    doc.getCurrentController().getViewCursor().gotoRange(inner.getCellByName("A1").getText().getStart(), False)
    return doc


def table_last_in_document(office):
    doc = _doc(office); t = doc.getText()
    table = doc.createInstance("com.sun.star.text.TextTable"); table.initialize(1, 2)
    t.insertTextContent(t.getEnd(), table, False)
    doc.getCurrentController().getViewCursor().gotoRange(table.getCellByName("A1").getText().getStart(), False)
    return doc


def _graphic(doc):
    g = doc.createInstance("com.sun.star.text.TextGraphicObject")
    g.Graphic = None
    g.setSize(Size(2000, 2000))
    t = doc.getText(); t.insertTextContent(t.getEnd(), g, False)
    return g


def image_selected(office):
    doc = _doc(office); _body(doc)
    doc.getCurrentController().select(_graphic(doc))
    return doc


def shape_selected(office):
    doc = _doc(office); _body(doc)
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    shape.setSize(Size(3000, 1500))
    t = doc.getText(); t.insertTextContent(t.getEnd(), shape, False)
    doc.getCurrentController().select(shape)
    return doc


def _frame(doc):
    f = doc.createInstance("com.sun.star.text.TextFrame")
    f.setSize(Size(5000, 2000))
    t = doc.getText(); t.insertTextContent(t.getEnd(), f, False)
    f.getText().setString("Khung")
    return f


def frame_selected(office):
    doc = _doc(office); _body(doc)
    doc.getCurrentController().select(_frame(doc))
    return doc


def inside_frame(office):
    doc = _doc(office); _body(doc); f = _frame(doc)
    doc.getCurrentController().getViewCursor().gotoRange(f.getText().getEnd(), False)
    return doc


def header(office):
    doc = _doc(office); _body(doc)
    style = doc.StyleFamilies.getByName("PageStyles").getByName("Standard")
    style.HeaderIsOn = True
    style.HeaderText.setString("Đầu trang")
    doc.getCurrentController().getViewCursor().gotoRange(style.HeaderText.getEnd(), False)
    return doc


def footer(office):
    doc = _doc(office); _body(doc)
    style = doc.StyleFamilies.getByName("PageStyles").getByName("Standard")
    style.FooterIsOn = True
    style.FooterText.setString("Chân trang")
    doc.getCurrentController().getViewCursor().gotoRange(style.FooterText.getEnd(), False)
    return doc


def footnote(office):
    doc = _doc(office); t = _body(doc)
    fn = doc.createInstance("com.sun.star.text.Footnote")
    t.insertTextContent(t.getEnd(), fn, False)
    fn.setString("Chú thích")
    doc.getCurrentController().getViewCursor().gotoRange(fn.getEnd(), False)
    return doc


def text_selected(office):
    doc = _doc(office); _body(doc)
    vc = doc.getCurrentController().getViewCursor()
    vc.gotoStart(False); vc.gotoEnd(True)
    return doc


def multi_selection(office):
    doc = _doc(office); _body(doc, "abc thường abc thường")
    desc = doc.createSearchDescriptor(); desc.SearchString = "abc"
    doc.getCurrentController().select(doc.findAll(desc))
    return doc


def protected_section(office):
    doc = _doc(office); t = _body(doc)
    t.insertControlCharacter(t.getEnd(), BREAK, False)
    sec = doc.createInstance("com.sun.star.text.TextSection")
    cur = t.createTextCursorByRange(t.getEnd())
    t.insertTextContent(cur, sec, False)
    sec.getAnchor().setString("Phần được bảo vệ")
    sec.IsProtected = True
    doc.getCurrentController().getViewCursor().gotoRange(sec.getAnchor().getEnd(), False)
    return doc


def plain_body(office):
    doc = _doc(office); _body(doc)
    return doc


def comment_editing(office):
    doc = _doc(office); _body(doc)
    frame = doc.getCurrentController().getFrame()
    office.dispatch(frame, ".uno:InsertAnnotation")
    return doc


def read_only(office):
    doc = _doc(office); _body(doc)
    path = os.path.join(office.workdir, "read-only.odt")
    prop = PropertyValue(); prop.Name, prop.Value = "FilterName", "writer8"
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop,)); doc.close(True)
    prop = PropertyValue(); prop.Name, prop.Value = "ReadOnly", True
    return office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (prop,))


SCENARIOS = [plain_body, table_cell, table_cell_text_selected, table_cells_selected, nested_table_cell,
             table_last_in_document, image_selected, shape_selected, frame_selected, inside_frame, header, footer,
             footnote, text_selected, multi_selection, protected_section, comment_editing, read_only]
