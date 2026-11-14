# SPDX-License-Identifier: AGPL-3.0-only
"""KeyTips and shortcuts of the familiar office suite on a real GUI (gtk3, vi_VN): the key matrix of 1.0.2.

Usage: python3 tests/runtime/check-keytips-office-parity.py [--instdir DIR] [--display :73] [--shots DIR]
       [--apps writer,calc,impress,draw]
The X display must already run. Per app: Alt shows the tab letters of data/ribbon/keytips-office-parity.json on the
tabs; every tab of the table opens with its letter (a screenshot of its command letters); the tab names carry no
underlined access key; a few command letters of the suite run their command (Alt R C comment, Alt A SA sort, Alt N SI
new slide); the shortcuts of hst-msoffice-shortcuts-parity.patch do what the suite does. Writes evidence.json.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402
from keytips_parity_matrix import ROWS, command_letters, focus, key, letters, record, shortcut_matrix, tips  # noqa: E402,E501

TABLE = os.path.join(hst_gui.ROOT, "data", "ribbon", "keytips-office-parity.json")


def tab_matrix(office, args, app, table, label):
    focus(args)
    key(args, "Alt_L")
    shown, row = tips(), {n: b for n, b, _s, _n in gui.ribbon_tabs()}
    want = table["tabs"][app]
    record(label("Alt shows the suite's tab letters"), all(v in shown for v in want.values()), sorted(shown))
    record(label("no tab name has an underlined access key"), not any("_" in n or "~" in n for n in row), sorted(row))
    key(args, "Escape", "Escape")
    for tab, tip in want.items():
        if tab == "FileLabel":
            continue
        focus(args)
        key(args, "Alt_L")
        letters(args, tip)
        now = tips()
        record(label(f"Alt, {tip} opens {gui.selected()} with command letters"), len(now) > 2, sorted(now))
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"{app}-{tip}-{tab}.png"))
        key(args, "Escape", "Escape", "Escape")


def check_app(app, args, port, table):
    office, _wid, _w = gui.start(args.instdir, app, args.display, os.path.join(args.out, app), port)
    label = lambda what: f"[{app}] {what}"  # noqa: E731
    try:
        doc = office.desktop().getCurrentComponent()
        tab_matrix(office, args, app, table, label)
        command_letters(office, args, app, doc, label)
        shortcut_matrix(office, args, app, doc, label)
        doc.setModified(False)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":73")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/keytips-office-parity"))
    parser.add_argument("--shots")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    with open(TABLE, encoding="utf-8") as handle:
        table = json.load(handle)
    for index, app in enumerate(args.apps.split(",")):
        try:
            check_app(app, args, 7480 + index, table)
        except Exception as error:  # noqa: BLE001 - report and go on with the next app
            record(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
