# SPDX-License-Identifier: AGPL-3.0-only
"""Check the contextual ribbon tabs of HST Writer, Sheets and Slides on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-contextual.py [--instdir DIR] [--display :71] [--shots DIR] [--apps writer,calc,impress]
The X display must already run. For a table, a picture, a shape and a chart selected through the controller:
  - the tabs named as in Office appear, and the ribbon stays on the tab that was current;
  - with the cursor back in the text the tabs are gone; a contextual tab that was current falls back to Trang đầu;
  - clicking a chart tab and a chart command opens the dialog of the chart, without activating the chart by hand;
  - the ribbon height stays the same in every state.
Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

TABLE = ["Thiết kế Bảng", "Bố trí Bảng"]
PICTURE, SHAPE = ["Định dạng Ảnh"], ["Định dạng Hình dạng"]
CHART = ["Thiết kế Biểu đồ", "Định dạng Biểu đồ"]
ROWS = []
CHART_CLSID = "12dcae26-281f-416f-a234-c3086127382e"


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


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
    return made


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


def check_app(app, args, port, image_url):
    office, _wid, windows = gui.start(args.instdir, app, args.display, os.path.join(args.out, app), port)
    try:
        doc = office.desktop().getCurrentComponent()
        objects = make_objects(app, doc, image_url)
        park(app, doc, office)
        plain = gui.visible_names()
        home_box = dict((t[0], t[1]) for t in gui.ribbon_tabs())["Chèn"]
        gui.click(args.display, home_box)
        top = gui.geometry()
        height = top[1] - top[0]
        expected = {"table": TABLE, "picture": PICTURE, "shape": SHAPE, "chart": CHART}
        # the chart last: it stays activated after its command, and the ribbon follows the chart then
        for kind, target in sorted(objects.items(), key=lambda item: item[0] == "chart"):
            doc.CurrentController.select(target)
            time.sleep(2)
            names = gui.visible_names()
            wanted = expected[kind]
            record(f"[{app}] {kind}: tabs {wanted}", all(n in names for n in wanted), names)
            record(f"[{app}] {kind}: ribbon stays on Chèn", gui.selected() == ["Chèn"], gui.selected())
            now = gui.geometry()
            record(f"[{app}] {kind}: ribbon height unchanged", now[1] - now[0] == height, f"{now[1] - now[0]} vs {height}")
            if args.shots:
                office.screenshot(os.path.join(args.shots, f"{app}-{kind}.png"))
            first = dict((t[0], t[1]) for t in gui.ribbon_tabs()).get(wanted[0])
            if first:
                gui.click(args.display, first)
                record(f"[{app}] {kind}: click selects '{wanted[0]}'", gui.selected() == [wanted[0]], gui.selected())
                if args.shots:
                    office.screenshot(os.path.join(args.shots, f"{app}-{kind}-tab.png"))
            if kind == "chart":
                gui.check_chart_command(office, args, app, record)
            park(app, doc, office)
            record(f"[{app}] {kind}: tabs leave with the selection", gui.visible_names() == plain, gui.visible_names())
            record(f"[{app}] {kind}: contextual tab falls back", gui.selected() == ["Trang đầu"], gui.selected())
            gui.click(args.display, dict((t[0], t[1]) for t in gui.ribbon_tabs())["Chèn"])
        doc.setModified(False)  # no save prompt when the office terminates
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-contextual"))
    parser.add_argument("--shots")
    parser.add_argument("--apps", default="writer,calc,impress")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    image = "file://" + os.path.join(args.instdir, "program/about.png")
    if not os.path.exists(image[7:]):
        image = "file://" + os.path.join(args.instdir, "share/extensions/hst-vietnamese-tools/banners/aios@1x.png")
    for index, app in enumerate(args.apps.split(",")):
        try:
            check_app(app, args, 7300 + index, image)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
