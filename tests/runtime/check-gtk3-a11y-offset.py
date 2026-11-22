# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (c) HASON TECH. HST Office.
"""Accessible objects of a gtk3 window with a native menu bar report their real screen position.

Usage: python3 tests/runtime/check-gtk3-a11y-offset.py --instdir DIR [--display :396] [--out DIR]

The X display must already run (e.g. `Xvfb :396 -screen 0 1366x768x24`); the check never starts or stops it. Run as
root it re-runs itself as the build user under dbus-run-session (own AT-SPI bus).

With the native GTK menu bar shown, the VCL content of a window starts below the menu bar, but the frame geometry
took the toplevel's position from the configure event, so every VCL accessible object (root pane, Start Center,
document, toolbars) was reported one menu bar height (27 px) too high until the first mouse event; Orca, magnifiers
and AT-SPI test drivers then point above the object. For each office window the check compares, through AT-SPI, the
screen y of the VCL root pane with the y of the GTK container that holds it (their difference was 27, it must be
0), and requires the root pane to start at the bottom of a showing menu bar. Cases:
- the Start Center (menu bar shown, built on an idle after the window appeared);
- a Writer document whose menu bar is switched on with .uno:Menubar after the window shows, then off again
  (the content moves inside the toplevel without a configure event).
Writes evidence.json; exit 1 on a failure.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:200]}", flush=True)


def extents(node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    return [box.x, box.y, box.width, box.height]


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if app is not None and "office" in (app.name or "").lower():
            return app
    return None


def showing_menu_bars(node, found, depth=0):
    import pyatspi
    try:
        if node.getRoleName() == "menu bar":
            state = node.getState()
            box = extents(node)
            if state.contains(pyatspi.STATE_SHOWING) and box[3] > 5:
                found.append(box)
            return
        if depth > 6 or node.getRoleName() == "root pane":
            return
        for index in range(min(node.childCount, 50)):
            showing_menu_bars(node.getChildAtIndex(index), found, depth + 1)
    except Exception:  # noqa: BLE001 - widgets come and go
        pass


def root_panes(node, frame_name, out, depth=0):
    """[(frame name, root pane box, GTK parent box)] below an office frame."""
    try:
        if node.getRoleName() == "root pane":
            out.append((frame_name, extents(node), extents(node.parent)))
            return
        if depth > 6:
            return
        for index in range(min(node.childCount, 50)):
            root_panes(node.getChildAtIndex(index), frame_name, out, depth + 1)
    except Exception:  # noqa: BLE001
        pass


def measure():
    """[{title, root_pane, gtk_container, menu_bars, offset_y}] of every office frame."""
    rows = []
    app = office_app()
    for index in range(app.childCount if app else 0):
        frame = app.getChildAtIndex(index)
        panes, bars = [], []
        root_panes(frame, frame.name, panes)
        showing_menu_bars(frame, bars)
        for title, pane, container in panes:
            rows.append({"title": title, "root_pane": pane, "gtk_container": container, "menu_bars": bars,
                         "offset_y": container[1] - pane[1]})
    return rows


def judge(case, title_part, want_menu_bar, timeout=20.0):
    """Wait until the frame whose title contains title_part shows (or hides) its menu bar, then check it."""
    deadline = time.time() + timeout
    while True:
        rows = [r for r in measure() if title_part in r["title"]]
        settled = rows and all(bool(r["menu_bars"]) == want_menu_bar for r in rows)
        if settled or time.time() >= deadline:
            break
        time.sleep(0.5)
    if not rows:
        record(f"{case}: frame found", False, f"no office frame titled *{title_part}*")
        return
    for row in rows:
        detail = json.dumps(row, ensure_ascii=False)
        record(f"{case}: menu bar {'shown' if want_menu_bar else 'hidden'}",
               bool(row["menu_bars"]) == want_menu_bar, detail)
        record(f"{case}: root pane at its GTK container", row["offset_y"] == 0, detail)
        if row["menu_bars"]:
            bottom = max(bar[1] + bar[3] for bar in row["menu_bars"])
            record(f"{case}: root pane starts below the menu bar", row["root_pane"][1] >= bottom, detail)


def dispatch(office, frame, command):
    helper = office.service("com.sun.star.frame.DispatchHelper")
    helper.executeDispatch(frame, command, "", 0, ())


def run(args):
    workdir = args.workdir or tempfile.mkdtemp(prefix="hst-a11y-offset-")
    office = hst_gui.Office(args.instdir, workdir, hst_gui.free_port(), display=args.display, lang="en_US.UTF-8",
                            nodefault=False)
    try:
        office.start()
        time.sleep(4)
        start_title = office.desktop().getFrames().getByIndex(0).getTitle()
        judge("Start Center", start_title, want_menu_bar=True)

        doc = office.desktop().loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        frame = doc.getCurrentController().getFrame()
        time.sleep(4)
        title = frame.getTitle()
        shown = any(r["menu_bars"] for r in measure() if title in r["title"])
        if not shown:  # the Tabbed UI hides the menu bar of documents: switch it on after the window showed
            dispatch(office, frame, ".uno:Menubar")
            judge("Writer, menu bar switched on", title, want_menu_bar=True)
            dispatch(office, frame, ".uno:Menubar")
            judge("Writer, menu bar switched off", title, want_menu_bar=False)
        else:
            judge("Writer, menu bar shown", title, want_menu_bar=True)
        doc.close(True)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":396")
    parser.add_argument("--workdir")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/gtk3-a11y-offset"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", HST_VCLPLUGIN="gtk3")
    hst_gui.setup_uno(args.instdir)
    try:
        run(args)
    except Exception as error:  # noqa: BLE001
        record("run", False, repr(error))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed or not ROWS else 0


if __name__ == "__main__":
    sys.exit(main())
