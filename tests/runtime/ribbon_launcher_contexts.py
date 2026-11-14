# SPDX-License-Identifier: AGPL-3.0-only
"""Document contexts for the ribbon launcher checks (check-ribbon-launchers.py on Linux,
check-windows-ribbon-launchers.py on Windows): a contextual tab's launcher needs a table, a picture or a shape
selected. Plain UNO, so the office's own python.exe runs it."""
import base64
import os

MODULES = {"writer": "swriter", "calc": "scalc", "impress": "simpress", "draw": "sdraw"}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def file_url(path):
    return "file:///" + os.path.abspath(path).replace("\\", "/").lstrip("/")


def add_shape(doc, text=""):
    from com.sun.star.awt import Point, Size
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    page = doc.getDrawPage() if hasattr(doc, "getDrawPage") else doc.getDrawPages().getByIndex(0)
    page.add(shape)
    shape.setPosition(Point(2000, 2000))
    shape.setSize(Size(6000, 3000))
    if text:
        shape.setString(text)
    doc.getCurrentController().select(shape)
    return shape


def add_picture(doc, workdir):
    path = os.path.join(workdir, "pixel.png")
    with open(path, "wb") as handle:
        handle.write(PNG)
    graphic = doc.createInstance("com.sun.star.text.TextGraphicObject")
    graphic.GraphicURL = file_url(path)
    graphic.Width, graphic.Height = 4000, 3000
    text = doc.getText()
    text.insertString(text.getEnd(), "Đoạn văn có ảnh. " * 20, False)
    text.insertTextContent(text.getStart(), graphic, False)
    doc.getCurrentController().select(graphic)
    return graphic


def prepare(doc, app, context, workdir):
    """Select what the launcher's group acts on in a new document `doc` of `app`."""
    if context == "table":
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(2, 2)
        doc.getText().insertTextContent(doc.getText().getEnd(), table, False)
        doc.getCurrentController().select(table.getCellByName("A1").createTextCursor())
    elif context == "picture":
        add_picture(doc, workdir)
    elif context == "shape":
        add_shape(doc, "Hình" if app in ("impress", "draw") else "")
    elif app == "writer":
        doc.getText().setString("Đoạn văn mẫu.")
    elif app == "calc":
        doc.getCurrentController().select(doc.Sheets.getByIndex(0).getCellRangeByName("A1"))
