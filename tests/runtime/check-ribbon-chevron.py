# SPDX-License-Identifier: AGPL-3.0-only
"""Check the chevron (») of the ribbon on a real GUI: shown only when a group is folded, and it opens them (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-chevron.py [--instdir DIR] [--display :71] [--shots DIR]
The X display must already run, at least 1600 px wide. In Writer's Home tab:
  - at every width of a sweep the chevron is on the ribbon exactly when one of the groups is not;
  - a click on it opens a popup with the folded groups, and Esc puts them back;
  - with KeyTips (Alt, H, then the chevron's letters) the popup opens with KeyTips on its commands; Esc closes both.
Writes evidence.json. Runs as the build user under dbus-run-session (AT-SPI).
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

GROUPS = ["Bảng tạm", "Phông chữ", "Đoạn văn", "Kiểu"]  # Writer's Home tab, left to right
WIDTHS = list(range(1600, 1440, -5))
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)


def showing(node):
    import pyatspi
    return node.getState().contains(pyatspi.STATE_SHOWING)


def scan():
    """Group captions, the chevron box (or None), the popup boxes and the key tips now on screen."""
    captions, chevron, tips = [], None, []
    for node in gui.walk(gui.office_app()):
        try:
            if not showing(node):
                continue
            role, name, box = node.getRoleName(), node.name or "", gui.extents(node)
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
        if role == "label" and name in GROUPS:
            captions.append((name, box))
        elif role == "label" and 0 < len(name) <= 2 and name == name.upper():
            tips.append((name, box))
        elif role == "push button" and not name and box[2] <= 30 and box[3] >= 60 and box[1] < 230:
            chevron = box
    popups = []
    for node in gui.office_app():
        try:
            if node.getRoleName() == "window" and showing(node):
                popups.append(gui.extents(node))
        except Exception:  # noqa: BLE001
            pass
    return captions, chevron, popups, tips


def inside(box, area):
    return area[0] <= box[0] and box[0] + box[2] <= area[0] + area[2] and area[1] <= box[1] and box[1] + box[3] <= area[1] + area[3]


def key(args, *names):
    for name in names:
        gui.xdo(args.display, "key", name)
        time.sleep(0.5)
    time.sleep(1.0)


def shot(office, args, name):
    if args.shots:
        office.screenshot(os.path.join(args.shots, f"chevron-{name}.png"))


def check_sweep(args, wid):
    """The chevron is there exactly when a group is folded; returns a width with a folded group."""
    folded_at, mismatches = None, []
    for width in WIDTHS:
        gui.xdo(args.display, "windowsize", wid, str(width), "900")
        time.sleep(2.5)
        captions, chevron, _popups, _tips = scan()
        on_ribbon = [n for n, b in captions if b[1] < 230]
        hidden = [g for g in GROUPS if g not in on_ribbon]
        if bool(chevron) != bool(hidden):
            mismatches.append((width, hidden, chevron))
        if hidden and folded_at is None:
            folded_at = width
    record("chevron shown exactly when a group is folded", not mismatches, mismatches or f"{WIDTHS[0]}..{WIDTHS[-1]} px")
    record("a group folds within the sweep", folded_at is not None, folded_at)
    return folded_at


def check_click(office, args, wid, width):
    gui.xdo(args.display, "windowsize", wid, str(width), "900")
    time.sleep(3)
    captions, chevron, _popups, _tips = scan()
    hidden = [g for g in GROUPS if g not in [n for n, b in captions if b[1] < 230]]
    if not chevron:
        record(f"[{width}] chevron on the ribbon", False, captions)
        return
    gui.click(args.display, chevron)
    time.sleep(1.5)
    captions, _chevron, popups, _tips = scan()
    shot(office, args, f"{width}-click")
    in_popup = [n for n, b in captions if popups and inside(b, popups[0])]
    record(f"[{width}] click opens a popup with the folded groups", bool(popups) and in_popup == hidden, (hidden, in_popup, popups))
    key(args, "Escape")
    captions, chevron, popups, _tips = scan()
    on_ribbon = [n for n, b in captions if b[1] < 230]
    record(f"[{width}] Esc closes it, groups and chevron as before", not popups and bool(chevron)
           and [g for g in GROUPS if g not in on_ribbon] == hidden, (on_ribbon, popups))


def check_keytips(office, args, width):
    gui.xdo(args.display, "mousemove", "500", "550", "click", "1")
    time.sleep(0.8)
    _captions, chevron, _popups, _tips = scan()
    key(args, "Alt_L", "h")
    _captions, _chevron, _popups, tips = scan()
    if not chevron or not tips:
        record(f"[{width}] KeyTips on the chevron", False, (chevron, tips))
        return
    centre = (chevron[0] + chevron[2] / 2, chevron[1] + chevron[3])
    tip = min(tips, key=lambda t: abs(t[1][0] + t[1][2] / 2 - centre[0]) + abs(t[1][1] + t[1][3] / 2 - centre[1]))[0]
    record(f"[{width}] the chevron has a KeyTip", True, tip)
    key(args, *tip.lower())
    time.sleep(1)
    _captions, _chevron, popups, tips = scan()
    shot(office, args, f"{width}-keytips")
    in_popup = [t for t, b in tips if popups and inside(b, popups[0])]
    record(f"[{width}] the KeyTip opens the popup with KeyTips on its commands", bool(popups) and bool(in_popup), (popups, in_popup))
    key(args, "Escape")
    _captions, _chevron, popups, tips = scan()
    record(f"[{width}] Esc closes the popup and its KeyTips", not popups and not tips, (popups, tips))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-chevron"))
    parser.add_argument("--shots")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office, wid, _windows = gui.start(args.instdir, "writer", args.display, os.path.join(args.out, "writer"), 7420)
    try:
        home = next(t for t in gui.ribbon_tabs() if t[0] == "Trang đầu")
        if not home[2]:
            gui.click(args.display, home[1])
        folded_at = check_sweep(args, wid)
        if folded_at:
            check_click(office, args, wid, folded_at)
            check_keytips(office, args, folded_at)
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
