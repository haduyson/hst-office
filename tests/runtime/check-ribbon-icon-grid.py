#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Icon grid invariants of the ribbon buttons (owner's rule, Lead's constants), checked on a measurement file.

Usage: python3 tests/runtime/check-ribbon-icon-grid.py MEASURE.json [--scale 1.0|1.5] [--out DIR]
MEASURE.json maps "app-width-tab" to the buttons: {"role", "name", "box": [x, y, w, h], "small", "ink": [dx, dy]}, where
ink is the icon's top-left offset from the button's top-left (the P2 measurement of the AT-SPI tree and the pixels).
Invariants (px, tolerance ±0.5, multiplied by the scale for 150 %):
  1. a small icon's inset is (4, 4), with or without a label (the same offset in a labelled and an icon-only button);
  2. small icons of one row share the top y (absolute), within the row's tolerance;
  3. small icons of one column share the left x (absolute);
  4. a large icon is centred horizontally in its button (inset (w - 24) / 2).
Not measured by this file: the 16 × 16 icon size and the 150 % pixel grid; those need the pixels (reported as SKIP).
Exit 1 on any FAIL.
"""
import argparse
import json
import os
import sys

TOL = 0.5
SMALL_INSET = (4, 4)
LARGE_ICON = 24
ROW_TOL = 0.5


def check(measure, scale):
    rows, skipped = [], ["icon size 16x16 and the 150 % pixel grid: need the pixels, not this file"]
    for key, buttons in measure.items():
        small = [b for b in buttons if b.get("small") and b.get("ink")]
        large = [b for b in buttons if not b.get("small") and b.get("ink")]
        for b in small:
            dx, dy = b["ink"]
            want = (SMALL_INSET[0] * scale, SMALL_INSET[1] * scale)
            ok = abs(dx - want[0]) <= TOL * scale and abs(dy - want[1]) <= TOL * scale
            rows.append((f"{key} {b['name']}: small icon inset {want}", ok, f"ink {dx},{dy}"))
        for b in large:
            x, y, w, h = b["box"]
            want_x = (w - LARGE_ICON * scale) / 2
            ok = abs(b["ink"][0] - want_x) <= TOL * scale
            rows.append((f"{key} {b['name']}: large icon centred", ok, f"ink x {b['ink'][0]}, centre {want_x:.1f}"))
        for i, a in enumerate(small):
            for c in small[i + 1:]:
                if abs(a["box"][1] - c["box"][1]) <= ROW_TOL:  # same row (same top of button)
                    ya, yc = a["box"][1] + a["ink"][1], c["box"][1] + c["ink"][1]
                    ok = abs(ya - yc) <= ROW_TOL * scale
                    rows.append((f"{key} row: {a['name']} / {c['name']} share the icon top", ok, f"{ya} vs {yc}"))
                if abs(a["box"][0] - c["box"][0]) <= ROW_TOL:  # same column
                    xa, xc = a["box"][0] + a["ink"][0], c["box"][0] + c["ink"][0]
                    ok = abs(xa - xc) <= ROW_TOL * scale
                    rows.append((f"{key} column: {a['name']} / {c['name']} share the icon left", ok, f"{xa} vs {xc}"))
    return rows, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("measure")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--out")
    args = parser.parse_args()
    with open(args.measure, encoding="utf-8") as handle:
        measure = json.load(handle)
    rows, skipped = check(measure, args.scale)
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    failed = sum(not ok for _n, ok, _d in rows)
    for reason in skipped:
        print(f"SKIP  {reason}")
    print(f"{len(rows)} checks, {failed} failed")
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "icon-grid.json"), "w", encoding="utf-8") as handle:
            json.dump({"checks": [{"check": n, "ok": ok, "detail": d} for n, ok, d in rows], "skipped": skipped},
                      handle, ensure_ascii=False, indent=1)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
