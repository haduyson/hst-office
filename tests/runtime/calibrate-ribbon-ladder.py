#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Calibrates the ladder classification (ribbon_mockup_geometry) against the P0 baseline on Linux (gtk3, Xvfb).

Usage: python3 tests/runtime/calibrate-ribbon-ladder.py --instdir DIR --baseline reference/p0-widths-baseline-linux.json
       [--display :281] [--out DIR]
For Writer's Trang đầu and Chèn at each width the baseline measured, the group ids of the baseline are mapped to the
mockup's group keys (MAPPING) and the state the baseline chose is compared with the state read from the accessible
tree. Writes <out>/calibration.json and prints one line per group and width. The mapping and the agreement rate are
the calibration record: a disagreement is a heuristic error or a real difference, decided by looking at the group.
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
import ribbon_mockup_geometry as geo  # noqa: E402

MAPPING = {  # baseline group id -> (tab key, mockup key)
    "gdHomeClipboard": ("home", "clip"), "gdHomeFont": ("home", "font"), "gdHomeParagraph": ("home", "para"),
    "gdHomeStyle": ("home", "styles"), "gdHomeHstEditing": ("home", "edit"), "gdHomeHstVietnamese": ("home", "viet"),
    "gdInsertPage": ("insert", "pages"), "gdInsertTables": ("insert", "tables"), "gdInsertGraphic": ("insert", "illus"),
    "gdInsertReferences": ("insert", "links"), "gdInsertComments": ("insert", "comments"),
    "gdInsertHeaderFooter": ("insert", "hf"), "gdInsertText": ("insert", "text"), "gdInsertSymbols": ("insert", "symbols"),
}
TABS = {"home": "Trang đầu", "insert": "Chèn"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--display", default=":281")
    parser.add_argument("--out", default="/tmp/ribbon-calibration")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(args.baseline, encoding="utf-8") as handle:
        rows = [r for r in json.load(handle)["rows"] if r["app"] == "writer" and not r.get("sweep")]
    wanted = {}
    for r in rows:
        for group in r["boxes"].get("pmhbHome" if r["tab"] == "Trang đầu" else "pmhbInsert", {}).get("groups", []):
            if group["id"] in MAPPING:
                wanted.setdefault(r["width"], {}).setdefault(r["tab"], {})[group["id"]] = group["state"]
    office, wid, _ = gui.start(args.instdir, "writer", args.display, os.path.join(args.out, "work"), 7702)
    report, agree, total = [], 0, 0
    try:
        for width in sorted(wanted):
            gui.xdo(args.display, "windowsize", wid, str(width), "900")
            time.sleep(4)
            for tab_name, groups in wanted[width].items():
                gui.open_tab(args.display, tab_name)
                time.sleep(2)
                nodes = atspi.ribbon_nodes()
                key = "home" if tab_name == "Trang đầu" else "insert"
                measured = geo.groups(nodes, key)
                for group_id, base_state in groups.items():
                    mockup_key = MAPPING[group_id][1]
                    ours = measured.get(mockup_key, {}).get("state")
                    total += 1
                    agree += ours == base_state
                    line = {"width": width, "tab": tab_name, "group": group_id, "key": mockup_key,
                            "baseline": base_state, "ours": ours}
                    report.append(line)
                    print(f"{width} {tab_name:10s} {group_id:22s} {mockup_key:9s} baseline={base_state} ours={ours}", flush=True)
    finally:
        office.stop()
    summary = {"agreement": f"{agree}/{total}", "rows": report}
    with open(os.path.join(args.out, "calibration.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=1)
    print(f"agreement {agree}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
