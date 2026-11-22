#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Icon grid invariants of the ribbon buttons (owner's rule, Lead's constants), checked on a measurement file.

Usage: python3 tests/runtime/check-ribbon-icon-grid.py MEASURE.json [--scale 1.0|1.5] [--out DIR]
MEASURE.json maps "app-width-tab" to the buttons: {"role", "name", "box": [x, y, w, h], "small", "slot": [x, y]}, where
slot is the [x, y] of the icon slot the layout places (absolute px), when P2 exports it.
Invariants (px, tolerance ±0.5, multiplied by the scale for 150 %), on the icon SLOT the layout places (P2's "slot";
the ink is information only, the Colibre icon has a transparent margin):
  1. a large icon's slot is centred horizontally in its button ((w - 24) / 2);
  2. small buttons of one row share the slot top; large buttons of one row share the slot top (same kind only);
  3. small buttons of one column share the slot left; large buttons of one column likewise.
Not measured by this file: the 16 × 16 icon size and the 150 % pixel grid (SKIP). The file needs a "slot" per button.
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
    """Rows are (name, ok, detail); the icon slot the layout places is the compared position, never the ink."""
    rows, skipped = [], ["icon size 16x16 and the 150 % pixel grid: need the pixels, not this file"]
    skipped.append("ink offsets are information only: the Colibre icon has a transparent margin (P2)")
    for key, buttons in measure.items():
        small = [b for b in buttons if b.get("small") and b.get("slot")]
        large = [b for b in buttons if not b.get("small") and b.get("slot")]
        for b in large:  # a large icon is centred in its 32 px slot, which the layout places
            x, y, w, h = b["box"]
            sx, _sy = b["slot"]
            want = x + (w - LARGE_ICON * scale) / 2
            ok = abs(sx - want) <= TOL * scale
            rows.append((f"{key} {b['name']}: large icon slot centred", ok, f"slot x {sx}, centre {want:.1f}"))
        for group, label in ((small, "small"), (large, "large")):  # compare only buttons of the same kind
            for i, a_ in enumerate(group):
                for c in group[i + 1:]:
                    if abs(a_["box"][1] - c["box"][1]) <= ROW_TOL:  # same row: the slots share the top
                        ya, yc = a_["slot"][1], c["slot"][1]
                        rows.append((f"{key} {label} row: {a_['name']} / {c['name']} share the slot top",
                                     abs(ya - yc) <= ROW_TOL * scale, f"{ya} vs {yc}"))
                    if abs(a_["box"][0] - c["box"][0]) <= ROW_TOL:  # same column: the slots share the left
                        xa, xc = a_["slot"][0], c["slot"][0]
                        rows.append((f"{key} {label} column: {a_['name']} / {c['name']} share the slot left",
                                     abs(xa - xc) <= ROW_TOL * scale, f"{xa} vs {xc}"))
    return rows, skipped


def parse_dump(lines):
    """[(size flag, command, icon rect, button rect, scale)] from HST_RIBBON_ICON lines (the VCL dump of P2).

    Format (15 fields): HST_RIBBON_ICON <L|S> <command> icon x y w h button x y w h scale <factor>; the last line of a
    command wins."""
    last = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 15 or parts[0] != "HST_RIBBON_ICON" or parts[3] != "icon" or parts[8] != "button":
            continue
        flag, command = parts[1], parts[2]
        icon = tuple(int(v) for v in parts[4:8])
        button = tuple(int(v) for v in parts[9:13])
        last[command] = (flag, command, icon, button, float(parts[14]))
    return list(last.values())


def check_dump(entries, icon_px=24):
    """The layout rules of P2 for the icon slot: S/M icon at (4, centred) of the button, L icon centred with its top at
    iconY below the button top (10 for a 17 px label; 7 when the font is taller; 32 px icons 4 px higher)."""
    rows = []
    for flag, command, icon, button, scale in entries:
        bx, by, bw, bh = button
        ix, iy, iw, ih = icon
        if flag == "S":
            want_x = bx + 4 * scale
            want_y = by + (bh - ih) / 2
            ok = abs(ix - want_x) <= TOL * scale and abs(iy - want_y) <= TOL * scale
            rows.append((f"{command}: small icon at (4, centred)", ok, f"icon {ix},{iy} want {want_x:.1f},{want_y:.1f}"))
        else:
            want_x = bx + (bw - iw) / 2
            ok = abs(ix - want_x) <= TOL * scale
            rows.append((f"{command}: large icon centred", ok, f"icon x {ix} want {want_x:.1f}"))
            dy = iy - by
            allowed = [v * scale for v in (10, 7, 6, 3)] if iw == icon_px else [v * scale for v in (6, 3)]
            ok = any(abs(dy - v) <= TOL * scale for v in allowed)
            rows.append((f"{command}: large icon top at iconY", ok, f"top offset {dy} allowed {allowed}"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("measure", help="the measurement JSON, or with --dump the HST_RIBBON_ICON text file")
    parser.add_argument("--dump", action="store_true", help="read the VCL dump (HST_RIBBON_DUMP_ICONS) instead")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.dump:
        with open(args.measure, encoding="utf-8") as handle:
            rows = check_dump(parse_dump(handle.read().splitlines()))
        skipped = ["the VCL dump has the icon and button rectangles only; no AT-SPI check here"]
    else:
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
