#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Commands keep their labels from 1485 px up, except in formatting groups (gap list G10), on gtk3 under Xvfb.

Per app (HST Writer, Sheets, Slides, Draw), tab and width (1920, 1485): every button of the ribbon band that shows only
its icon (ICON_MAX px wide or less) must belong to a formatting group (FORMATTING: bold, italic, alignment, lists,
number formats) or to a group shown as its "Caption ▾" button, or be bare by design in the reference suite too (BARE_GROUPS,
BARE_COMMANDS: Developer controls, grid toggles, shape combine, record navigation, A→Z/Z→A, View's Show toggles
and the Zoom group's small buttons). Gallery arrows and the group launchers (↘) are not
commands of the band. The reference suite labels almost every command at these widths.
Usage: python3 tests/runtime/check-ribbon-labels.py --instdir DIR [--display :71] [--apps writer,calc] [--out DIR]
Runs as the build user under dbus-run-session (AT-SPI). Writes <out>/results.json; exit 1 on any FAIL.
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
from ribbon_home_tools_gui import group_range  # noqa: E402

FORMATTING = {"Phông chữ", "Đoạn văn", "Căn chỉnh", "Số"}  # bare formatting icons are allowed (G10)
# bare by design in the reference suite too (coordinator 15/11/2026): whole groups, and single commands
BARE_GROUPS = {"Nhà phát triển", "Lưới", "Gộp hình",  # Developer controls, grid/snap toggles, shape combine
               # View: the Show toggles, and the Zoom group's small buttons beside its large labelled ones
               # (Zoom, 100%, Zoom to Selection, Fit to Window keep their labels at every width; owner, G10)
               "Hiện", "Phóng to/thu nhỏ"}
BARE_COMMANDS = {"Bản ghi đầu", "Bản ghi trước", "Bản ghi sau", "Bản ghi cuối",  # record navigation ◀ ▶
                 "Sắp xếp tăng dần", "Sắp xếp giảm dần",  # Sheets' A→Z, Z→A beside the labelled Sort
                 # Fontwork's format toggles beside its labelled gallery: formatting commands (G10)
                 "Dạng chữ nghệ thuật", "Chữ nghệ thuật cùng độ cao chữ", "Căn lề chữ nghệ thuật",
                 "Giãn cách ký tự trong chữ nghệ thuật"}
WIDTHS = (1920, 1485)
ICON_MAX = 40  # an icon with its button padding; with its label a button is wider
SMALL_MAX = 45  # a small button is one row of a group; a large one (icon over label) is taller
BAND = (44, 135)  # the buttons of a tab page, above the caption row
ROLES = ("push button", "toggle button", "push button menu", "menu button")
SKIP_TABS = ("Tệp tin",)
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:300]}", flush=True)


def scan():
    """Captions [(name, box)] and the bare icons [(name, box)] of the tab page on screen."""
    captions, icons = [], []
    for name, role, box, _node in gui.ribbon_nodes(ROLES + ("label",), band=200):
        if role == "label" and name and 120 < box[1] < 175 and box[3] < 30:
            captions.append((name, box))
        # a small button (one row of the group) as narrow as its icon: a large button's label is below its icon,
        # so a short label ("Ảnh") leaves it narrow too
        elif role != "label" and name and BAND[0] < box[1] < BAND[1] and 20 <= box[2] <= ICON_MAX \
                and 20 <= box[3] < SMALL_MAX:
            icons.append((name.replace("\n", " "), box))
    return captions, icons


def check_tab(app, width, tab):
    captions, icons = scan()
    if not captions:
        return
    ranges = {caption: group_range(captions, caption) for caption, _box in captions}
    bare = {}
    for name, box in icons:
        # a caption spans its group's width: the button's group is the caption above which it stands; between two
        # captions, the nearer half
        group = next((c for c, b in captions if b[0] <= box[0] + box[2] // 2 < b[0] + b[2]), None) \
            or next((c for c, (left, right) in ranges.items() if left <= box[0] < right), "?")
        if group not in FORMATTING | BARE_GROUPS and name not in BARE_COMMANDS:
            bare.setdefault(group, []).append(name)
    record(f"[{app} {width}] {tab}: commands outside formatting groups are labelled", not bare, bare)


def check_app(app, args, port):
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "office-" + app), port, display=args.display,
                            extra_args=["--" + app], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    try:
        time.sleep(10)
        office.close_welcome()
        wid = next(w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES[app] in n)
        gui.xdo(args.display, "windowmove", wid, "0", "0")
        for width in WIDTHS:
            gui.xdo(args.display, "windowsize", wid, str(width), "900")
            time.sleep(4)
            for tab in [t for t in gui.visible_names() if t not in SKIP_TABS]:
                gui.open_tab(args.display, tab)
                time.sleep(2)
                check_tab(app, width, tab)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":71")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-labels"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    for index, app in enumerate(args.apps.split(",")):
        try:
            check_app(app, args, 7500 + 2 * index)
        except Exception as error:  # noqa: BLE001 - one app's crash must not hide the others' results
            record(f"[{app}] measured", False, repr(error))
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
