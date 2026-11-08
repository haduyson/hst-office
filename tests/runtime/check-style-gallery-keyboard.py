# SPDX-License-Identifier: AGPL-3.0-only
"""The Styles gallery on Writer's Home tab, by keyboard (gtk3, vi_VN).

Usage: python3 tests/runtime/check-style-gallery-keyboard.py [--instdir DIR] [--display :71] [--out DIR]

At 1600 px (the gallery shows one preview) and at 1920 px (several): a click on the first preview applies its
style; Right applies the next style, also past the last visible preview (the gallery pages on); Enter applies
the focused style and opens no dialog (it used to open Modify Style); Left goes back to the first style.
Reads the paragraph style at the view cursor through UNO. Writes evidence.json; exit 1 on a failed check.
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

PORT = 7474
GALLERY = "Xem thử kiểu dáng"
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:240]}", flush=True)


def gallery_box():
    for node in gui.walk(gui.office_app()):
        try:
            if node.getRoleName() == "panel" and node.name == GALLERY and gui.showing(node):
                return gui.extents(node)
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
    return None


def windows(display, office):
    return sorted(name for _wid, name in hst_gui.toplevels(display, office.pid))


def sweep(args, office, wid, width):
    display = args.display
    gui.xdo(display, "windowsize", wid, str(width), "900")
    time.sleep(4)
    box = gallery_box()
    if box is None:
        record(f"[{width}] the Styles gallery is on the ribbon", False, "no gallery")
        return
    cursor = office.desktop().getCurrentComponent().getCurrentController().getViewCursor()
    before = windows(display, office)
    gui.click(display, (box[0] + 8, box[1] + 8, 40, box[3] - 16))
    time.sleep(1.2)
    first = cursor.ParaStyleName
    gui.xdo(display, "key", "Right")
    time.sleep(1.2)
    second = cursor.ParaStyleName
    record(f"[{width}] Right applies the next style", second != first, (first, second))
    gui.xdo(display, "key", "Right")
    time.sleep(1.2)
    third = cursor.ParaStyleName
    record(f"[{width}] Right goes on past the visible previews", third not in (first, second), (second, third))
    gui.xdo(display, "key", "Return")
    time.sleep(1.5)
    after = windows(display, office)
    record(f"[{width}] Enter applies the focused style and opens no dialog",
           cursor.ParaStyleName == third and not set(after) - set(before), (cursor.ParaStyleName, sorted(set(after) - set(before))))
    if set(after) - set(before):
        gui.xdo(display, "key", "Escape")
        time.sleep(1)
    for _ in range(2):
        gui.xdo(display, "key", "Left")
        time.sleep(1.2)
    record(f"[{width}] Left goes back to the first style", cursor.ParaStyleName == first, (first, cursor.ParaStyleName))
    cursor.ParaStyleName = first  # leave the paragraph as it was
    time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/style-gallery-keyboard"))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=True)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office = None
    try:
        office, wid, _windows = gui.start(args.instdir, "writer", args.display, args.out, PORT)
        for width in (1600, 1920):
            sweep(args, office, wid, width)
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        if office is not None and office.proc is not None:
            office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
