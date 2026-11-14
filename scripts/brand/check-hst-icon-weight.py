#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Regression check of the optical weight and sharpness of the shipped HST command icons.

Every cmd/ glyph of the themes (sc_ 16 px, lc_ 24 px, 32/ 32 px) is rasterised at its own size
from the shipped SVG (filled outlines; even-odd per <path>, union across paths, 4 x 4 samples per px)
and measured on its ink, the paths painted in the theme's ink colour:

  stroke   estimated line weight in px, 2 x ink area / ink outline length (a 1 px line gives ~1);
  ink      share of the canvas covered by ink;
  fringe   share of painted pixels only partly covered (alpha 8-80 %), the blur measure of
           tests/runtime/check-hst-icon-sharpness.py.

COLIBRE holds the same medians of the LibreOffice Colibre icons the HST glyphs stand beside (533
ribbon requests, dark outline ink only, rsvg-convert, 1.0.2 tree): 1 px lines at every size. Exit 1 when
  * a size's median stroke or ink differs from Colibre's by more than 25 % / 35 %, or the median
    stroke at 24 / 32 px exceeds 1.25 x the 16 px one (large icons heavier than small ones: the
    2 px / 3 px pens of 1.0.1);
  * an icon's stroke exceeds 1.5 x, or its ink 2 x, its size's median (outliers);
  * a size's median fringe exceeds 0.35, or an icon's fringe exceeds MAX_FRINGE (blurred icon);
  * geometry reaches outside the canvas (clipped shapes);
  * a display-scale variant (name@150.svg, name@250.svg) is blurred, clipped, or heavier than its scale's pen.
Icons drawn heavy on purpose (HEAVY_ON_PURPOSE) are measured, not judged; icons without ink (the
HASON TECH mark in its brand colour) are judged only on fringe and clipping.
Standard library plus NumPy. --json writes every measurement.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hst_icon_outline import flatten  # noqa: E402
from hst_svg_path import parse_path  # noqa: E402
from hst_icon_lattice import BASE_PEN, target_pen  # noqa: E402
from hst_svg_math import round_half_up  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"
SS = 4
SIZES = {"cmd/sc_": 16, "cmd/lc_": 24, "cmd/32/": 32}
COLIBRE = {16: {"stroke": 0.92, "ink": 0.251}, 24: {"stroke": 0.91, "ink": 0.156}, 32: {"stroke": 0.94, "ink": 0.125}}
MAX_FRINGE = 0.8
# Heavy on purpose: the bold B's heavier pen; the solid dots of the grid toggle are not lines.
HEAVY_ON_PURPOSE = {"bold", "gridvisible"}


def load_builder():
    spec = importlib.util.spec_from_file_location("build_hst_icon_theme", HERE / "build-hst-icon-theme.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def coverage(polygons, size):
    """Even-odd coverage of `polygons` (lists of points in px) sampled at SS x SS points per pixel."""
    centres = (np.arange(size * SS) + 0.5) / SS
    inside = np.zeros((size * SS, size * SS), dtype=bool)
    for points in polygons:
        a = np.array(points, dtype=float)
        b = np.roll(a, -1, axis=0)
        ys = centres[:, None]
        crossing = (a[None, :, 1] > ys) != (b[None, :, 1] > ys)
        with np.errstate(divide="ignore", invalid="ignore"):
            x = a[None, :, 0] + (ys - a[None, :, 1]) * (b[None, :, 0] - a[None, :, 0]) / (b[None, :, 1] - a[None, :, 1])
        x = np.where(crossing, x, -np.inf)
        inside ^= (np.sum(centres[None, None, :] < x[:, :, None], axis=1) % 2).astype(bool)
    return inside


def raster(svg, size, ink):
    """(alpha of all paint, alpha of ink, px of geometry outside the canvas); alphas size x size."""
    every, inked = np.zeros((size * SS,) * 2, dtype=bool), np.zeros((size * SS,) * 2, dtype=bool)
    overflow = 0.0
    for element in ET.fromstring(svg).iter(f"{NS}path"):
        outlines = [flatten(sub)[0] for sub in parse_path(element.get("d", ""))]
        outlines = [points for points in outlines if len(points) > 2]
        overflow = max([overflow] + [max(-v, v - size) for points in outlines for point in points for v in point])
        layer = coverage(outlines, size)
        every |= layer
        if (element.get("fill") or "").upper() == ink.upper():
            inked |= layer

    def alpha(mask):
        return mask.reshape(size, SS, size, SS).mean(axis=(1, 3))
    return alpha(every), alpha(inked), overflow


def measure(svg, size, ink):
    paint, alpha, overflow = raster(svg, size, ink)
    solid = np.pad(alpha > 0.5, 1)
    edges = int(np.sum(solid[1:, :] != solid[:-1, :]) + np.sum(solid[:, 1:] != solid[:, :-1]))
    painted = paint[paint >= 0.08]
    return {"stroke": round(float(2 * alpha.sum() / edges), 3) if edges else 0.0,
            "ink": round(float(alpha.mean()), 4),
            "fringe": round(float(np.mean(painted < 0.8)), 3) if painted.size else 0.0,
            "overflow": round(float(overflow), 3)}


def measure_theme(files, ink):
    """{name: measurements} of every cmd icon; display-scale variants (name@150.svg) carry their scale."""
    result = {}
    for name in sorted(files):
        prefix = next((p for p in SIZES if name.startswith(p)), None)
        if prefix and name.endswith(".svg") and "/" not in name[len(prefix):]:
            stem, _, percent = name[len(prefix):-4].partition("@")
            scale = int(percent or 100)
            pixels = round_half_up(SIZES[prefix] * scale / 100)
            result[name] = dict(measure(files[name].decode("utf-8"), pixels, ink), size=SIZES[prefix],
                                stem=stem, scale=scale)
    return result


def judge_variants(theme, icons):
    """Display-scale variants: crisp (fringe), unclipped, and as heavy as the pen of their scale."""
    failures = []
    for size, scale in sorted({(i["size"], i.get("scale", 100)) for i in icons.values() if i.get("scale", 100) != 100}):
        group = [i for i in icons.values() if (i["size"], i.get("scale", 100)) == (size, scale) and i["ink"]
                 and i["stem"] not in HEAVY_ON_PURPOSE]
        pen = target_pen(BASE_PEN, size, scale / 100)
        stroke, fringe = (statistics.median(i[k] for i in group) for k in ("stroke", "fringe"))
        if stroke > 1.25 * pen or fringe > 0.35:
            failures.append(f"{theme} {size} px at {scale} %: median stroke {stroke:.2f} (pen {pen}), fringe {fringe:.2f}")
    for name, icon in icons.items():
        if icon.get("scale", 100) != 100 and (icon["overflow"] > 0.01 or icon["fringe"] > MAX_FRINGE):
            failures.append(f"{theme} {name}: fringe {icon['fringe']:.2f}, {icon['overflow']:.2f} px outside")
    return failures


def judge(theme, icons):
    failures, medians = judge_variants(theme, icons), {}
    icons = {name: icon for name, icon in icons.items() if icon.get("scale", 100) == 100}
    for size in sorted(set(SIZES.values())):
        group = [i for i in icons.values() if i["size"] == size and i["stem"] not in HEAVY_ON_PURPOSE and i["ink"]]
        medians[size] = {k: statistics.median(i[k] for i in group) for k in ("stroke", "ink", "fringe")}
    for size, median in medians.items():
        reference = COLIBRE[size]
        if abs(median["stroke"] / reference["stroke"] - 1) > 0.25 or median["stroke"] > 1.25 * medians[16]["stroke"]:
            failures.append(f"{theme} {size} px: median stroke {median['stroke']:.2f} px, Colibre "
                            f"{reference['stroke']:.2f}, 16 px {medians[16]['stroke']:.2f}")
        if abs(median["ink"] / reference["ink"] - 1) > 0.35:
            failures.append(f"{theme} {size} px: median ink {median['ink']:.3f}, Colibre {reference['ink']:.3f}")
        if median["fringe"] > 0.35:
            failures.append(f"{theme} {size} px: median fringe {median['fringe']:.2f} (blurred set)")
    for name, icon in icons.items():
        median = medians[icon["size"]]
        if icon["overflow"] > 0.01:
            failures.append(f"{theme} {name}: geometry {icon['overflow']:.2f} px outside the canvas, clipped")
        if icon["fringe"] > MAX_FRINGE:
            failures.append(f"{theme} {name}: fringe {icon['fringe']:.2f}, blurred")
        if icon["stem"] in HEAVY_ON_PURPOSE or not icon["ink"]:
            continue
        if icon["stroke"] > 1.5 * median["stroke"]:
            failures.append(f"{theme} {name}: stroke {icon['stroke']:.2f} px vs median {median['stroke']:.2f}")
        if icon["ink"] > 2.0 * median["ink"]:
            failures.append(f"{theme} {name}: ink {icon['ink']:.3f} vs median {median['ink']:.3f}")
    return failures, medians


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--themes", nargs="+", default=["hst", "hst_dark"],
                        help="HST themes to build in memory and check (every theme draws the same masters)")
    parser.add_argument("--json", type=Path, help="write every measurement here")
    args = parser.parse_args()
    builder = load_builder()
    report, failures = {}, []
    for theme in args.themes:
        if theme not in builder.FULL_THEMES:
            parser.error(f"unknown theme {theme}; one of {', '.join(builder.FULL_THEMES)}")
        icons = measure_theme(builder.resources(theme), builder.PALETTES[theme])
        problems, medians = judge(theme, icons)
        failures += problems
        report[theme] = {"medians": medians, "icons": icons}
        for size, median in medians.items():
            count = sum(i["size"] == size and i["scale"] == 100 for i in icons.values())
            print(f"{theme} {size:>2} px: {count} icons (+ scale variants), median stroke "
                  f"{median['stroke']:.2f} px, ink {median['ink']:.3f}, fringe {median['fringe']:.2f}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for line in failures:
        print("FAIL", line)
    print(f"{len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
