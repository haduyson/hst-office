# SPDX-License-Identifier: AGPL-3.0-only
"""Check on a real GTK GUI that the native menu bar, now built only when shown, is complete whenever it is shown.

Usage: python3 tests/runtime/check-gtk-menubar-lazy-build.py [--instdir DIR] [--display :72] [--file X.xlsx]
The X display must already run. hst-gtk-menubar-lazy-build.patch defers the GTK menu bar (model and widgets) to an
idle that builds only a menu bar still shown, so under the Tabbed UI a spreadsheet opens and closes without building
it. Checked through AT-SPI ("menu bar" of the office window, its menus, the items of the first menu):
  - Tabbed UI: no menu bar after the open; .uno:Menubar shows a complete one (>= 10 menus, File menu >= 10 items),
    a second .uno:Menubar hides it; File - Close leaves the Start Center with its own menu bar;
  - standard toolbars: the menu bar is there, complete, right after the open (built at the first idle).
Also prints open and close times. Writes evidence.json. Runs as the build user under dbus-run-session (AT-SPI).
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

ROWS = []
CALC_MODE = "/org.openoffice.Office.UI.ToolbarMode/Applications/org.openoffice.Office.UI.ToolbarMode:Application['Calc']"


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)


def menubar(timeout=6.0):
    """(menu names, items of the first menu) of the showing menu bar of the office, or None."""
    import pyatspi
    deadline = time.time() + timeout
    while True:
        app = gui.office_app()
        for frame in [app.getChildAtIndex(i) for i in range(app.childCount)] if app else []:
            stack = [frame]
            while stack:
                node = stack.pop()
                try:
                    state = node.getState()
                    if (node.getRoleName() == "menu bar" and state.contains(pyatspi.STATE_SHOWING)
                            and state.contains(pyatspi.STATE_VISIBLE) and gui.extents(node)[3] > 5):
                        menus = [node.getChildAtIndex(i) for i in range(node.childCount)]
                        return [m.name for m in menus], (menus[0].childCount if menus else 0)
                    if node.getRoleName() in gui.SKIP or len(stack) > 2000:
                        continue
                    stack.extend(node.getChildAtIndex(i) for i in range(min(node.childCount, 200)))
                except Exception:  # noqa: BLE001 - widgets come and go
                    continue
        if time.time() >= deadline:
            return None
        time.sleep(0.5)


def complete(found, menus=10, items=10):
    return found is not None and len(found[0]) >= menus and found[1] >= items


def open_file(office, path):
    start = time.monotonic()
    doc = office.load("file://" + path if path else "private:factory/scalc")
    took = time.monotonic() - start
    time.sleep(2)
    return doc, doc.getCurrentController().getFrame(), took


def tabbed(args):
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "tabbed"), 7431, display=args.display).start()
    try:
        doc, frame, took = open_file(office, args.file)
        record("tabbed: open time (s)", True, round(took, 2))
        record("tabbed: no menu bar after the open", menubar(2) is None, menubar(0.1))
        office.dispatch(frame, ".uno:Menubar")
        shown = menubar()
        record("tabbed: .uno:Menubar shows a complete menu bar", complete(shown), shown)
        office.dispatch(frame, ".uno:Menubar")
        record("tabbed: a second .uno:Menubar hides it", menubar(2) is None)
        start = time.monotonic()
        office.dispatch(frame, ".uno:CloseDoc")
        record("tabbed: close time (s)", True, round(time.monotonic() - start, 2))
        start_center = menubar()
        record("tabbed: the Start Center has its menu bar", complete(start_center, 3, 3), start_center)
    finally:
        office.stop()


def standard(args):
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "standard"), 7432, display=args.display,
                            config=[(CALC_MODE, "Active", "Default")]).start()
    try:
        _doc, _frame, took = open_file(office, args.file)
        shown = menubar()
        record("standard toolbars: complete menu bar after the open", complete(shown), (round(took, 2), shown))
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":72")
    parser.add_argument("--file", help="a workbook to open (default: a new spreadsheet)")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/gtk-menubar-lazy-build"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    args.file = args.file and os.path.abspath(args.file)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", HST_VCLPLUGIN="gtk3")
    hst_gui.setup_uno(args.instdir)
    for phase in (tabbed, standard):
        try:
            phase(args)
        except Exception as error:  # noqa: BLE001
            record(f"{phase.__name__}: crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
