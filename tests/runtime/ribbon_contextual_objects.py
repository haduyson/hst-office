# SPDX-License-Identifier: AGPL-3.0-only
"""Documents for check-ribbon-contextual.py: a table, a picture, a shape and a chart in each app, a pivot table in
Sheets and a page header in Writer, made through UNO; and the selection put back in the text or a plain cell."""
import time

CHART_CLSID = "12dcae26-281f-416f-a234-c3086127382e"


def size(width, height):
    import uno
    return uno.createUnoStruct("com.sun.star.awt.Size", width, height)


def point(x, y):
    import uno
    return uno.createUnoStruct("com.sun.star.awt.Point", x, y)


def make_objects(app, doc, image_url):
    """{kind: object to select} in a new document of the app; a table only where the app has one."""
    made = {}
    if app == "writer":
        text = doc.Text
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(2, 2)
        text.insertTextContent(text.getEnd(), table, False)
        made["table"] = table.getCellByName("A1")
        graphic = doc.createInstance("com.sun.star.text.TextGraphicObject")
        graphic.GraphicURL = image_url
        graphic.setSize(size(3000, 3000))
        text.insertTextContent(text.getEnd(), graphic, False)
        made["picture"] = graphic
        chart = doc.createInstance("com.sun.star.text.TextEmbeddedObject")
        chart.CLSID = CHART_CLSID
        chart.setSize(size(9000, 6000))
        text.insertTextContent(text.getEnd(), chart, False)
        made["chart"] = chart
        style = doc.StyleFamilies.getByName("PageStyles").getByName("Standard")
        style.HeaderIsOn = True
        made["header"] = style.HeaderText.getStart()
        page = doc.DrawPage
    elif app == "calc":
        sheet = doc.Sheets.getByIndex(0)
        page = sheet.DrawPage
        made["chart"] = None  # below, after the data
        for row, value in enumerate((1, 2, 3)):
            sheet.getCellByPosition(0, row).Value = value
    else:
        page = doc.DrawPages.getByIndex(0)
        chart = doc.createInstance("com.sun.star.drawing.OLE2Shape")
        page.add(chart)
        chart.CLSID = CHART_CLSID
        chart.setPosition(point(1000, 1000))
        chart.setSize(size(9000, 6000))
        made["chart"] = chart
        table = doc.createInstance("com.sun.star.drawing.TableShape")
        page.add(table)
        table.setPosition(point(12000, 1000))
        table.setSize(size(6000, 3000))
        made["table"] = table
    if app != "writer":
        graphic = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
        page.add(graphic)
        graphic.GraphicURL = image_url
        graphic.setPosition(point(1000, 8000))
        graphic.setSize(size(3000, 3000))
        made["picture"] = graphic
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    page.add(shape)
    shape.setPosition(point(5000, 8000))
    shape.setSize(size(3000, 2000))
    made["shape"] = shape
    if app == "calc":
        from com.sun.star.awt import Rectangle
        from com.sun.star.table import CellRangeAddress
        address = CellRangeAddress()
        address.Sheet, address.EndRow = 0, 2
        sheet.Charts.addNewByName("c1", Rectangle(9000, 1000, 9000, 6000), (address,), False, False)
        made["chart"] = page.getByIndex(page.Count - 1)
        made["pivot"] = make_pivot(sheet)
    return made


def make_pivot(sheet):
    """A small pivot table from H1:I4 at H11; returns a cell inside its output."""
    from com.sun.star.sheet.DataPilotFieldOrientation import ROW, DATA
    from com.sun.star.sheet.GeneralFunction import SUM
    from com.sun.star.table import CellAddress, CellRangeAddress
    for row, (name, value) in enumerate((("Nhóm", None), ("a", 1), ("b", 2), ("a", 3))):
        sheet.getCellByPosition(7, row).String = name
        if value is None:
            sheet.getCellByPosition(8, row).String = "Số"
        else:
            sheet.getCellByPosition(8, row).Value = value
    tables = sheet.DataPilotTables
    descriptor = tables.createDataPilotDescriptor()
    source = CellRangeAddress()
    source.Sheet, source.StartColumn, source.EndColumn, source.EndRow = 0, 7, 8, 3
    descriptor.setSourceRange(source)
    fields = descriptor.DataPilotFields
    fields.getByIndex(0).Orientation = ROW
    data = fields.getByIndex(1)
    data.Orientation, data.Function = DATA, SUM
    target = CellAddress()
    target.Sheet, target.Column, target.Row = 0, 7, 10
    tables.insertNewByName("p1", target, descriptor)
    return sheet.getCellByPosition(7, 12)


def park(app, doc, office):
    """Selection back in the text or a plain cell."""
    controller = doc.CurrentController
    if app == "writer":  # out of a frame or a chart first, then past the table at the start of the document
        office.dispatch(controller.getFrame(), ".uno:Escape")
        office.dispatch(controller.getFrame(), ".uno:Escape")
        time.sleep(0.5)
        controller.select(doc.Text.getEnd())
    elif app == "calc":
        controller.select(doc.Sheets.getByIndex(0).getCellByPosition(5, 20))
    else:
        import uno
        controller.select(uno.Any("void", None))
    time.sleep(1)
