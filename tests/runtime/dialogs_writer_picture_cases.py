# SPDX-License-Identifier: AGPL-3.0-only
"""Picture properties follow Word's Layout: Position, Text Wrapping, Size. Used by check-dialogs-writer.py."""
import base64
import os

from hst_dialog_uitest import click, has_child, props, select_tab, tab_titles, type_value, visible

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

# style radio: wrap mode, in background, contour, contour outside
STYLES = {
    "hstwrapsquare": ("PARALLEL", False, False, None),
    "hstwraptight": ("PARALLEL", False, True, True),
    "hstwrapthrough": ("PARALLEL", False, True, False),
    "hstwraptopbottom": ("NONE", False, False, None),
    "hstwrapbehind": ("THROUGH", True, False, None),
    "hstwrapfront": ("THROUGH", False, False, None),
}


def new_picture(h, doc):
    path = os.path.join(h.office.workdir, "pixel.png")
    with open(path, "wb") as handle:
        handle.write(PNG)
    graphic = doc.createInstance("com.sun.star.text.TextGraphicObject")
    graphic.GraphicURL = "file://" + path
    graphic.Width, graphic.Height = 4000, 3000
    text = doc.getText()
    text.insertString(text.getEnd(), "Đoạn văn có ảnh. " * 20, False)
    text.insertTextContent(text.getStart(), graphic, False)
    doc.getCurrentController().select(graphic)
    h.wait_idle()
    return graphic


def state_of(graphic):
    outside = graphic.ContourOutside if graphic.SurroundContour else None
    return (graphic.Surround.value, not graphic.Opaque, graphic.SurroundContour, outside)


def set_style(h, doc, graphic, radio):
    doc.getCurrentController().select(graphic)
    dlg = h.open_dialog(".uno:GraphicDialog", "PictureDialog")
    select_tab(dlg, 1)
    click(dlg, radio)
    click(dlg, "ok")
    h.wait_idle()


def check_picture(h, c):
    doc = h.new_document()
    graphic = new_picture(h, doc)
    dlg = h.open_dialog(".uno:GraphicDialog", "PictureDialog")
    titles = tab_titles(dlg)
    c.equal("picture: Word's three tabs at one level", titles[:3], ["Vị trí", "Ngắt dòng văn bản", "Kích cỡ"])
    c.equal("picture: nothing removed", len(titles), 11)
    select_tab(dlg, 0)
    c.equal("picture: size is not on Position", visible(dlg, "width"), False)
    c.equal("picture: anchor is on Position", visible(dlg, "topara"), True)
    select_tab(dlg, 2)
    c.equal("picture: width is on Size", visible(dlg, "width"), True)
    c.equal("picture: anchor is not on Size", visible(dlg, "topara"), False)
    type_value(dlg, "width", "6")
    select_tab(dlg, 0)  # leaving and coming back must keep the typed value
    select_tab(dlg, 2)
    click(dlg, "ok")
    h.wait_idle()
    c.equal("picture: Size tab reaches the document", abs(graphic.Width - 6000) <= 10, True)

    for radio, expected in STYLES.items():
        if radio == "hstwrapsquare":  # a new picture is already Square: leave it first, so the click changes it
            set_style(h, doc, graphic, "hstwraptopbottom")
        set_style(h, doc, graphic, radio)
        c.equal(f"wrap: {radio} applied", state_of(graphic), expected)
        path = os.path.join(h.office.workdir, f"{radio}.docx")
        doc.storeToURL("file://" + path, props(FilterName="MS Word 2007 XML"))
        again = h.office.load("file://" + path)
        c.equal(f"wrap: {radio} after DOCX", state_of(again.getGraphicObjects().getByIndex(0)), expected)
        h.close_document(again)

    set_style(h, doc, graphic, "hstwrapinline")
    c.equal("wrap: In Line anchors as character", graphic.AnchorType.value, "AS_CHARACTER")
    set_style(h, doc, graphic, "hstwrapsquare")
    c.equal("wrap: Square leaves the line", (graphic.AnchorType.value, graphic.Surround.value), ("AT_PARAGRAPH", "PARALLEL"))
    h.close_document(doc)


def check_frame_style_keeps_size(h, c):
    """The frame style dialog has no Size tab: its one page must still show the size fields."""
    doc = h.new_document()
    dlg = h.open_dialog(".uno:InsertFrame", "FrameDialog")
    c.equal("frame: same tabs as the picture", tab_titles(dlg)[:3], ["Vị trí", "Ngắt dòng văn bản", "Kích cỡ"])
    c.equal("frame: position page still present", has_child(dlg, "topara"), True)
    click(dlg, "cancel")
    h.close_document(doc)
