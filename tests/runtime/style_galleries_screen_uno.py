# SPDX-License-Identifier: AGPL-3.0-only
"""UNO side of check-style-galleries-screen.py, run with the office's own Python (the packaged office brings
its Python, which has no AT-SPI). One command per call against the running office's socket; prints JSON.

  python style_galleries_screen_uno.py PORT setup APP PNG   picture "hstpic" and table "hsttable" in the document
  python style_galleries_screen_uno.py PORT select APP picture|table
  python style_galleries_screen_uno.py PORT state APP picture|table
  python style_galleries_screen_uno.py PORT quit APP
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style_galleries_uno as sg  # noqa: E402


class Remote:
    def __init__(self, port):
        import uno
        self.uno = uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
        self.desktop = self.service("com.sun.star.frame.Desktop")

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def url(self, path):
        return self.uno.systemPathToFileUrl(os.path.abspath(path))


def point(x, y):
    from com.sun.star.awt import Point
    return Point(x, y)


def page_of(app, doc):
    return doc.DrawPage if app == "writer" else doc.Sheets.getByIndex(0).DrawPage if app == "calc" \
        else doc.DrawPages.getByIndex(0)


def named(page, name):
    return next(page.getByIndex(i) for i in range(page.Count) if page.getByIndex(i).Name == name)


def setup(remote, app, doc, png):
    if app == "writer":
        picture = sg.writer_picture(remote, doc, png)
        picture.Name = "hstpic"
        sg.writer_table(doc).Name = "hsttable"
    elif app == "calc":
        sheet, _table = sg.sheets_table(doc)
        picture = sg.shape_picture(remote, doc, sheet.DrawPage, png)
        picture.Name, picture.Position = "hstpic", point(9000, 500)
    else:
        page = page_of(app, doc)
        while page.Count:
            page.remove(page.getByIndex(0))
        picture = sg.shape_picture(remote, doc, page, png)
        picture.Name = "hstpic"
        table = sg.slides_table(doc, page)
        table.Name, table.Position = "hsttable", point(9000, 1000)
    return {"ok": True}


def target(app, doc, kind):
    if app == "writer":
        return doc.GraphicObjects.getByName("hstpic") if kind == "picture" \
            else doc.TextTables.getByName("hsttable").getCellByName("B2")
    if app == "calc" and kind == "table":
        return doc.Sheets.getByIndex(0).getCellRangeByName("B2")
    return named(page_of(app, doc), "hst" + ("pic" if kind == "picture" else "table"))


def state(app, doc, kind):
    if kind == "picture":
        obj = target(app, doc, kind)
        return {"colour": obj.TopBorder.Color if app == "writer" else obj.LineColor}
    if app == "writer":
        table = doc.TextTables.getByName("hsttable")
        return {"style": table.TableTemplateName, "colour": table.getCellByName("A1").BackColor}
    if app == "calc":
        return {"style": doc.DatabaseRanges.getByName("Bang1").TableStyleName}
    table = named(page_of(app, doc), "hsttable")
    return {"style": table.TableTemplate.Name if table.TableTemplate else None,
            "colour": table.Model.getCellByPosition(0, 0).FillColor}


def main():
    port, command, app = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    remote = Remote(port)
    doc = remote.desktop.getCurrentComponent()
    if command == "setup":
        result = setup(remote, app, doc, sys.argv[4])
    elif command == "select":
        doc.getCurrentController().select(target(app, doc, sys.argv[4]))
        result = {"ok": True}
    elif command == "state":
        result = state(app, doc, sys.argv[4])
    else:  # quit: no save prompt, then the office ends
        doc.setModified(False)
        result = {"ok": True}
        print(json.dumps(result), flush=True)
        try:
            remote.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        return
    print(json.dumps(result))


if __name__ == "__main__":
    main()
