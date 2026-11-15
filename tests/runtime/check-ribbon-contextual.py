# SPDX-License-Identifier: AGPL-3.0-only
"""Check the contextual ribbon tabs of HST Writer, Sheets and Slides on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-contextual.py [--instdir DIR] [--display :71] [--shots DIR] [--apps writer,calc,impress]
The X display must already run. For a table, a picture, a shape and a chart selected through the controller, in
Sheets also for the cell cursor in a pivot table and in Writer for the cursor in a page header:
  - the tabs named as in Office appear, and the ribbon stays on the tab that was current; entering a header opens
    "Đầu trang & chân trang" instead, as Word opens Header & Footer;
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
from ribbon_contextual_objects import make_objects, park  # noqa: E402

TABLE = ["Thiết kế bảng", "Bố trí bảng"]
PICTURE, SHAPE = ["Định dạng ảnh"], ["Định dạng hình dạng"]
CHART = ["Thiết kế biểu đồ", "Định dạng biểu đồ"]
PIVOT = ["Phân tích bảng tổng hợp"]
HEADER = ["Đầu trang & chân trang"]
OPENS = {"header"}  # contexts whose tab opens on entry (the others only appear)
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


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
        expected = {"table": TABLE, "picture": PICTURE, "shape": SHAPE, "chart": CHART, "pivot": PIVOT, "header": HEADER}
        # the pivot table first: after a drawing selection, the cursor moved through the API does not switch Sheets
        # to its pivot shell (a mouse click is not checked here); the chart last: it stays activated after its
        # command, and the ribbon follows the chart then
        order = {"pivot": -1, "chart": 1}
        for kind, target in sorted(objects.items(), key=lambda item: order.get(item[0], 0)):
            doc.CurrentController.select(target)
            time.sleep(2)
            names = gui.visible_names()
            wanted = expected[kind]
            record(f"[{app}] {kind}: tabs {wanted}", all(n in names for n in wanted), names)
            if kind in OPENS:
                record(f"[{app}] {kind}: '{wanted[0]}' opens", gui.selected() == [wanted[0]], gui.selected())
            else:
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
    finally:
        try:  # no save prompt at terminate, also after a failed step: terminate() would wait on it for ever
            doc.setModified(False)
        except Exception:  # noqa: BLE001 - no document yet, or the office is gone; stop() handles that
            pass
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
