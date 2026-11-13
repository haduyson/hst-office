# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic Writer documents with the cursor or selection in each place an HST Writer command can start from, one
function per place (check-nd30-insertion-point.py); the names say where."""
import os
import time

import uno
from com.sun.star.awt import Size
from com.sun.star.beans import PropertyValue


def _doc(office, text="Đoạn văn bản thường."):
    """A new visible Writer document holding one paragraph of `text`."""
    doc = office.load("private:factory/swriter")
    doc.getText().insertString(doc.getText().getEnd(), text, False)
    return doc


def close(doc, tries=10):
    """Close without saving; Writer vetoes while it answers a clipboard query of the X server, so try again."""
    from com.sun.star.util import CloseVetoException
    doc.setModified(False)
    for _ in range(tries):
        try:
            return doc.close(True)
        except CloseVetoException:
            time.sleep(0.5)
    doc.dispose()


def _header_table(doc):
    t = doc.getText()
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(2, 2)
    t.insertTextContent(t.getStart(), table, False)
    table.getCellByName("A1").setString("BỘ TÀI CHÍNH")
    table.getCellByName("B1").setString("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM")
    return table


def table_cell(office):
    doc = _doc(office); table = _header_table(doc)
    doc.getCurrentController().getViewCursor().gotoRange(table.getCellByName("B1").getText().getEnd(), False)
    return doc


def table_cell_text_selected(office):
    doc = _doc(office); table = _header_table(doc)
    vc = doc.getCurrentController().getViewCursor()
    vc.gotoRange(table.getCellByName("A1").getText().getStart(), False)
    vc.gotoRange(table.getCellByName("A1").getText().getEnd(), True)
    return doc


def table_cells_selected(office):
    doc = _doc(office); table = _header_table(doc)
    tc = table.createCursorByCellName("A1")
    tc.goRight(1, True)
    doc.getCurrentController().select(tc)
    return doc


def nested_table_cell(office):
    doc = _doc(office); table = _header_table(doc)
    cell = table.getCellByName("A2")
    inner = doc.createInstance("com.sun.star.text.TextTable")
    inner.initialize(1, 1)
    cell.getText().insertTextContent(cell.getText().getStart(), inner, False)
    doc.getCurrentController().getViewCursor().gotoRange(inner.getCellByName("A1").getText().getStart(), False)
    return doc


def table_last_in_document(office):
    doc = _doc(office, ""); t = doc.getText()
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
    doc = _doc(office)
    doc.getCurrentController().select(_graphic(doc))
    return doc


def shape_selected(office):
    doc = _doc(office)
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
    doc = _doc(office)
    doc.getCurrentController().select(_frame(doc))
    return doc


def inside_frame(office):
    doc = _doc(office); f = _frame(doc)
    doc.getCurrentController().getViewCursor().gotoRange(f.getText().getEnd(), False)
    return doc


def _page_text(office, kind, text):
    doc = _doc(office)
    style = doc.StyleFamilies.getByName("PageStyles").getByName("Standard")
    setattr(style, kind + "IsOn", True)
    getattr(style, kind + "Text").setString(text)
    doc.getCurrentController().getViewCursor().gotoRange(getattr(style, kind + "Text").getEnd(), False)
    return doc


def header(office):
    return _page_text(office, "Header", "Đầu trang")


def footer(office):
    return _page_text(office, "Footer", "Chân trang")


def footnote(office):
    doc = _doc(office); t = doc.getText()
    fn = doc.createInstance("com.sun.star.text.Footnote")
    t.insertTextContent(t.getEnd(), fn, False)
    fn.setString("Chú thích")
    doc.getCurrentController().getViewCursor().gotoRange(fn.getEnd(), False)
    return doc


def text_selected(office):
    doc = _doc(office)
    vc = doc.getCurrentController().getViewCursor()
    vc.gotoStart(False); vc.gotoEnd(True)
    return doc


def multi_selection(office):
    doc = _doc(office, "abc thường abc thường")
    desc = doc.createSearchDescriptor(); desc.SearchString = "abc"
    doc.getCurrentController().select(doc.findAll(desc))
    return doc


def protected_section(office):
    doc = _doc(office); t = doc.getText()
    t.insertControlCharacter(t.getEnd(), 0, False)  # paragraph break
    sec = doc.createInstance("com.sun.star.text.TextSection")
    cur = t.createTextCursorByRange(t.getEnd())
    t.insertTextContent(cur, sec, False)
    sec.getAnchor().setString("Phần được bảo vệ")
    sec.IsProtected = True
    doc.getCurrentController().getViewCursor().gotoRange(sec.getAnchor().getEnd(), False)
    return doc


def plain_body(office):
    return _doc(office)


def comment_editing(office):
    doc = _doc(office)
    frame = doc.getCurrentController().getFrame()
    office.dispatch(frame, ".uno:InsertAnnotation")
    return doc


def read_only(office):
    doc = _doc(office)
    path = os.path.join(office.workdir, "read-only.odt")
    prop = PropertyValue(); prop.Name, prop.Value = "FilterName", "writer8"
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop,)); close(doc)
    prop = PropertyValue(); prop.Name, prop.Value = "ReadOnly", True
    return office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (prop,))


SCENARIOS = [plain_body, table_cell, table_cell_text_selected, table_cells_selected, nested_table_cell,
             table_last_in_document, image_selected, shape_selected, frame_selected, inside_frame, header, footer,
             footnote, text_selected, multi_selection, protected_section, comment_editing, read_only]
