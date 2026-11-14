# SPDX-License-Identifier: AGPL-3.0-only
"""The picture and table style galleries on the ribbon of HST Writer, Sheets and Slides (gtk3, vi_VN).

Usage: python3 tests/runtime/check-style-galleries-screen.py --instdir DIR [--display :83] [--out DIR] [--dark]
The X display must already run. For each app at 1920x1000: selects a picture, opens "Định dạng ảnh", finds the
gallery "Kiểu dáng ảnh" (one row, at least 3 tiles), clicks the "Viền xanh" tile and checks the picture got the
blue outline; then the same with the table, "Thiết kế bảng", "Kiểu dáng bảng" and its first tile (Xanh HST).
Saves the ribbon of each tab (ribbon-<app>-<kind>[-dark].png). --dark runs in dark mode (application colours
dark, GTK Adwaita:dark). AT-SPI runs here (system Python, as the build user under dbus-run-session); the UNO
steps run in the office's own Python (style_galleries_screen_uno.py), which a packaged office brings.
"""
import argparse
import json
import os
import socket
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
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style_galleries_screen_uno.py")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


class SocketOffice(hst_gui.Office):
    """hst_gui.Office whose UNO bridge lives in the worker: here only wait for the socket."""
    def _connect(self, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    time.sleep(3)
                    return None
            time.sleep(1)
        raise RuntimeError("the office socket did not open")


def uno(args, port, *command):
    python = os.path.join(args.instdir, "program", "python")
    out = subprocess.run([python, WORKER, str(port), *command], capture_output=True, text=True, timeout=120)
    if out.returncode:
        raise RuntimeError(f"{command}: {out.stderr.strip()[-400:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def start(args, app, port):
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False,
                   stderr=subprocess.DEVNULL)
    config = [("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]
    env = {}
    if args.dark:
        config.append(("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2"))
        env["GTK_THEME"] = "Adwaita:dark"
    office = SocketOffice(args.instdir, os.path.join(args.out, app + ("-dark" if args.dark else "")), port,
                          display=args.display, extra_args=[f"--{app}"], nodefault=False, config=config, env=env)
    office.start()
    time.sleep(8)
    window = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
    gui.xdo(args.display, "windowmove", window, "0", "0")
    gui.xdo(args.display, "windowsize", window, "1920", "1000")
    time.sleep(4)
    return office


def gallery(name):
    """(box, tiles) of the gallery: the named ribbon node, then the first node below it with the tiles."""
    for found, _role, box, node in gui.ribbon_nodes({"layered pane", "list", "tree table", "table", "panel",
                                                     "scroll pane", "filler"}):
        if found != name:
            continue
        for inner in gui.walk(node):
            tiles = [inner.getChildAtIndex(i) for i in range(min(inner.childCount, 40))]
            tiles = [t for t in tiles if t is not None and t.getRoleName() in ("icon", "list item", "table cell")]
            if len(tiles) >= 1:
                return box, [t for t in tiles if gui.extents(t)[2] > 0 and gui.extents(t)[1] >= 0]
    return None, []


def check_kind(args, app, port, kind):
    tag = "-dark" if args.dark else ""
    tab, name, tile_name = GALLERIES[kind]
    uno(args, port, "select", app, kind)
    time.sleep(2)
    record(f"[{app}] {kind}: '{tab}' opens", gui.open_tab(args.display, tab), gui.selected())
    time.sleep(1.5)
    box, tiles = gallery(name)
    tops = {gui.extents(n)[1] for n in tiles}
    record(f"[{app}] {kind}: gallery '{name}' shows one row of at least 3 tiles",
           box is not None and len(tiles) >= 3 and len(tops) == 1, (box, len(tiles), tops))
    full = os.path.join(args.out, f"full-{app}-{kind}{tag}.png")
    hst_gui.screenshot(full, args.display)
    subprocess.run(["convert", full, "-crop", "1920x240+0+0", os.path.join(args.out, f"ribbon-{app}-{kind}{tag}.png")],
                   check=False)
    tile = next((t for t in tiles if (t.name or "") == tile_name), None)
    if tile is None:
        record(f"[{app}] {kind}: tile '{tile_name}' is there", False, [t.name for t in tiles])
        return
    gui.click(args.display, gui.extents(tile))
    time.sleep(1.5)
    state = uno(args, port, "state", app, kind)
    if kind == "picture":
        record(f"[{app}] picture: a click on '{tile_name}' outlines the picture blue", state["colour"] == 0x0072BB, state)
    else:
        record(f"[{app}] table: a click on '{tile_name}' applies HST Blue", state["style"] == "HST Blue", state)


def check(app, args, port, png):
    office = start(args, app, port)
    try:
        uno(args, port, "setup", app, png)
        for kind in ("picture", "table"):
            check_kind(args, app, port, kind)
    finally:
        try:
            uno(args, port, "quit", app)
        except Exception:  # noqa: BLE001 - the office may be gone; stop() ends it
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
