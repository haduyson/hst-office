# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Collects the v3 ribbon's layout dumps and screenshots from the real app, every main tab at several window widths.

Usage: python3 tests/runtime/collect-ribbon-v3-dumps.py --instdir DIR --out DIR [--display :283]
           [--apps writer,calc,impress,draw] [--widths 1280,1366,1470,1536,1920,2560] [--height 900] [--no-shots]
           [--contextual 1920]

The office runs with HST_RIBBON_DUMP_LAYOUT=<out>/dumps/<app>-w<width> (hst-ribbon-v3-layout.patch: every tab page
writes <box>-<logical width>.json when its banner is placed), one fresh profile per app. For every width the window
is resized, then every ribbon tab but "Tệp tin" is opened through AT-SPI and, unless --no-shots, the window's top
(the ribbon) is saved as <out>/shots/<app>-w<width>-<tab index>.png. Check the dumps with check-ribbon-v3-dumps.py.
With --contextual WIDTHS a table, a picture, a shape and a chart (ribbon_contextual_objects.py) are selected in turn at
those widths and every contextual tab they show is opened and dumped (<out>/dumps/<app>-ctx-<object>-w<width>/);
after a command on the object (KEEP_COMMANDS) the contextual tab must still be the current one (bug: the ribbon went
back to Trang đầu), written to <out>/contextual.json.
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
from ribbon_contextual_objects import make_objects, park  # noqa: E402

PORTS = {"writer": 7631, "calc": 7632, "impress": 7633, "draw": 7634}  # one fixed UNO port per app
RIBBON_HEIGHT = 200  # px of the window's top kept in a shot: title, tab row, ribbon body, a little document
# a command run on the selected object from its contextual tab, per app and object (the tab must stay current)
KEEP_COMMANDS = {
    ("writer", "picture"): ".uno:GraphicFilterInvert", ("writer", "table"): ".uno:InsertRowsAfter",
    ("writer", "shape"): ".uno:FillShadow", ("calc", "picture"): ".uno:GraphicFilterInvert",
    ("calc", "shape"): ".uno:FillShadow", ("impress", "picture"): ".uno:GraphicFilterInvert",
    ("impress", "shape"): ".uno:FillShadow", ("impress", "table"): ".uno:InsertRowsAfter",
    ("draw", "picture"): ".uno:GraphicFilterInvert", ("draw", "shape"): ".uno:FillShadow",
}


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


def settle(live, fallback, longest=10.0):
    """Waits until the ribbon's layout settles: its fit pass count (<live>/layout-passes, hst-ribbon-v3-layout.patch)
    unchanged for a second, at most LONGEST seconds; a build without the count: FALLBACK seconds. A dump taken
    sooner could catch a layout pass half done (every group large past the banner while the fit was redone)."""
    path = os.path.join(live, "layout-passes")
    if not os.path.exists(path):
        time.sleep(fallback)
        return
    end, last, stable_since = time.monotonic() + longest, None, time.monotonic()
    while time.monotonic() < end:
        try:
            with open(path, encoding="ascii") as handle:
                now = handle.read().strip()
        except OSError:
            now = None
        if now != last:
            last, stable_since = now, time.monotonic()
        elif time.monotonic() - stable_since >= 1.0:
            return
        time.sleep(0.2)


def move_dumps(live, target):
    os.makedirs(target, exist_ok=True)
    for name in os.listdir(live):
        if name != "layout-passes":  # the office's running count, not a dump
            os.replace(os.path.join(live, name), os.path.join(target, name))
    return len(os.listdir(target))


def dispatch(office, frame, command):
    from com.sun.star.util import URL
    url = URL()
    url.Complete = command
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    target = frame.queryDispatch(url, "", 0)
    if target is not None:
        target.dispatch(url, ())
    return target is not None


def collect_contextual(args, app, office, window, live, root):
    """Every contextual tab of every object at the --contextual widths; [(object, width, tab, kept)]."""
    doc = office.desktop().getCurrentComponent()
    image = "file://" + os.path.join(args.instdir, "program/about.png")
    if not os.path.exists(image[7:]):
        image = "file://" + os.path.join(args.instdir, "share/extensions/hst-vietnamese-tools/banners/aios@1x.png")
    objects = make_objects(app, doc, image)
    objects.pop("pivot", None)
    objects.pop("header", None)
    rows = []
    try:
        for width in args.contextual:
            gui.xdo(args.display, "windowsize", window, str(width), str(args.height))
            settle(live, 3)
            park(app, doc, office)
            plain = set(gui.visible_names())
            for kind, target in sorted(objects.items(), key=lambda item: item[0] == "chart"):
                doc.CurrentController.select(target)
                settle(live, 2)
                tabs = [n for n in gui.visible_names() if n and n not in plain]
                for index, name in enumerate(tabs):
                    if not gui.open_tab(args.display, name):
                        continue
                    settle(live, 1.5)
                    if args.shots:
                        shot = os.path.join(args.out, "shots", f"{app}-ctx-{kind}-w{width}-{index}.png")
                        os.makedirs(os.path.dirname(shot), exist_ok=True)
                        subprocess.run(["import", "-display", args.display, "-window", "root", "-crop",
                                        f"{width}x{RIBBON_HEIGHT}+0+0", "+repage", shot], check=False)
                    kept = None
                    command = KEEP_COMMANDS.get((app, kind))
                    if index == 0 and command and kind != "chart":
                        if dispatch(office, doc.CurrentController.Frame, command):
                            time.sleep(2)
                            kept = gui.selected() == [name]
                    rows.append({"object": kind, "width": width, "tab": name, "command": command if kept is not None
                                 else None, "kept": kept})
                    print(f"{app} {kind} w{width} {name}: kept={kept}", flush=True)
                move_dumps(live, os.path.join(root, f"{app}-ctx-{kind}-w{width}"))
                park(app, doc, office)
                time.sleep(1)
    finally:
        try:
            doc.setModified(False)
        except Exception:  # noqa: BLE001 - the document may be gone already
            pass
    return rows


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
            settle(live, 3)
            names = [n for n in gui.visible_names() if n and n != "Tệp tin"]
            if not names and args.shots:  # no ribbon tab found: keep the screen to see why
                shot = os.path.join(args.out, "shots", f"{app}-w{width}-notabs.png")
                os.makedirs(os.path.dirname(shot), exist_ok=True)
                subprocess.run(["import", "-display", args.display, "-window", "root", shot], check=False)
            for index, name in enumerate(names):
                if not gui.open_tab(args.display, name):
                    print(f"{app} w{width}: cannot open {name}", flush=True)
                    continue
                settle(live, 1.5)
                if args.shots:
                    shot = os.path.join(args.out, "shots", f"{app}-w{width}-{index:02d}.png")
                    os.makedirs(os.path.dirname(shot), exist_ok=True)
                    subprocess.run(["import", "-display", args.display, "-window", "root", "-crop",
                                    f"{width}x{RIBBON_HEIGHT}+0+0", "+repage", shot], check=False)
            count = move_dumps(live, os.path.join(root, f"{app}-w{width}"))
            seen.append((width, names))
            print(f"{app} w{width}: {len(names)} tabs, {count} dumps", flush=True)
        if args.contextual:
            seen.append(("contextual", collect_contextual(args, app, office, window, live, root)))
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
    parser.add_argument("--contextual", default="", help="widths of the contextual pass (empty: none)")
    args = parser.parse_args()
    args.widths = [int(w) for w in args.widths.split(",") if w]
    args.contextual = [int(w) for w in args.contextual.split(",") if w]
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
