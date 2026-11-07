# SPDX-License-Identifier: AGPL-3.0-only
"""The tab row's feature search box is reachable by assistive technology (gtk3, vi_VN, AT-SPI).

Usage: python3 tests/runtime/check-ribbon-tab-search-a11y.py [--instdir DIR] [--display :71] [--out DIR]

In Writer, the ribbon's page tab list (the tab control) has, after its page tabs, a push button
"Tìm tính năng… (Alt+Q)" with one action, "press"; doing it opens the feature search popup (a new
top-level window of the office). Exit 1 when a check fails.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ribbon_tabs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-ribbon-tabs.py"))
tabs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tabs)

NAME = "Tìm tính năng"


def search_box():
    """(tab list node, search button node) of the ribbon, or (None, None)."""
    for node in tabs.walk(tabs.office_app()):
        try:
            if node.getRoleName() != "page tab list":
                continue
            for index in range(node.childCount):
                child = node.getChildAtIndex(index)
                if child is not None and child.getRoleName() == "push button" and (child.name or "").startswith(NAME):
                    return node, child
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
    return None, None


def window_count(display, pid):
    return len(hst_gui.toplevels(display, pid))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-tab-search-a11y"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office, _wid = tabs.start(args.instdir, "writer", args, "writer", 7460)
    try:
        tab_list, box = search_box()
        tabs.record("search box is a child of the ribbon's page tab list", box is not None,
                    (box.name if box else None, tab_list.childCount if tab_list else None))
        if box is None:
            return finish()
        pages = sum(1 for i in range(tab_list.childCount) if tab_list.getChildAtIndex(i).getRoleName() == "page tab")
        index = next(i for i in range(tab_list.childCount) if tab_list.getChildAtIndex(i) == box)
        tabs.record("search box follows the page tabs", index >= pages, (index, pages))
        action = box.queryAction()
        names = [action.getName(i) for i in range(action.nActions)]
        tabs.record("search box has the action 'press'", "press" in names, names)
        windows = window_count(args.display, office.pid)
        done = action.doAction(names.index("press")) if "press" in names else False
        time.sleep(3)
        office.screenshot(os.path.join(args.out, "search-open.png"))
        after = window_count(args.display, office.pid)
        tabs.record("pressing it opens the feature search (a popup window)", bool(done) and after > windows,
                    (done, windows, after))
        tabs.xdo(args.display, "key", "Escape")
    finally:
        office.stop()
    return finish()


def finish():
    failed = sum(r["status"] != "PASS" for r in tabs.ROWS)
    print(f"{len(tabs.ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
