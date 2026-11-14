# SPDX-License-Identifier: AGPL-3.0-only
"""The picture and table style galleries on the ribbon of HST Writer, Sheets and Slides (gtk3, vi_VN).

Usage: python3 tests/runtime/check-style-galleries-screen.py --instdir DIR [--display :83] [--out DIR] [--dark]
The X display must already run. For each app at 1920x1000: selects a picture, opens "Định dạng ảnh", finds the
gallery "Kiểu dáng ảnh" (one row, at least 3 tiles), clicks the "Viền xanh" tile and checks the picture got the
blue outline; then the same with the table, "Thiết kế bảng", "Kiểu dáng bảng" and its first tile (Xanh HST).
Saves the ribbon of each tab (ribbon-<app>-<kind>[-dark].png). --dark runs in dark mode (application colours
dark, GTK Adwaita:dark). Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json.
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
import style_galleries_uno as sg  # noqa: E402

NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides"}
GALLERIES = {"picture": ("Định dạng ảnh", "Kiểu dáng ảnh", "Viền xanh"),
             "table": ("Thiết kế bảng", "Kiểu dáng bảng", "Xanh HST")}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


class Shim:
    """What style_galleries_uno needs from an office: services and file URLs."""
    def __init__(self, office):
        self.office = office

    def service(self, name):
        return self.office.service(name)

    def url(self, path):
        return "file://" + os.path.abspath(path)


def start(args, app, port):
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False,
                   stderr=subprocess.DEVNULL)
    config = [("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]
    env = {}
    if args.dark:
        config.append(("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2"))
        env["GTK_THEME"] = "Adwaita:dark"
    office = hst_gui.Office(args.instdir, os.path.join(args.out, app + ("-dark" if args.dark else "")), port,
                            display=args.display, extra_args=[f"--{app}"], nodefault=False, config=config, env=env)
    office.start()
    time.sleep(8)
    window = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
    gui.xdo(args.display, "windowmove", window, "0", "0")
    gui.xdo(args.display, "windowsize", window, "1920", "1000")
    time.sleep(4)
    return office


def point(x, y):
    from com.sun.star.awt import Point
    return Point(x, y)


def objects(app, doc, shim, png):
    if app == "writer":
        picture = sg.writer_picture(shim, doc, png)
        table = sg.writer_table(doc)
        return picture, table.getCellByName("B2"), lambda: table.getCellByName("A1").BackColor
    if app == "calc":
        sheet, table = sg.sheets_table(doc)
        picture = sg.shape_picture(shim, doc, sheet.DrawPage, png)
        picture.Position = point(9000, 500)
        return picture, sheet.getCellRangeByName("B2"), lambda: table.TableStyleName
    page = doc.DrawPages.getByIndex(0)
    while page.Count:
        page.remove(page.getByIndex(0))
    picture = sg.shape_picture(shim, doc, page, png)
    table = sg.slides_table(doc, page)
    table.Position = point(9000, 1000)
    return picture, table, lambda: table.Model.getCellByPosition(0, 0).FillColor


def gallery(name):
    """The gallery's icon view: the named ribbon node whose children are the tiles."""
    for found, _role, box, node in gui.ribbon_nodes({"layered pane", "list", "tree table", "table", "panel"}):
        if found == name and node.childCount >= 1:
            tiles = [node.getChildAtIndex(i) for i in range(node.childCount)]
            return box, [t for t in tiles if t is not None and gui.showing(t)]
    return None, []


def check(app, args, port, png):
    office = start(args, app, port)
    tag = "-dark" if args.dark else ""
    doc = office.desktop().getCurrentComponent()
    try:
        picture, table_target, table_state = objects(app, doc, Shim(office), png)
        for kind, target in (("picture", picture), ("table", table_target)):
            doc.CurrentController.select(target)
            time.sleep(2)
            tab, name, tile_name = GALLERIES[kind]
            record(f"[{app}] {kind}: '{tab}' opens", gui.open_tab(args.display, tab), gui.selected())
            time.sleep(1.5)
            box, tiles = gallery(name)
            heights = {t[3] for t in (gui.extents(n) for n in tiles)}
            tops = {gui.extents(n)[1] for n in tiles}
            record(f"[{app}] {kind}: gallery '{name}' shows one row of at least 3 tiles",
                   box is not None and len(tiles) >= 3 and len(tops) == 1, (box, len(tiles), tops, heights))
            office.screenshot(os.path.join(args.out, f"full-{app}-{kind}{tag}.png"))
            subprocess.run(["convert", os.path.join(args.out, f"full-{app}-{kind}{tag}.png"), "-crop", "1920x260+0+0",
                            os.path.join(args.out, f"ribbon-{app}-{kind}{tag}.png")], check=False)
            tile = next((t for t in tiles if (t.name or "") == tile_name), None)
            if tile is None:
                record(f"[{app}] {kind}: tile '{tile_name}' is there", False, [t.name for t in tiles])
                continue
            before = picture.LineColor if kind == "picture" and app != "writer" else None
            gui.click(args.display, gui.extents(tile))
            time.sleep(1.5)
            if kind == "picture":
                colour = picture.TopBorder.Color if app == "writer" else picture.LineColor
                record(f"[{app}] picture: a click on '{tile_name}' outlines the picture blue", colour == 0x0072BB,
                       (hex(colour), before))
            else:
                state = table_state()
                record(f"[{app}] table: a click on '{tile_name}' applies HST Blue", state in ("HST Blue", 0x0072BB),
                       state if isinstance(state, str) else hex(state))
    finally:
        try:
            doc.setModified(False)
        except Exception:  # noqa: BLE001 - the office may be gone; stop() handles that
            pass
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":83")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/style-galleries-screen"))
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    png = os.path.join(args.out, "picture.png")
    sg.write_png(png)
    for index, app in enumerate(args.apps.split(",")):
        try:
            check(app, args, 7480 + index, png)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
    suffix = "-dark" if args.dark else ""
    with open(os.path.join(args.out, f"evidence{suffix}.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
