#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Each Writer button of Trang đầu and Chèn shows its label (or only its icon) as the reference table says, on gtk3.

Usage: python3 tests/runtime/check-ribbon-word-labels.py --instdir DIR [--display :281] [--out DIR]
Expected states: ribbon-word-label-expected.json (from reports/word-ribbon-audit.md, widths 1920, 1485, 1366). A button
shows a label when it is wider than ICON_MAX px (an icon with its padding is narrower). A button named in the
expected table but absent from the ribbon is listed as absent and is not an error (the table's "unmapped" rows are
never checked). Run as the build user under dbus-run-session, as the other AT-SPI checks. Exit 1 on any FAIL.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402
import ribbon_mockup_atspi as atspi  # noqa: E402

EXPECTED = os.path.join(HERE, "ribbon-word-label-expected.json")
WIDTHS = (1920, 1485, 1366)
ICON_MAX = 40
BUTTON_ROLES = ("push button", "toggle button", "push button menu", "menu button")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def wanted(state, width):
    """'label', 'icon' or None (no check) for a reference state at one width."""
    value = state if isinstance(state, str) else state.get(str(width))
    if value is None:
        return None
    if value in ("có", "có, xếp dọc"):
        return "label"
    if value == "chỉ icon":
        return "icon"
    return None


def check(args, expected):
    office, wid, _ = gui.start(args.instdir, "writer", args.display, os.path.join(args.out, "work"), 7703)
    try:
        for index, width in enumerate(WIDTHS):
            gui.xdo(args.display, "windowsize", wid, str(width), "900")
            time.sleep(4)
            for tab in ("Trang đầu", "Chèn"):
                gui.open_tab(args.display, tab)
                time.sleep(2)
                nodes = atspi.ribbon_nodes()
                for row in (r for r in expected["rows"] if r["tab"] == tab):
                    want = wanted(row["states"][index] if len(row["states"]) == 3 else row["states"][0], width)
                    if want is None:
                        continue
                    for name in row["hst"]:
                        found = next((n for n in nodes if n[0] in BUTTON_ROLES and n[1] == name), None)
                        if found is None:
                            print(f"absent  {width} {tab} {name}", flush=True)
                            continue
                        box = found[2]
                        got = "label" if box[2] > ICON_MAX else "icon"
                        record(f"[writer {width}] {tab}: {name} shows {want}", got == want, f"width {box[2]}, got {got}")
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":281")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-word-labels"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "NO_AT_BRIDGE=0",
                              "GTK_MODULES=gail:atk-bridge", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    with open(EXPECTED, encoding="utf-8") as handle:
        expected = json.load(handle)
    hst_gui.setup_uno(args.instdir)
    try:
        check(args, expected)
    except Exception as error:  # noqa: BLE001 - shown as FAIL with its reason
        record("word label checks ran", False, repr(error))
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
