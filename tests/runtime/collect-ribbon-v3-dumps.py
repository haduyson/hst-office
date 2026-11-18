# SPDX-License-Identifier: AGPL-3.0-only
"""Collects the v3 ribbon's layout dumps and screenshots from the real app, every main tab at several window widths.

Usage: python3 tests/runtime/collect-ribbon-v3-dumps.py --instdir DIR --out DIR [--display :283]
           [--apps writer,calc,impress,draw] [--widths 1280,1366,1470,1536,1920,2560] [--height 900] [--no-shots]

The office runs with HST_RIBBON_DUMP_LAYOUT=<out>/dumps/<app>-w<width> (hst-ribbon-v3-layout.patch: every tab page
writes <box>-<logical width>.json when its banner is placed), one fresh profile per app. For every width the window
is resized, then every ribbon tab but "Tệp tin" is opened through AT-SPI and, unless --no-shots, the window's top
(the ribbon) is saved as <out>/shots/<app>-w<width>-<tab index>.png. Check the dumps with check-ribbon-v3-dumps.py.
The X display (wide enough for the widest window) must already run; this script never starts or stops it.
Runs as the build user like the other GUI checks (dbus-run-session, AT-SPI).
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

PORTS = {"writer": 7631, "calc": 7632, "impress": 7633, "draw": 7634}  # one fixed UNO port per app
RIBBON_HEIGHT = 200  # px of the window's top kept in a shot: title, tab row, ribbon body, a little document


def start(instdir, app, display, work, dumps):
    subprocess.run(["xprop", "-display", display, "-root", "-remove", "AT_SPI_BUS"], check=False,
                   stderr=subprocess.DEVNULL)
    office = hst_gui.Office(instdir, work, PORTS[app], display=display, extra_args=[f"--{app}"], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")],
                            env={"HST_RIBBON_DUMP_LAYOUT": dumps, "HST_RIBBON_DUMP_APP": app})
    office.start()
    time.sleep(8)
    windows = [w for w, n in hst_gui.toplevels(display, office.pid) if gui.NAMES[app] in n]
    if not windows:
        office.stop()
        raise RuntimeError(f"{app}: no window")
    gui.xdo(display, "windowmove", windows[0], "0", "0")
    return office, windows[0]


def collect_app(args, app):
    """[(width, tab names)] of one app; the dumps go to <out>/dumps/<app>-w<width>/."""
    root = os.path.join(args.out, "dumps")
    os.makedirs(root, exist_ok=True)
    # the office writes into one directory; the files are moved per width after each pass
    live = os.path.join(root, f"{app}-live")
    os.makedirs(live, exist_ok=True)
    office, window = start(args.instdir, app, args.display, os.path.join(args.out, "work", app), live)
    seen = []
    try:
        for width in args.widths:
            gui.xdo(args.display, "windowsize", window, str(width), str(args.height))
            time.sleep(3)
            names = [n for n in gui.visible_names() if n and n != "Tệp tin"]
            for index, name in enumerate(names):
                if not gui.open_tab(args.display, name):
                    print(f"{app} w{width}: cannot open {name}", flush=True)
                    continue
                time.sleep(1.5)
                if args.shots:
                    shot = os.path.join(args.out, "shots", f"{app}-w{width}-{index:02d}.png")
                    os.makedirs(os.path.dirname(shot), exist_ok=True)
                    subprocess.run(["import", "-display", args.display, "-window", "root", "-crop",
                                    f"{width}x{RIBBON_HEIGHT}+0+0", "+repage", shot], check=False)
            target = os.path.join(root, f"{app}-w{width}")
            os.makedirs(target, exist_ok=True)
            for name in os.listdir(live):
                os.replace(os.path.join(live, name), os.path.join(target, name))
            seen.append((width, names))
            print(f"{app} w{width}: {len(names)} tabs, {len(os.listdir(target))} dumps", flush=True)
    finally:
        office.stop()
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":283")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--widths", default="1280,1366,1470,1536,1920,2560")
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--no-shots", dest="shots", action="store_false")
    args = parser.parse_args()
    args.widths = [int(w) for w in args.widths.split(",")]
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "NO_AT_BRIDGE=0",
                              "GTK_MODULES=gail:atk-bridge", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    hst_gui.setup_uno(args.instdir)
    summary = {}
    for app in args.apps.split(","):
        try:
            summary[app] = collect_app(args, app)
        except Exception as error:  # noqa: BLE001 - one app's failure must not lose the others' dumps
            print(f"{app}: {error}", flush=True)
            summary[app] = f"error: {error}"
    with open(os.path.join(args.out, "collected.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
