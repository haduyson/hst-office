#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Calibrate the HST frame glyphs against the Colibre icons they stand beside.

The default "Cổ điển" style shows Colibre everywhere it has an icon, so a frame glyph must neither
look heavier, smaller nor softer than its Colibre neighbours: the File tab items around it, the
other sidebar decks, the status bar controls. NEIGHBOURS lists 2-3 such icons per glyph. Each
glyph and neighbour is rasterised (rsvg-convert; the shipped HST files are filled outlines on whole
pixels, so VCL with the HST patches gives the same pixels) at every logical size and display scale:

  100 %  the 1x file (Windows 125 % uses the same raster: CountDPIScaleFactor gives 100)
  150 %  HST: the @150 variant at 1.0; Colibre: its SVG at 1.5 (what VCL does today)
  200 %  both at 2x
  250 %  HST: the @250 variant; Colibre at 2.5

and measured on the light theme, where the outline ink is dark:
  size     optical size: larger side of the bounding box of paint (alpha >= 25 %) / canvas;
  stroke   outline weight in device px: 2 x ink area / outline length of the dark ink;
  ink      ink density: mean coverage of the dark ink over the canvas;
  fringe   share of painted pixels only partly covered (8-80 %), the blur measure of
           tests/runtime/check-hst-icon-sharpness.py;
  halfpx   share of painted pixels at 30-70 % coverage (half-pixel lines).
A glyph is flagged when a metric leaves its neighbours' range widened by TOLERANCE (fringe and
halfpx only upwards: sharper is never an outlier; fringe never above the softest neighbour, so a
circle may be as soft as Colibre's circles but no softer), or when its ink density is more than
INK_MEDIAN from the neighbours' median. `outliers()` is the gate of
tests/unit/test_hst_icon_frame_set.py. With --sheet, a side-by-side sheet (light and dark)
and with --json the measurement table are written. Needs NumPy, Pillow, rsvg-convert.
"""
import argparse
import json
import statistics
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hst_classic_icons as classic  # noqa: E402
import hst_icon_frame_sheet as sheet  # noqa: E402
from hst_icon_glyph import variant_key  # noqa: E402

from hst_icon_frame_glyphs import NATIVE, NEIGHBOURS, native_masters, sizes_of, square_masters  # noqa: E402

# Small control marks drawn inside a button (the document tab's close and new), the visual size of
# LibreOffice's own close mark by owner decision of 20/11: judged on pen weight, sharpness and an ink
# density no heavier than the heaviest close mark beside them.
MARKS = {"tabclose", "tabnew"}
# Measured, accepted exceptions: (glyph, display scale %) -> metrics not judged. At 250 % the 45-degree arms
# of the tab-close mark snap to a 2 px pen, and any 2 px diagonal measures fringe 0.39 (pens 1.65-2.4 and
# spans 8-10 units were swept on 20/11/2026); LibreOffice's own close mark is no sharper at 1x (0.44).
EXCEPTIONS = {}
# Named tolerances: near misses the owner's reviewer accepted after measuring through VCL (rsvg passes
# them): (glyph, cell) -> {metric: extra allowance}. sidebar-property at 32 px carries 0.0005 more ink
# than the median band (20/11/2026).
NEAR_MISSES = {("sidebar-property", "32@100"): {"ink": 0.001}}
SCALES = (100, 150, 200, 250)
METRICS = ("size", "stroke", "ink", "fringe", "halfpx")
TOLERANCE = {"size": 0.10, "stroke": 0.15, "ink": 0.20, "fringe": 0.0, "halfpx": 0.10}
INK_MEDIAN = 0.15  # ink density also within +-15 % of the neighbours' median: never heavier than Colibre on average
ONE_SIDED = {"fringe", "halfpx"}
INK_LUMA = 110  # light theme: Colibre's outline ink #3A3A38 and HST's currentColor are both darker than this


class Rasteriser:
    """rsvg-convert by default; with VCL rasters (tests/runtime/render-svg-through-vcl.py output) the
    product's own pixels. Every request is recorded so the VCL job list can be written."""

    def __init__(self, vcl=None):
        self.vcl, self.jobs = vcl, {}

    @staticmethod
    def key(svg, pixels, height):
        import hashlib
        return hashlib.sha1(svg.encode("utf-8")).hexdigest()[:16] + f"-{pixels}" + (
            "" if height == pixels else f"x{height}")

    def __call__(self, svg, pixels, height=None):
        height = pixels if height is None else height
        key = self.key(svg, pixels, height)
        self.jobs[key] = {"svg": svg, "pixels": pixels, "height": height}
        if self.vcl is None:
            return sheet.rasterise(svg, pixels, height)
        if key not in self.vcl:
            raise ValueError(f"no VCL raster for {key}; rerun with --emit-jobs and the VCL renderer")
        rows = np.asarray(self.vcl[key], dtype=float)  # height x width x (a, r, g, b), 0..1
        rgba = np.stack([rows[:, :, 1], rows[:, :, 2], rows[:, :, 3], rows[:, :, 0]], axis=2)
        return Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")


RASTER = Rasteriser()


def colibre_request(name, size):
    """Colibre request of a neighbour at a logical size (res/ images have one size only)."""
    if not name.startswith("cmd/sc_"):
        return name
    stem = name[len("cmd/sc_"):]
    return {16: f"cmd/sc_{stem}", 24: f"cmd/lc_{stem}", 32: f"cmd/32/{stem}"}[size]


class Colibre:
    def __init__(self, icon_themes):
        self.root = Path(icon_themes)
        self.cover = {theme: classic.Coverage(self.root, theme) for theme in ("colibre_svg", "colibre_dark_svg")}

    def svg(self, request, dark=False):
        theme = "colibre_dark_svg" if dark else "colibre_svg"
        links = self.cover[theme].links
        real = links.get(request + ".png") or links.get(request + ".svg") or request + ".svg"
        path = self.root / theme / (real[:-4] + ".svg")
        return path.read_text(encoding="utf-8") if path.is_file() else None


def measure(image):
    """Metrics of one RGBA raster (light theme)."""
    rgba = np.asarray(image, dtype=float) / 255.0
    alpha = rgba[:, :, 3]
    luma = (0.299 * rgba[:, :, 0] + 0.587 * rgba[:, :, 1] + 0.114 * rgba[:, :, 2]) * 255
    ink = np.where(luma < INK_LUMA, alpha, 0.0)
    side = max(alpha.shape)
    rows, cols = np.nonzero(alpha >= 0.25)
    size = (max(rows.max() - rows.min(), cols.max() - cols.min()) + 1) / side if rows.size else 0.0
    solid = np.pad(ink > 0.5, 1)
    edges = int(np.sum(solid[1:, :] != solid[:-1, :]) + np.sum(solid[:, 1:] != solid[:, :-1]))
    painted = alpha[alpha >= 0.08]
    return {"size": round(float(size), 3),
            "stroke": round(float(2 * ink.sum() / edges), 3) if edges else 0.0,
            "ink": round(float(ink.mean()), 4),
            "fringe": round(float(np.mean(painted < 0.8)), 3) if painted.size else 0.0,
            "halfpx": round(float(np.mean((painted > 0.3) & (painted < 0.7))), 3) if painted.size else 0.0}


def svg_size(text):
    """(width, height) in px of an SVG with numeric width/height, else of its viewBox."""
    import re
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text)
    number = re.compile(r"\s*(\d+(?:\.\d+)?)")
    width, height = number.match(root.get("width") or ""), number.match(root.get("height") or "")
    if width and height:
        return float(width.group(1)), float(height.group(1))
    box = (root.get("viewBox") or "0 0 16 16").split()
    return float(box[2]), float(box[3])


def cells(name, theme, colibre):
    """[(label, scale, hst raster callable, [(request, raster callable)])] of one glyph."""
    dark = theme.endswith("_dark")
    result = []
    if name in NATIVE:
        files = sheet.shipped_native(name, theme)
        width, height = sheet.native_size(files["100"])
        for scale in SCALES:
            w, h = round(width * scale / 100), round(height * scale / 100)
            text = files[str(scale)] if scale in (150, 250) else files["100"]
            hst = (lambda text=text, w=w, h=h: RASTER(text, w, h))
            result.append((f"native@{scale}", scale, hst, neighbour_rasters(colibre, name, None, scale, dark)))
        return result
    files = sheet.shipped(name, theme)
    for size in sizes_of(name):
        for scale in SCALES:
            key = f"{sheet.PREFIX[size]}{name}.svg"
            key = variant_key(key, scale) if scale in (150, 250) else key
            pixels = round(size * scale / 100)
            hst = (lambda text=files[key], pixels=pixels: RASTER(text, pixels))
            result.append((f"{size}@{scale}", scale, hst, neighbour_rasters(colibre, name, size, scale, dark)))
    return result


def neighbour_rasters(colibre, name, size, scale, dark):
    """[(request, raster callable)] of a glyph's Colibre neighbours at a logical size (None: their native size)."""
    found = []
    for neighbour in NEIGHBOURS[name]:
        request = colibre_request(neighbour, size) if size else neighbour
        svg = colibre.svg(request, dark)
        if svg is None:
            continue
        if size:
            w = h = round(size * scale / 100)
        else:
            width, height = svg_size(svg)
            w, h = round(width * scale / 100), round(height * scale / 100)
        found.append((request, lambda svg=svg, w=w, h=h: RASTER(svg, w, h)))
    return found


def judge(name, label, scale, hst, neighbours):
    flags = []
    allowance = NEAR_MISSES.get((name, label), {})
    for metric in METRICS:
        if name in MARKS and metric in ("size", "ink") or metric in EXCEPTIONS.get((name, scale), ()):
            continue
        values = [m[metric] for m in neighbours.values()]
        if not values:
            continue
        low, high = min(values), max(values)
        span = TOLERANCE[metric] * max(high, 1e-6) + allowance.get(metric, 0.0)
        if hst[metric] > high + span:
            flags.append(f"{metric} {hst[metric]} > Colibre {high}")
        elif metric not in ONE_SIDED and hst[metric] < low - span:
            flags.append(f"{metric} {hst[metric]} < Colibre {low}")
    if neighbours:
        middle = statistics.median(m["ink"] for m in neighbours.values())
        heaviest = max(m["ink"] for m in neighbours.values())
        extra = allowance.get("ink", 0.0)
        # a mark matches LibreOffice's own close mark in size, so it may be as heavy as the heaviest
        # close mark beside it, never heavier
        if (hst["ink"] > (1 + INK_MEDIAN) * heaviest + extra if name in MARKS
                else abs(hst["ink"] - middle) > INK_MEDIAN * middle + extra):
            flags.append(f"ink {hst['ink']} not within 15 % of the Colibre median {round(middle, 4)}")
    return flags


def compare(names, colibre):
    """{glyph: {label: {"hst": metrics, "colibre": {request: metrics}, "flags": [...]}}}."""
    report = {}
    for name in names:
        report[name] = {}
        for label, scale, hst_raster, neighbours in cells(name, "hst", colibre):
            hst = measure(hst_raster())
            measured = {request: measure(raster()) for request, raster in neighbours}
            report[name][label] = {"hst": hst, "colibre": measured,
                                   "flags": judge(name, label, scale, hst, measured)}
    return report


def outliers(report):
    return {f"{name} {key}": cell["flags"] for name, cells in report.items() for key, cell in cells.items()
            if cell["flags"]}


def draw_sheet(names, colibre, report, path):
    """Light and dark panels: per glyph, every cell as a 2 x 2 block (HST top left, then its Colibre
    neighbours) with the HST measurements below; a red label marks an outlier."""
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    cell_w, row_h, label_w, header = 180, 2 * 80 + 4 + 52, 150, 24
    columns = max(len(report[name]) for name in names)
    panels = []
    for dark in (False, True):
        theme = "hst_dark" if dark else "hst"
        image = Image.new("RGB", (label_w + columns * cell_w, header + row_h * len(names)), sheet.BACKGROUND[theme])
        drawing = ImageDraw.Draw(image)
        drawing.text((8, 6), ("Dark" if dark else "Light") + ": HST glyph (top left) beside its Colibre neighbours; "
                     "red label = outlier", fill=sheet.TEXT[theme], font=font)
        for row, name in enumerate(names):
            y = header + row * row_h
            drawing.text((8, y + 8), name, fill=sheet.TEXT[theme], font=font)
            for column, (label, _, hst_raster, neighbours) in enumerate(cells(name, theme, colibre)):
                x = label_w + column * cell_w
                cell = report[name][label]
                icons = [hst_raster()] + [raster() for _, raster in neighbours]
                w, h = max(i.width for i in icons), max(i.height for i in icons)
                for index, icon in enumerate(icons[:4]):
                    image.paste(icon, (x + 4 + (index % 2) * (w + 4), y + 22 + (index // 2) * (h + 4)), icon)
                hst = cell["hst"]
                colour = (220, 40, 40) if cell["flags"] else sheet.TEXT[theme]
                drawing.text((x + 4, y + 6), label, fill=sheet.TEXT[theme], font=font)
                drawing.text((x + 4, y + row_h - 34),
                             f"w {hst['stroke']:.2f} i {hst['ink']:.2f}\ns {hst['size']:.2f} f {hst['fringe']:.2f}",
                             fill=colour, font=font)
        panels.append(image)
    result = Image.new("RGB", (panels[0].width, sum(p.height for p in panels)), (255, 255, 255))
    result.paste(panels[0], (0, 0))
    result.paste(panels[1], (0, panels[0].height))
    path.parent.mkdir(parents=True, exist_ok=True)
    result.save(path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lo-tree", type=Path, required=True, help="pristine LibreOffice tree (its Colibre SVG)")
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--emit-jobs", type=Path, help="write the SVGs to rasterise through VCL and stop")
    parser.add_argument("--vcl-rasters", type=Path, help="VCL rasters of those jobs (render-svg-through-vcl.py)")
    parser.add_argument("--only", nargs="+", help="judge only these glyphs")
    args = parser.parse_args()
    global RASTER
    if args.vcl_rasters:
        RASTER = Rasteriser(json.loads(args.vcl_rasters.read_text(encoding="utf-8")))
    names = square_masters(sheet.STAGE) + native_masters(sheet.STAGE)
    if args.only:
        names = [n for n in names if n in args.only]
    missing = sorted(set(names) - set(NEIGHBOURS))
    if missing:
        sys.exit(f"no Colibre neighbours listed for {missing}")
    colibre = Colibre(args.lo_tree / "icon-themes")
    report = compare(names, colibre)
    if args.emit_jobs:
        for name in names:  # the dark panel of the sheet needs the dark rasters too
            for _, _, hst_raster, neighbours in cells(name, "hst_dark", colibre):
                hst_raster()
                for _, raster in neighbours:
                    raster()
        args.emit_jobs.write_text(json.dumps(RASTER.jobs) + "\n", encoding="utf-8")
        print(f"{len(RASTER.jobs)} rasters to render through VCL: {args.emit_jobs}")
        return 0
    if args.json:
        args.json.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if args.sheet:
        draw_sheet(names, colibre, report, args.sheet)
    flagged = outliers(report)
    for key, flags in flagged.items():
        print("OUTLIER", key, "; ".join(flags))
    print(f"{len(names)} glyphs, {len(flagged)} outlier cells")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
