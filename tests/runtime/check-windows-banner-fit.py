#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Judge what collect-windows-banner-fit.py gathered on Windows with check-banner-fit.py's rules.

Usage: python3 tests/runtime/check-windows-banner-fit.py --collected DIR --instdir LINUX_INSTDIR [--out FILE]
DIR holds collected-<label>.json and shots\\ (pulled from the Windows PC); LINUX_INSTDIR is an installed HST Office
of the same build, for the bundled artworks the banner may show. Per app, scale and theme:
  - case: on the first tab, exactly one banner, which has its artwork's ratio and shows it edge to edge, with the
    ribbon's body on both sides of it;
  - -header: the tab row is one surface from the first tab title to the window's right edge, every title on it;
  - -tabs: one banner on every tab, flush with the right end of the ribbon (8 px before the client area's right
    edge, scaled with the office's own UI factor: 1 up to 125 %, see office_scale), the same box on every tab.
Exit 1 when a case fails; writes the rows to --out (JSON).
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_banner_probe as probe  # noqa: E402


def load_check(name):
    """A tests/runtime/check-*.py script as a module (its main() is not run)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"),
                                                  os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fit = load_check("check-banner-fit")


def office_scale(percent):
    """The office's own UI scale factor at a display scaling (vcl Window CountDPIScaleFactor, not macOS): 1 up to
    120 DPI (125 %), then 1.5, 2 and 2.5; fonts follow the display scaling, the ribbon's pixel geometry this factor."""
    dpi = 96 * percent / 100
    return 2.5 if dpi > 216 else 2 if dpi > 168 else 1.5 if dpi > 120 else 1


def judge_case(case, data, scale, shots_dir, catalogue):
    """[(name, ok, detail)] for one app/scale/theme of the collected data."""
    frame, tabs = data["client"], data["tabs"]
    for tab in tabs:  # collections before the banner filter kept the window's own node "<document> — <app>"
        window = [box for box in tab["banners"] if box[3] > 200]
        tab["banners"] = [box for box in tab["banners"] if box[3] <= 200]
        if frame[2] <= 0 and window:  # client box read after the window closed: its accessible box is the client area
            frame = window[0]
    margin = fit.RIGHT_MARGIN * office_scale(scale)
    if not tabs:
        return [(case, False, "no tab collected")]
    first = tabs[0]
    shot = os.path.join(shots_dir, first["shot"])
    rows = []
    if len(first["banners"]) != 1:
        rows.append((case, False, f"{len(first['banners'])} banners visible on {first['tab']}"))
    else:
        box = first["banners"][0]
        ok, detail = fit.judge(box, shot, catalogue)
        same, surface = fit.body_continuous(shot, box, frame)
        rows.append((case, ok and same, f"{detail} at {box}; {surface}"))
    titles = [(name, box) for name, box in first["tabs"]]
    if titles:
        boxes = [box for _name, box in titles]
        ok, detail = fit.header_continuous(shot, titles, fit.row_widgets(first["widgets"], boxes, frame), frame)
    else:
        ok, detail = False, "no tab titles"
    rows.append((f"{case}-header", ok, detail))
    seen, bad = {}, []
    right = frame[0] + frame[2] - margin
    for tab in tabs:
        if len(tab["banners"]) != 1:
            bad.append(f"{tab['tab']}: {len(tab['banners'])} banners")
            continue
        box = tuple(tab["banners"][0])
        seen[tab["tab"]] = box
        if abs(box[0] + box[2] - right) > 1:
            bad.append(f"{tab['tab']}: right edge {box[0] + box[2]}, expected {right}")
    if len(set(seen.values())) > 1:
        bad.append(f"the banner moves between tabs: {sorted(set(seen.values()))}")
    rows.append((f"{case}-tabs", not bad and bool(seen),
                 "; ".join(bad) or f"{len(seen)} tabs, banner at {next(iter(seen.values()))}"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collected", required=True)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    catalogue, _ = probe.items(args.instdir)
    results = []
    for path in sorted(glob.glob(os.path.join(args.collected, "collected-*.json"))):
        with open(path, encoding="utf-8") as handle:
            collected = json.load(handle)
        scale = collected.pop("scale")
        for case, data in collected.items():
            rows = [(case, False, "not collected")] if data is None else judge_case(
                case, data, scale, os.path.join(args.collected, "shots"), catalogue)
            for name, ok, detail in rows:
                results.append({"case": name, "status": "PASS" if ok else "FAIL", "detail": detail})
                print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    ok = bool(results) and all(r["status"] == "PASS" for r in results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
    print(f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} cases pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
