# SPDX-License-Identifier: AGPL-3.0-only
"""Fixtures and helpers of check-style-galleries.py: a picture and a table in Writer, Sheets and Slides,
the vnd.hst.styles: dispatch, undo counting and OOXML part reading."""
import os
import struct
import zipfile
import zlib

from headless_office import props

RESULTS = []
PICTURE_IDS = ["none", "thin", "blue", "white-shadow", "soft-shadow", "dark-frame", "thin-drop-shadow", "blue-shadow"]
TABLE_IDS = ["HST Blue", "HST Light Grid", "HST Green", "HST Orange", "HST Teal", "HST Purple", "HST Charcoal",
             "HST Minimal"]
# (line colour, line width 1/100 mm, shadow distance) as svx HstStyleGalleryData.cxx defines them
PICTURES = {"none": (None, 0, 0), "thin": (0x7F8C99, 26, 0), "blue": (0x0072BB, 79, 0),
            "white-shadow": (0xFFFFFF, 212, 106), "soft-shadow": (None, 0, 141), "dark-frame": (0x322E2E, 212, 0),
            "thin-drop-shadow": (0x7F8C99, 26, 141), "blue-shadow": (0x0072BB, 79, 106)}
# header fill (None: no fill) and band fill of each table style
TABLES = {"HST Blue": (0x0072BB, 0xE3EFF8), "HST Light Grid": (None, 0xF2F4F7), "HST Green": (0x1E8E3E, 0xE6F4EA),
          "HST Orange": (0xD9480F, 0xFDEBDD), "HST Teal": (0x0F8A8A, 0xE0F2F2), "HST Purple": (0x7B3FC4, 0xEFE6FA),
          "HST Charcoal": (0x322E2E, 0xEFEFEF), "HST Minimal": (None, None)}


def record(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"), flush=True)


def write_png(path, width=64, height=48):
    """A small opaque PNG (sky over grass), so the picture fixtures need no file in the repository."""
    rows = b"".join(b"\x00" + (b"\xcf\xe5\xf5" if y < height // 2 else b"\x3e\x8e\x55") * width for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def graphic(office, png):
    provider = office.service("com.sun.star.graphic.GraphicProvider")
    return provider.queryGraphic(props(URL=office.url(png)))


def size(width, height):
    from com.sun.star.awt import Size
    return Size(width, height)


def shape_picture(office, doc, page, png):
    shape = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
    page.add(shape)
    shape.Graphic = graphic(office, png)
    shape.setSize(size(6000, 4500))
    return shape


def writer_picture(office, doc, png):
    picture = doc.createInstance("com.sun.star.text.TextGraphicObject")
    picture.Graphic = graphic(office, png)
    picture.Width, picture.Height = 6000, 4500
    text = doc.getText()
    text.insertTextContent(text.getEnd(), picture, False)
    return picture


def writer_table(doc):
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(5, 3)
    text = doc.getText()
    text.insertTextContent(text.getEnd(), table, False)
    for row in range(5):
        for col, letter in enumerate("ABC"):
            table.getCellByName(f"{letter}{row + 1}").setString("Tiêu đề" if row == 0 else f"{row}{letter}")
    return table


def sheets_table(doc):
    from com.sun.star.table import CellRangeAddress
    sheet = doc.Sheets.getByIndex(0)
    for row in range(5):
        for col in range(3):
            sheet.getCellByPosition(col, row).setString(f"Cột {col + 1}" if row == 0 else f"{row * 10 + col}")
    ranges = doc.DatabaseRanges
    ranges.addNewByName("Bang1", CellRangeAddress(0, 0, 0, 2, 4))
    table = ranges.getByName("Bang1")
    table.ContainsHeader = True
    table.TableStyleName = "TableStyleMedium2"  # a style makes the database range a table
    table.UseRowStripes = True
    return sheet, table


def slides_table(doc, page):
    shape = doc.createInstance("com.sun.star.drawing.TableShape")
    page.add(shape)
    shape.setSize(size(12000, 6000))
    model = shape.Model
    model.Rows.insertByIndex(0, 3)
    model.Columns.insertByIndex(0, 2)
    for row in range(model.Rows.Count):
        for col in range(model.Columns.Count):
            model.getCellByPosition(col, row).setString(f"{col}{row}")
    return shape


def dispatch(office, doc, target, style):
    frame = doc.getCurrentController().getFrame()
    office.service("com.sun.star.frame.DispatchHelper").executeDispatch(
        frame, f"vnd.hst.styles:{target}", "", 0, props(Style=style))


def undo_count(doc):
    return len(doc.getUndoManager().getAllUndoActionTitles())


def store(office, doc, path, filter_name):
    doc.storeToURL(office.url(path), props(FilterName=filter_name, Overwrite=True))


def part(path, member_prefix):
    """The concatenated text of the zip members whose names start with member_prefix."""
    with zipfile.ZipFile(path) as archive:
        return "".join(archive.read(name).decode("utf-8") for name in archive.namelist()
                       if name.startswith(member_prefix))
