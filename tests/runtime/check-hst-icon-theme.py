#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Capture three tabs per app with geometry evidence on an existing Xvfb display.

Run each baseline/product, light/dark, scale 1/2 combination in a separate process.
--legacy-binary selects HST explicitly: it does NOT test the new C++ auto selector.
PNG captures are native physical pixels; no screenshot resizing is performed.
"""
import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_gui
from hst_icon_theme_surfaces import surfaces

spec = importlib.util.spec_from_file_location("tabs", Path(__file__).with_name("check-ribbon-tabs.py"))
tabs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tabs)
APP_TABS = {"writer": ("Trang đầu", "Chèn", "Bố cục"),
            "calc": ("Trang đầu", "Chèn", "Dữ liệu"),
            "impress": ("Trang đầu", "Chèn", "Thiết kế")}


def walk_ui(node, depth=0):
    if node is None:
        return
    try:
        role = node.getRoleName()
    except Exception:
        return
    yield node
    # Geometry needs the chrome, not every accessible spreadsheet cell. Avoid
    # making 200% screenshot runs spend minutes traversing the document model.
    if role in ("document text", "document spreadsheet", "document presentation", "table") or depth >= 14:
        return
    try:
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))]
    except Exception:
        return
    for child in children:
        yield from walk_ui(child, depth + 1)


tabs.walk = walk_ui


def office_accessible(pid):
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        try:
            app = desktop.getChildAtIndex(index)
            if app and app.get_process_id() == pid:
                return app
        except Exception:
            continue
    return None


def capture(display, wid, path):
    # Crop the visible X root to the actual application allocation. Capturing an
    # offscreen window drawable can leave unpainted rectangles in GTK3 output.
    tabs.xdo(display, "mousemove", "2999", "1799")
    time.sleep(0.3)
    size = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", wid],
                                   env=dict(os.environ, DISPLAY=display), text=True)
    width = re.search(r"WIDTH=(\d+)", size).group(1)
    height = re.search(r"HEIGHT=(\d+)", size).group(1)
    subprocess.run(["import", "-display", display, "-window", "root", "-crop",
                    f"{width}x{height}+0+0", str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--display", default=":91")
    parser.add_argument("--variant", choices=("baseline", "hst"), required=True)
    parser.add_argument("--mode", choices=("light", "dark"), required=True)
    parser.add_argument("--scale", type=int, choices=(1, 2), required=True)
    parser.add_argument("--legacy-binary", action="store_true")
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--surfaces", action="store_true", help="also capture Writer sidebar, menus, dialog and Start Center")
    args = parser.parse_args()
    os.environ["DISPLAY"] = args.display
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        user = os.environ.get("HST_BUILD_USER", "hstbuild")
        for path in (args.out, args.work):
            subprocess.run(["chown", "-R", user, str(path)], check=True)
        os.execvp("runuser", ["runuser", "-u", user, "--", "env", f"HST_BUILD_USER={user}",
                              f"DISPLAY={args.display}",
                              "dbus-run-session", "--", sys.executable, *sys.argv])
    hst_gui.setup_uno(str(args.instdir))
    # Pin this run's accessibility bus; parallel Xvfb runs must never pick up
    # another display's cached AT-SPI address from the user's runtime directory.
    bus = subprocess.check_output(["dbus-send", "--session", "--print-reply",
                                   "--dest=org.a11y.Bus", "/org/a11y/bus",
                                   "org.a11y.Bus.GetAddress"], text=True)
    os.environ["AT_SPI_BUS_ADDRESS"] = re.search(r'string "([^"]+)"', bus).group(1)
    tag = f"{args.variant}-{args.mode}-{args.scale * 100}"
    config = [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2" if args.mode == "dark" else "1"),
              ("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]
    if args.variant == "hst" and args.legacy_binary:
        config.append(("/org.openoffice.Office.Common/Misc", "SymbolStyle", "hst_dark" if args.mode == "dark" else "hst"))
    rows = []
    for app in args.apps.split(","):
        subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        office = hst_gui.Office(str(args.instdir), str(args.work / f"{tag}-{app}"), 22100 + int(args.display[1:]),
                               display=args.display, extra_args=["--" + app], nodefault=False, config=config,
                               env={"GTK_THEME": "Adwaita:dark" if args.mode == "dark" else "Adwaita",
                                    "GDK_SCALE": str(args.scale), "GDK_DPI_SCALE": "1"})
        try:
            office.start()
            tabs.office_app = lambda: office_accessible(office.pid)
            time.sleep(2)
            window = next(w for w, n in hst_gui.toplevels(args.display, office.pid) if tabs.NAMES[app] in n)
            tabs.xdo(args.display, "windowmove", window, "0", "0")
            tabs.xdo(args.display, "windowsize", window, str(1485 * args.scale), str(900 * args.scale))
            time.sleep(2)
            for index, name in enumerate(APP_TABS[app]):
                found = next(t for t in tabs.ribbon_tabs() if t[0] == name)
                # Invoke the tab list's accessible selection, avoiding backend-specific
                # conversions between AT-SPI logical coordinates and X11 pixels.
                if not found[2]:
                    found[3].parent.querySelection().selectChild(found[3].getIndexInParent())
                time.sleep(1)
                if tabs.selected() != [name]:
                    raise RuntimeError(f"Tab click failed: {name}: {tabs.selected()}")
                geometry = tabs.geometry()
                shot = f"{tag}-{app}-{index:02d}.png"
                capture(args.display, window, args.out / shot)
                row = {"app": app, "tab": name, "shot": shot, "geometry_atspi": geometry,
                       "selected": tabs.selected(), "scale": args.scale,
                       "legacy_explicit_theme": args.variant == "hst" and args.legacy_binary}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            if args.surfaces and app == "writer":
                surfaces(tabs, office, window, args, tag)
        finally:
            office.stop()
    if args.surfaces:
        center = hst_gui.Office(str(args.instdir), str(args.work / f"{tag}-start-center"),
                               22100 + int(args.display[1:]), display=args.display, nodefault=False,
                               config=config, env={"GTK_THEME": "Adwaita:dark" if args.mode == "dark" else "Adwaita",
                                                   "GDK_SCALE": str(args.scale), "GDK_DPI_SCALE": "1"})
        try:
            center.start()
            window = next(w for w, n in hst_gui.toplevels(args.display, center.pid) if n == "HST Office")
            tabs.xdo(args.display, "windowmove", window, "0", "0")
            tabs.xdo(args.display, "windowsize", window, str(1485 * args.scale), str(900 * args.scale))
            time.sleep(2)
            capture(args.display, window, args.out / f"{tag}-start-center.png")
        finally:
            center.stop()
    suffix = "-surfaces" if args.surfaces else "-subset" if args.apps != "writer,calc,impress" else ""
    (args.out / f"{tag}{suffix}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
