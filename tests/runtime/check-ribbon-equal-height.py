#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""One ribbon height and one caption row in HST Writer, Sheets, Slides and Draw (gap list G06,
hst-ribbon-equal-height.patch), on gtk3 under Xvfb.

Per app and width (1366, 1485, 1920), on the first tab after "Tệp tin": the ribbon's tab control height, the top of
the document tab strip and the y of the group captions. Checks: the tab control height and the document strip's top
are the same in every app at every width (±1 px), and every caption lies within ±2 px of the shared caption row.
Usage: python3 tests/runtime/check-ribbon-equal-height.py --instdir DIR [--display :71] [--out DIR]
Runs as the build user under dbus-run-session (AT-SPI). Exit 1 on any FAIL.
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

APPS = ("writer", "calc", "impress", "draw")
WIDTHS = (1366, 1485, 1920)
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:300]}", flush=True)


def measure():
    """(tab control height, caption y values, document strip top) of the ribbon now on screen."""
    heights, captions = [], []
    for node in gui.walk(gui.office_app()):
        try:
            role, box = node.getRoleName(), gui.extents(node)
            if role == "page tab list" and gui.showing(node) and box[1] < 60:
                heights.append(box[3])
            elif role == "label" and node.name and gui.showing(node) and 100 < box[1] < 200 and box[3] < 30:
                captions.append(box[1])
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
    return (max(heights) if heights else None), sorted(set(captions)), gui.geometry()[1]


def measure_app(app, args, port):
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "office-" + app), port, display=args.display,
                            extra_args=["--" + app], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    found = {}
    try:
        time.sleep(10)
        office.close_welcome()
        wid = next(w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES[app] in n)
        gui.xdo(args.display, "windowmove", wid, "0", "0")
        for width in WIDTHS:
            gui.xdo(args.display, "windowsize", wid, str(width), "900")
            time.sleep(4)
            found[width] = measure()
            print(f"[{app} {width}] {found[width]}", flush=True)
    finally:
        office.stop()
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-equal-height"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    data = {app: measure_app(app, args, 7400 + 2 * i) for i, app in enumerate(APPS)}
    for width in WIDTHS:
        heights = {app: data[app][width][0] for app in APPS}
        strips = {app: data[app][width][2] for app in APPS}
        known = [h for h in heights.values() if h]
        record(f"[{width}] one tab control height in the 4 apps", len(known) == len(APPS)
               and max(known) - min(known) <= 1, heights)
        tops = [t for t in strips.values() if t is not None]
        record(f"[{width}] the document strip starts at one y in the 4 apps", len(tops) == len(APPS)
               and max(tops) - min(tops) <= 1, strips)
        captions = {app: data[app][width][1] for app in APPS}
        every = sorted(y for ys in captions.values() for y in ys)
        row = every[len(every) // 2] if every else None
        stray = {app: [y for y in ys if abs(y - row) > 2] for app, ys in captions.items()} if row else captions
        record(f"[{width}] the group captions share one row (y {row} ±2)", bool(every) and not any(stray.values()),
               stray)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"measured": {a: {str(w): v for w, v in d.items()} for a, d in data.items()}, "rows": ROWS},
                  handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
