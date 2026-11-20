#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Rasterise a list of SVGs through VCL's own pipeline and write their ARGB pixels.

Input (--jobs): {key: {"svg": text, "pixels": width, "height": height (default width)}}, e.g. from scripts/brand/hst_icon_frame_compare.py
--emit-jobs. Each SVG is rendered at pixels / its own width (VCL's scale for an icon of that
size), with hst_vcl_icon_raster (headless office of --instdir). Output (--out): {key: rows of
(a, r, g, b) 0..1}. A raster whose size is not pixels x height is an error. Run with the instdir's
Python as root with an X display, like check-hst-icon-sharpness.py.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hst_gui  # noqa: E402


def natural_width(svg):
    root = ET.fromstring(svg)
    width = re.match(r"\s*(\d+(?:\.\d+)?)", root.get("width") or "")
    if width:
        return float(width.group(1))
    box = (root.get("viewBox") or "").split()
    if len(box) != 4:
        raise ValueError("SVG without width or viewBox")
    return float(box[2])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--instdir", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=22197)
    args = parser.parse_args()
    if not re.fullmatch(r":\d+", args.display):
        parser.error("--display must look like :97")
    os.environ["DISPLAY"] = args.display
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    hst_gui.setup_uno(str(args.instdir.resolve()))
    import hst_vcl_icon_raster as raster
    office = hst_gui.Office(str(args.instdir.resolve()), str(args.work.resolve() / "render"), args.port,
                            display=args.display, extra_args=["--headless"])
    result, errors = {}, []
    try:
        office.start()
        for key, job in sorted(jobs.items()):
            svg, pixels, tall = job["svg"].encode("utf-8"), job["pixels"], job.get("height", job["pixels"])
            width, height, rows = raster.rasterise(office.ctx, svg, pixels / natural_width(job["svg"]), key, argb=True)
            if width != pixels or abs(height - tall) > 1:
                errors.append(f"{key}: {width}x{height}, expected {pixels}x{tall}")
                continue
            # a non-square image scaled by its width may round its height one pixel the other way:
            # crop the extra bottom row or pad a transparent one so every raster has the asked size
            rows = [list(row) for row in rows[:tall]]
            rows += [[(0.0, 0.0, 0.0, 0.0)] * width for _ in range(tall - len(rows))]
            result[key] = [[list(p) for p in row] for row in rows]
    finally:
        office.stop()
    args.out.write_text(json.dumps(result) + "\n", encoding="utf-8")
    print(f"{len(result)} rasters; {len(errors)} errors")
    for line in errors[:20]:
        print("ERROR", line)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
