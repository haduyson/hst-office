#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
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

# glyph -> Colibre requests (16 px names; the 24/32 px names are derived) that stand beside it
NEIGHBOURS = {
    "home": ["cmd/sc_adddirect", "cmd/sc_open", "cmd/sc_setdocumentproperties"],
    "saveas": ["cmd/sc_save", "cmd/sc_print", "cmd/sc_open"],
    "setupusbtoken": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "previousversions": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "unsaveddocuments": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "toggleduplex": ["cmd/sc_print", "cmd/sc_printpreview", "cmd/sc_exporttopdf"],
    # the tab marks stand beside LibreOffice's own close-button marks (vcl/res/closedoc is the × of its
    # close buttons), not beside document icons
    "tabclose": ["vcl/res/closedoc", "cmd/sc_closewin", "cmd/sc_delete"],
    "tabnew": ["vcl/res/closedoc", "cmd/sc_closewin", "cmd/sc_delete"],
    "sidebar-property": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-style": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-navigator": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "signature-status": ["svx/res/doc_modified_no", "svx/res/zoom_page_statusbar",
                         "svx/res/a11y_check_issues_not_found"],
}
# Small control marks drawn inside a button (the document tab's close and new), the visual size of
# LibreOffice's own close mark by owner decision of 20/11: judged on pen weight, sharpness and an ink
# density no heavier than the heaviest close mark beside them.
MARKS = {"tabclose", "tabnew"}
# Measured, accepted exceptions: (glyph, display scale %) -> metrics not judged. At 250 % the 45-degree arms
# of the tab-close mark snap to a 2 px pen, and any 2 px diagonal measures fringe 0.39 (pens 1.65-2.4 and
# spans 8-10 units were swept on 20/11/2026); LibreOffice's own close mark is no sharper at 1x (0.44).
EXCEPTIONS = {("tabclose", 250): {"fringe", "halfpx"}}
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
    def key(svg, pixels):
        import hashlib
        return hashlib.sha1(svg.encode("utf-8")).hexdigest()[:16] + f"-{pixels}"

    def __call__(self, svg, pixels):
        key = self.key(svg, pixels)
        self.jobs[key] = {"svg": svg, "pixels": pixels}
        if self.vcl is None:
            return sheet.rasterise(svg, pixels)
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
    side = alpha.shape[0]
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


def hst_raster(files, name, size, scale):
    key = f"{sheet.PREFIX[size]}{name}.svg"
    pixels = round(size * scale / 100)
    if scale in (150, 250):
        return RASTER(files[variant_key(key, scale)], pixels)
    return RASTER(files[key], pixels)


def colibre_raster(colibre, name, size, scale, dark=False):
    svg = colibre.svg(colibre_request(name, size), dark)
    if svg is None:
        return None
    return RASTER(svg, round(size * scale / 100))


def sizes_of(name):
    return (24, 32) if name.startswith("sidebar-") else (16, 24, 32)


def compare(names, colibre):
    """{glyph: {"size@scale": {"hst": metrics, "colibre": {neighbour: metrics}, "flags": [...]}}}."""
    report = {}
    for name in names:
        files = sheet.shipped(name, "hst")
        report[name] = {}
        for size in sizes_of(name):
            for scale in SCALES:
                hst = measure(hst_raster(files, name, size, scale))
                neighbours = {}
                for neighbour in NEIGHBOURS[name]:
                    image = colibre_raster(colibre, neighbour, size, scale)
                    if image is not None:
                        neighbours[colibre_request(neighbour, size)] = measure(image)
                flags = []
                for metric in METRICS:
                    if name in MARKS and metric in ("size", "ink") or metric in EXCEPTIONS.get((name, scale), ()):
                        continue
                    values = [m[metric] for m in neighbours.values()]
                    if not values:
                        continue
                    low, high = min(values), max(values)
                    span = TOLERANCE[metric] * max(high, 1e-6)
                    if hst[metric] > high + span:
                        flags.append(f"{metric} {hst[metric]} > Colibre {high}")
                    elif metric not in ONE_SIDED and hst[metric] < low - span:
                        flags.append(f"{metric} {hst[metric]} < Colibre {low}")
                if neighbours:
                    middle = statistics.median(m["ink"] for m in neighbours.values())
                    heaviest = max(m["ink"] for m in neighbours.values())
                    # a mark matches LibreOffice's own close mark in size, so it may be as heavy as the
                    # heaviest close mark beside it, never heavier
                    if (hst["ink"] > (1 + INK_MEDIAN) * heaviest if name in MARKS
                            else abs(hst["ink"] - middle) > INK_MEDIAN * middle):
                        flags.append(f"ink {hst['ink']} not within 15 % of the Colibre median {round(middle, 4)}")
                report[name][f"{size}@{scale}"] = {"hst": hst, "colibre": neighbours, "flags": flags}
    return report


def outliers(report):
    return {f"{name} {key}": cell["flags"] for name, cells in report.items() for key, cell in cells.items()
            if cell["flags"]}


def draw_sheet(names, colibre, report, path):
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    columns = [(s, sc) for s in (16, 24, 32) for sc in SCALES]
    cell_w = [max(2 * round(s * sc / 100) + 16, 96) for s, sc in columns]
    row_h, label_w, header = 2 * 80 + 4 + 46, 140, 34  # a 2 x 2 block of the largest raster (32 px at 250 %) + labels
    panels = []
    for dark in (False, True):
        theme = "hst_dark" if dark else "hst"
        width = label_w + sum(cell_w)
        image = Image.new("RGB", (width, header + row_h * len(names)), sheet.BACKGROUND[theme])
        drawing = ImageDraw.Draw(image)
        drawing.text((8, 8), ("Dark" if dark else "Light") + ": HST glyph (first) beside its Colibre neighbours; "
                     "red label = outlier", fill=sheet.TEXT[theme], font=font)
        x = label_w
        for (s, sc), w in zip(columns, cell_w):
            drawing.text((x + 4, 20), f"{s} px @{sc}%", fill=sheet.TEXT[theme], font=font)
            x += w
        for row, name in enumerate(names):
            y = header + row * row_h
            files = sheet.shipped(name, theme)
            drawing.text((8, y + 8), name, fill=sheet.TEXT[theme], font=font)
            x = label_w
            for (s, sc), w in zip(columns, cell_w):
                if s in sizes_of(name):
                    cell = report[name][f"{s}@{sc}"]
                    icons = [hst_raster(files, name, s, sc)]
                    icons += [i for i in (colibre_raster(colibre, n, s, sc, dark) for n in NEIGHBOURS[name]) if i]
                    px = icons[0].width
                    ix, iy = x + 4, y + 6
                    for index, icon in enumerate(icons):  # a 2 x 2 block: HST top left
                        image.paste(icon, (ix + (index % 2) * (px + 4), iy + (index // 2) * (px + 4)), icon)
                    hst = cell["hst"]
                    colour = (220, 40, 40) if cell["flags"] else sheet.TEXT[theme]
                    drawing.text((x + 4, y + row_h - 40),
                                 f"w {hst['stroke']:.2f} i {hst['ink']:.2f}\ns {hst['size']:.2f} f {hst['fringe']:.2f}",
                                 fill=colour, font=font)
                x += w
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
    args = parser.parse_args()
    global RASTER
    if args.vcl_rasters:
        RASTER = Rasteriser(json.loads(args.vcl_rasters.read_text(encoding="utf-8")))
    names = sorted(p.stem for p in sheet.STAGE.glob("*.svg"))
    missing = sorted(set(names) - set(NEIGHBOURS))
    if missing:
        sys.exit(f"no Colibre neighbours listed for {missing}")
    colibre = Colibre(args.lo_tree / "icon-themes")
    report = compare(names, colibre)
    if args.emit_jobs:
        for name in names:  # the dark panel of the sheet needs the dark rasters too
            files = sheet.shipped(name, "hst_dark")
            for size in sizes_of(name):
                for scale in SCALES:
                    hst_raster(files, name, size, scale)
                    for neighbour in NEIGHBOURS[name]:
                        colibre_raster(colibre, neighbour, size, scale, True)
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
