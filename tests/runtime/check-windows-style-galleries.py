#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The picture and table style galleries on the ribbon of HST Writer, Sheets and Slides on Windows.

Usage (the office's own python.exe, in the tester's own session, see windows-own-session-task.ps1):
    "<install>\\program\\python.exe" tests/runtime/check-windows-style-galleries.py --install DIR --out DIR [--port 2190]
For each app: a picture and a table; selects the picture, opens "Định dạng ảnh" through accessibility, checks the
gallery "Kiểu dáng ảnh" shows one row of at least 3 tiles, saves the window (PrintWindow, also in a disconnected
session), chooses the "Viền xanh" tile through accessibility and checks the outline; the same for the table and
"Xanh HST". No keys or clicks are sent. Evidence: <out>/results.json and <out>/<app>-<kind>.png. Exit 1 on a FAIL.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style_galleries_uno as sg  # noqa: E402
import windows_gui as wg  # noqa: E402
from citations_dialogs_win32 import Win32Driver, office_windows  # noqa: E402

APPS = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides"}
GALLERIES = {"picture": ("Định dạng ảnh", "Kiểu dáng ảnh", "Viền xanh"),
             "table": ("Thiết kế bảng", "Kiểu dáng bảng", "Xanh HST")}


class Shim:
    def __init__(self, office):
        self.office = office

    def service(self, name):
        return self.office.service(name)

    def url(self, path):
        import uno
        return uno.systemPathToFileUrl(os.path.abspath(path))


def set_ui_vietnamese(office):
    import uno
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", "/org.openoffice.Setup/L10N"
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
    access.setPropertyValue("ooLocale", "vi")
    access.commitChanges()


def make(app, doc, shim, png):
    if app == "writer":
        picture = sg.writer_picture(shim, doc, png)
        table = sg.writer_table(doc)
        return picture, table.getCellByName("B2"), lambda: table.getCellByName("A1").BackColor
    if app == "calc":
        sheet, table = sg.sheets_table(doc)
        picture = sg.shape_picture(shim, doc, sheet.DrawPage, png)
        return picture, sheet.getCellRangeByName("B2"), lambda: 0x0072BB if table.TableStyleName == "HST Blue" else -1
    page = doc.DrawPages.getByIndex(0)
    while page.Count:
        page.remove(page.getByIndex(0))
    picture = sg.shape_picture(shim, doc, page, png)
    table = sg.slides_table(doc, page)
    return picture, table, lambda: table.Model.getCellByPosition(0, 0).FillColor


def choose(context):
    """Select an accessible child (a page tab, a gallery tile) in its parent, as a click does."""
    parent = context.getAccessibleParent().getAccessibleContext()
    parent.selectAccessibleChild(context.getAccessibleIndexInParent())
    time.sleep(1.5)


def tiles_of(root, name):
    for context, _depth in wg.walk(root):
        try:
            if context.getAccessibleName() == name and context.getAccessibleChildCount() >= 1:
                kids = [context.getAccessibleChild(i).getAccessibleContext()
                        for i in range(context.getAccessibleChildCount())]
                if all(kid.getAccessibleName() for kid in kids):
                    return kids
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
    return []


def check_app(office, app, check, out, png):
    doc = office.load("private:factory/s" + ("writer" if app == "writer" else "calc" if app == "calc" else "impress"))
    try:
        picture, table, table_state = make(app, doc, Shim(office), png)
        root = doc.CurrentController.Frame.ContainerWindow
        hwnd = next((h for h, title in office_windows() if APPS[app] in title), None)
        for kind, target in (("picture", picture), ("table", table)):
            tab, name, tile_name = GALLERIES[kind]
            doc.CurrentController.select(target)
            time.sleep(2)
            page_tab = wg.find_named(root, tab, "PAGE_TAB")
            if page_tab is not None:
                choose(page_tab)
            check("[%s] %s: tab '%s'" % (app, kind, tab), page_tab is not None)
            tiles = tiles_of(root, name)
            tops = {t.getLocationOnScreen().Y for t in tiles if wg.showing(t)}
            check("[%s] %s: gallery '%s' one row of at least 3 tiles" % (app, kind, name),
                  len([t for t in tiles if wg.showing(t)]) >= 3 and len(tops) == 1,
                  ([t.getAccessibleName() for t in tiles], sorted(tops)))
            if hwnd:
                Win32Driver().screenshot(hwnd, os.path.join(out, "%s-%s.png" % (app, kind)))
            tile = next((t for t in tiles if t.getAccessibleName() == tile_name), None)
            if tile is None:
                check("[%s] %s: tile '%s'" % (app, kind, tile_name), False)
                continue
            choose(tile)
            if kind == "picture":
                colour = picture.TopBorder.Color if app == "writer" else picture.LineColor
            else:
                colour = table_state()
            check("[%s] %s: choosing '%s' applies HST blue" % (app, kind, tile_name), colour == 0x0072BB, hex(colour))
            if hwnd:
                Win32Driver().screenshot(hwnd, os.path.join(out, "%s-%s-applied.png" % (app, kind)))
    finally:
        doc.setModified(False)
        doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2190)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    check = wg.Results(out, "style-galleries")
    png = os.path.join(out, "picture.png")
    sg.write_png(png)
    office = wg.WinOffice(args.install, os.path.join(out, "profile"), args.port, os.path.join(out, "log"))
    try:
        office.start(fresh=True)
        seen = wg.dismiss_startup(office, os.path.join(out, "startup.png"), timeout=30, settle=5)
        check.note("start-up dialogs", seen)
        set_ui_vietnamese(office)  # a fresh profile follows the Windows language; the names checked are Vietnamese
        seen = seen or ["restart for the UI language"]
        # a document loaded right after a start-up question was ended over UNO has crashed the office on this
        # harness (check-windows-ui-mode-tabs.py): start again until a start shows no question
        for start in range(2, 5):
            if not seen:
                break
            office.stop()
            office.start()
            seen = wg.dismiss_startup(office, os.path.join(out, "startup-%d.png" % start), timeout=15, settle=3)
            check.note("start-up dialogs, start %d" % start, seen)
        for app in APPS:
            try:
                check_app(office, app, check, out, png)
            except Exception:  # noqa: BLE001
                import traceback
                check("[%s] ran" % app, False, traceback.format_exc()[-1200:])
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
