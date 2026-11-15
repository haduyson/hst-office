# SPDX-License-Identifier: AGPL-3.0-only
"""Checks the Writer ribbon tabs Trang đầu and Chèn (gtk3, vi_VN) against the mockup's reference vectors.

Usage: python3 tests/runtime/check-ribbon-mockup.py --instdir DIR [--display :281] [--out DIR] [--sweep-step 10]
For each tab and each width of ribbon-mockup-expected.json (1100-1920) the window is resized and read through AT-SPI:
  - every group's ladder state (L, M, S, C) equals the mockup vector (ribbon_mockup_geometry.py, heuristic classification);
  - the body of a ribbon group, from its top to the bottom of its caption, is 106 px (±1);
  - from the top of the tab row to the top of the document tab strip is 147 px (±1);
  - the banner matches the mockup rule for its width (260 wide up to 1440 px, then growing to 360 at 1920; height 104/360 of width);
  - the font box "Tên phông" is 128 px and the size box "Kích cỡ phông" 46 px wherever the font group is L;
  - with --sweep-step N the states are read every N px from 1100 to 1920 and no group moves to a larger ladder level as
    the window widens (monotonic).
Writes <out>/results.json and <out>/measured.json. Runs as the build user (dbus-run-session, AT-SPI); exit 1 on any FAIL.
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
import ribbon_mockup_geometry as geo  # noqa: E402
from ribbon_mockup_rules import LEVEL, expected_banner, is_monotonic  # noqa: E402

EXPECTED = os.path.join(HERE, "ribbon-mockup-expected.json")
TOLERANCE = 1  # px, for sizes (the plan's ±1 px)
ROWS = []
WINDOW = [None]  # AT-SPI window id of the office under test, set by main


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def measure(tab, width):
    """States, body, tab row, banner and font boxes at one width of one tab."""
    nodes = geo.ribbon_nodes()
    tab_top, strip = geo.tab_geometry(nodes)
    return {"groups": geo.groups(nodes, tab), "tab_top": tab_top, "strip": strip, "banner": geo.banner(nodes),
            "font_box": geo.named_box(nodes, "Tên phông"), "size_box": geo.named_box(nodes, "Kích cỡ phông"),
            "width": width}


def check_width(tab, width, want, got):
    tag = f"[writer {tab} {width}]"
    states = {k: v["state"] for k, v in got["groups"].items()}
    diff = geo.compare_states(want["states"], {k: {"state": s} for k, s in states.items()})
    record(f"{tag} ladder states equal the mockup vector", not diff, diff or states)
    bodies = {k: v["caption_bottom"] - v["box"][1] for k, v in got["groups"].items() if v["state"] != "C"}
    off = {k: b for k, b in bodies.items() if abs(b - 106) > TOLERANCE}
    record(f"{tag} group body is 106 px", bool(bodies) and not off, off or bodies)
    if got["tab_top"] is not None and got["strip"] is not None:
        span = got["strip"][1] - got["tab_top"]
        record(f"{tag} tab row to document strip is 147 px", abs(span - 147) <= TOLERANCE, span)
    banner = got["banner"]
    if banner is not None:
        ew, eh = expected_banner(width)
        record(f"{tag} banner {ew}x{eh}", abs(banner[2] - ew) <= TOLERANCE and abs(banner[3] - eh) <= TOLERANCE,
               list(banner[2:]))
    if got["groups"].get("font", {}).get("state") == "L":
        fb = got["font_box"]
        record(f"{tag} font box 128 px", fb is not None and abs(fb[2] - 128) <= TOLERANCE, fb and fb[2])
        sb = got["size_box"]
        record(f"{tag} size box 46 px", sb is not None and abs(sb[2] - 46) <= TOLERANCE, sb and sb[2])


def run_tab(display, tab, widths, expected, measured):
    tabs = {t[0]: t for t in gui.ribbon_tabs()}
    name = {"home": "Trang đầu", "insert": "Chèn"}[tab]
    if name in tabs and not tabs[name][2]:
        gui.click(display, tabs[name][1])
    levels = {}
    for width in widths:
        gui.xdo(display, "windowsize", WINDOW[0], str(width), "900")
        time.sleep(3)
        got = measure(tab, width)
        measured[f"{tab}-{width}"] = {"states": {k: v["state"] for k, v in got["groups"].items()},
                                      "banner": got["banner"], "font_box": got["font_box"]}
        if width in [int(k.split("-")[1]) for k in expected if k.startswith(tab + "-")]:
            check_width(tab, width, expected[f"{tab}-{width}"], got)
        for key, value in got["groups"].items():
            levels.setdefault(key, []).append((width, value["state"]))
    return levels


def monotonic(levels, tab):
    """Each group's ladder level never drops as the window widens: the mockup's ladder only grows with the window."""
    for key, series in levels.items():
        states = [s for _w, s in sorted(series)]
        ok = is_monotonic(states) if all(s in LEVEL for s in states) else False
        record(f"[writer {tab}] {key} is monotonic from 1100 to 1920", ok, states if not ok else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":281")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-mockup"))
    parser.add_argument("--sweep-step", type=int, default=0, help="also sweep 1100-1920 in steps of N px (0: off)")
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "NO_AT_BRIDGE=0",
                              "GTK_MODULES=gail:atk-bridge", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    with open(EXPECTED, encoding="utf-8") as handle:
        expected = json.load(handle)["states"]
    hst_gui.setup_uno(args.instdir)
    office, wid, _ = gui.start(args.instdir, "writer", args.display, os.path.join(args.out, "work"), 7601)
    WINDOW[0] = wid
    measured = {}
    try:
        for tab in ("home", "insert"):
            widths = sorted({int(k.split("-")[1]) for k in expected if k.startswith(tab + "-")})
            if args.sweep_step:
                widths = list(range(1100, 1921, args.sweep_step))
            monotonic(run_tab(args.display, tab, widths, expected, measured), tab)
    finally:
        office.stop()
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "measured.json"), "w", encoding="utf-8") as handle:
        json.dump(measured, handle, ensure_ascii=False, indent=1, default=str)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
