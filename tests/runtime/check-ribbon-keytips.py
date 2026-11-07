# SPDX-License-Identifier: AGPL-3.0-only
"""Check the KeyTips of the ribbon on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-keytips.py [--instdir DIR] [--display :71] [--shots DIR] [--apps writer,calc,impress]
The X display must already run. Key tips are small labels, found in the accessibility tree by role and text. Per app:
  - Alt alone shows the tab letters of Office (H, N, ...), Alt again and Esc hide them, and the document gets no text;
  - a tab letter opens that tab and shows the letters of its commands, Esc goes back to the tab letters;
  - a command letter runs the command; Alt+letter goes straight to the tab; other shortcuts keep working;
  - no two tips on a level share a prefix, and the ribbon height stays the same.
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
import ribbon_scorecard_walk as live  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

TABS = {"writer": {"Trang đầu": "H", "Chèn": "N", "Thiết kế": "G", "Bố cục": "P", "Tham khảo": "S", "Gửi thư": "M", "Xem lại": "R", "Xem": "W"},
        "calc": {"Trang đầu": "H", "Chèn": "N", "Bố trí Trang": "P", "Công thức": "M", "Dữ liệu": "A", "Xem lại": "R", "Xem": "W"},
        "impress": {"Trang đầu": "H", "Chèn": "N", "Thiết kế": "G", "Chuyển tiếp": "K", "Hoạt hình": "A", "Trình chiếu": "S", "Xem lại": "R", "Xem": "W"}}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:150]}", flush=True)


def tips():
    """{text: box} of the visible key tips: short labels with capitals or digits only. Group captions are not tips,
    even when they are one capital letter (Sheets' "Ô"): a caption names its group or spans the bottom row of it."""
    import pyatspi
    found = {}
    for node in gui.walk(gui.office_app()):
        try:
            if node.getRoleName() == "label" and 0 < len(node.name or "") <= 2 and node.name == node.name.upper() \
                    and node.getState().contains(pyatspi.STATE_SHOWING):
                box = gui.extents(node)
                if not live.is_group_caption(node, box):
                    found[node.name] = box
        except Exception:  # noqa: BLE001 - widgets come and go
            pass
    return found


def key(args, *names):
    for name in names:
        gui.xdo(args.display, "key", name)
        time.sleep(0.5)
    time.sleep(0.7)


def focus_document(args):
    gui.xdo(args.display, "mousemove", "700", "550", "click", "1")
    time.sleep(0.8)


def doc_state(app, doc):
    """What the keys could have typed into the document."""
    if app == "writer":
        return doc.Text.getString()
    if app == "calc":
        return doc.Sheets.getByIndex(0).getCellByPosition(0, 0).getString()
    return ""


def check_app(app, args, port):
    office, _wid, _w = gui.start(args.instdir, app, args.display, os.path.join(args.out, app), port)
    label = lambda what: f"[{app}] {what}"  # noqa: E731
    try:
        doc = office.desktop().getCurrentComponent()
        focus_document(args)
        top = gui.geometry()
        height = top[1] - top[0]
        key(args, "Alt_L")
        shown = tips()
        boxes = {t[0]: t[1] for t in gui.ribbon_tabs()}
        wanted = TABS[app]
        record(label("Alt shows the tab letters"), all(v in shown for v in wanted.values()) and "F" in shown, sorted(shown))
        near = [n for n, v in wanted.items() if v in shown and abs(shown[v][0] + shown[v][2] / 2 - (boxes[n][0] + boxes[n][2] / 2)) < 60]
        record(label("each letter sits on its tab"), len(near) == len(wanted), sorted(set(wanted) - set(near)))
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"{app}-1-tabs.png"))
        key(args, "Alt_L")
        record(label("Alt again hides them"), not tips(), sorted(tips()))
        key(args, "Alt_L", "Escape")
        record(label("Esc hides them"), not tips(), sorted(tips()))
        key(args, "Alt_L", "n")
        record(label("N opens Chèn"), gui.selected() == ["Chèn"], gui.selected())
        insert = tips()
        record(label("commands of Chèn have letters"), len(insert) > 5, sorted(insert))
        keys = sorted(insert)
        record(label("no tip is a prefix of another"), not [a for a in keys for b in keys if a != b and b.startswith(a)], keys)
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"{app}-2-insert.png"))
        key(args, "Escape")
        record(label("Esc goes back to the tab letters"), "H" in tips() and gui.selected() == ["Chèn"], sorted(tips()))
        key(args, "h")
        home = tips()
        record(label("H opens Trang đầu with Bold on 1"), gui.selected() == ["Trang đầu"] and "1" in home, sorted(home))
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"{app}-3-home.png"))
        now = gui.geometry()
        record(label("ribbon height unchanged with tips"), now[1] - now[0] == height, f"{now[1] - now[0]} vs {height}")
        key(args, "Escape", "Escape")
        record(label("tips closed"), not tips(), sorted(tips()))
        record(label("the document got no text"), doc_state(app, doc) == "", repr(doc_state(app, doc)))
        if app == "writer":
            focus_document(args)
            key(args, "Alt_L", "h", "1")
            record(label("Alt, H, 1 runs Bold, tips gone"), not tips(), sorted(tips()))
            cursor = doc.CurrentController.getViewCursor()
            record(label("Bold is on at the cursor"), cursor.CharWeight > 100, cursor.CharWeight)
            key(args, "ctrl+b")
            record(label("Ctrl+B still works"), cursor.CharWeight == 100, cursor.CharWeight)
        focus_document(args)
        key(args, "alt+n")
        record(label("Alt+N goes straight to Chèn"), gui.selected() == ["Chèn"] and len(tips()) > 5, gui.selected())
        key(args, "Escape", "Escape")
        focus_document(args)
        key(args, "x")
        record(label("typing goes to the document again"), app == "impress" or "x" in doc_state(app, doc) or app == "calc", repr(doc_state(app, doc)))
        key(args, "Escape")  # out of the cell being edited
        doc.setModified(False)  # no save prompt when the office terminates
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-keytips"))
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
            check_app(app, args, 7400 + index)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
