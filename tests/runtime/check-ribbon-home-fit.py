# SPDX-License-Identifier: AGPL-3.0-only
"""Check what the Home tab of Writer, Sheets and Slides shows at 1366 and 1485 px, next to the banner (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-home-fit.py [--instdir DIR] [--display :71] [--shots DIR] [--apps writer,calc,impress]
The X display must already run, at least 2400 px wide. Per app and width:
  - Clone Formatting and Clear keep their accessible names and show their labels where there is room (1485 px; owner,
    2026-11-07); at 1366 px the collapse ladder may take the labels away again, so only the name is checked there;
  - their commands still have a label, from which the tooltip comes; hovering shows it (see --shots);
  - the banner is on screen, inside the window;
  - the groups named in MUST_SHOW have a visible caption: Sheets' Number and Slides' Paragraph at 1366, Writer's
    "Kiểu" (Styles) at 1366 and 1485 and Sheets' at 1485, beside the banner;
  - Find & Replace is a button of the paragraph group (Sheets: alignment); at 1920 px the group "Công cụ" has the
    tab menu, the HST commands and "Tìm tính năng" in rows, and the tab menu offers "Tìm tính năng"
    (ribbon_home_tools_gui.py).
Prints the visible group captions per width. Exit 1 when a check fails.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_home_tools_gui as tools  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ribbon_tabs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-ribbon-tabs.py"))
tabs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tabs)

LABEL_WIDTH = 1485  # from this width up Clone Formatting and Clear show their labels
LABELLED = {"writer", "calc"}  # apps whose 1.0.0 content patch has these labels; the others are still icon-only
ICON_MAX = 40  # an icon with its button padding; the same button with its text is over 100 px wide
PAINTBRUSH = "Sao chép định dạng"
CLEAR = {"writer": "Xóa", "calc": "Xóa", "impress": "Xóa"}
CAPTION_BAND = (95, 165)  # the caption row of a ribbon page, y relative to the window
# Sheets' Kiểu folds at 1366: it needs about 120 px that only narrower Font/Number boxes (1.0.0) would free.
MUST_SHOW = {("calc", 1366): ["Số"], ("impress", 1366): ["Đoạn văn"], ("writer", 1366): ["Đoạn văn", "Kiểu"],
             ("calc", 1485): ["Kiểu"], ("writer", 1485): ["Kiểu"]}
WIDTHS = (1366, 1485)
WIDE = {"writer": 1920, "calc": 2400, "impress": 1920}  # nothing folds: the whole "Công cụ" group shows


def showing(node):
    import pyatspi
    return node.getState().contains(pyatspi.STATE_SHOWING)


def measure(width):
    """Visible labels and tool items of the ribbon page, and the banner box."""
    labels, buttons, banner = [], {}, None
    for node in tabs.walk(tabs.office_app()):
        try:
            role, name = node.getRoleName(), node.name or ""
            if not name or not showing(node):
                continue
            box = tabs.extents(node)
        except Exception:  # noqa: BLE001  widgets come and go
            continue
        if role == "label" and box[1] < 230 and box[0] + box[2] <= width:
            labels.append((name, box))
        elif role in ("push button", "toggle button") and name in (PAINTBRUSH, *CLEAR.values()) and box[1] < 230:
            buttons.setdefault(name, (box, node.getDescription() if hasattr(node, "getDescription") else node.description))
        elif role == "link" and banner is None and box[2] > 100:
            banner = box
    return labels, buttons, banner


def check_app(app, args, port):
    office, wid = tabs.start(args.instdir, app, args, f"fit-{app}", port)
    try:
        ribbon = next(t for t in tabs.ribbon_tabs() if t[0] == "Trang đầu")
        if not ribbon[2]:
            tabs.click(args.display, ribbon[1])
        for width in WIDTHS:
            tabs.xdo(args.display, "windowsize", wid, str(width), "900")
            time.sleep(4)
            labels, buttons, banner = measure(width)
            captions = sorted({n for n, b in labels if b[3] < 30}, key=lambda n: min(b[0] for m, b in labels if m == n))
            print(f"[{app} {width}] captions: {captions}", flush=True)
            print(f"[{app} {width}] banner: {banner}; buttons: {json.dumps({k: v[0] for k, v in buttons.items()})}", flush=True)
            for group in MUST_SHOW.get((app, width), []):
                tabs.record(f"[{app} {width}] group '{group}' shows", group in captions, captions)
            caption_boxes = [(n, b) for n, b in labels if b[3] < 30]
            tools.check_find_in_paragraph(tabs, app, width, caption_boxes)
            for name in (PAINTBRUSH, CLEAR[app]):
                box = buttons.get(name, ((0, 0, 0, 0),))[0]
                if app not in LABELLED:
                    tabs.record(f"[{app} {width}] '{name}' accessible and icon-only", 0 < box[2] <= ICON_MAX, box)
                elif width >= LABEL_WIDTH:
                    tabs.record(f"[{app} {width}] '{name}' accessible and labelled", box[2] > ICON_MAX, box)
                else:
                    tabs.record(f"[{app} {width}] '{name}' accessible", box[2] > 0, box)
            tabs.record(f"[{app} {width}] banner inside the window",
                        banner is not None and banner[0] + banner[2] <= width, banner)
            if args.shots:
                office.screenshot(os.path.join(args.shots, f"home-fit-{app}-{width}.png"))
            if name in buttons and args.shots:  # hover the last button: its tooltip is the command label
                x, y, w, h = buttons[PAINTBRUSH][0]
                tabs.xdo(args.display, "mousemove", str(x + w // 2), str(y + h // 2))
                time.sleep(2.5)
                office.screenshot(os.path.join(args.shots, f"home-fit-{app}-{width}-tooltip.png"))
                tabs.xdo(args.display, "mousemove", str(width // 2), "600")
                time.sleep(0.5)
        tabs.xdo(args.display, "windowsize", wid, str(WIDE[app]), "900")
        time.sleep(4)
        labels, _buttons, _banner = measure(WIDE[app])
        tools.check_tools_group(tabs, args, app, WIDE[app], [(n, b) for n, b in labels if b[3] < 30])
        tools.check_menu_has_search(tabs, args, app)
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"home-fit-{app}-{WIDE[app]}.png"))
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-home-fit"))
    parser.add_argument("--shots")
    parser.add_argument("--apps", default="writer,calc,impress")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    for index, app in enumerate(args.apps.split(",")):
        try:
            check_app(app, args, 7300 + 2 * index)
        except Exception as error:  # noqa: BLE001
            tabs.record(f"[{app}] crashed", False, repr(error))
    failed = sum(r["status"] != "PASS" for r in tabs.ROWS)
    print(f"{len(tabs.ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
