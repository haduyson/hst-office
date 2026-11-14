# SPDX-License-Identifier: AGPL-3.0-only
"""One shipped HST command glyph: its SVG at a raster size, and its display-scale variants.

VCL rasterises an icon SVG at its icon scale, which window.cxx (CountDPIScaleFactor) rounds to
100, 150, 200 or 250 % (a 125 % display draws icons at 100 %, 175 % at 150 %). At 150 and 250 % the
1 px lines of a snapped glyph fall between pixels (grey, blurred), so each glyph also ships a
natively snapped variant `<name>@<percent>.svg` drawn at round(size x scale) px;
hst-icon-theme-fractional-scale.patch makes VCL load it at 1.0. 100 % and 200 % need none: the 1x
geometry doubles onto whole pixels. Standard library only.
"""
from pathlib import Path, PurePosixPath

import hst_modern_icons as modern
from hst_icon_snap import snap_svg

SOURCE = Path(__file__).resolve().parents[2] / "icon-themes-src/hst"
MISSING_MODERN = set()
FACTORS = {150: 1.5, 250: 2.5}


def variant_key(key, percent):
    """Archive name of the `percent` % variant of the shipped icon `key` (cmd/lc_x.svg -> cmd/lc_x@150.svg)."""
    path = PurePosixPath(key)
    return str(path.with_name(f"{path.stem}@{percent}{path.suffix}"))


def glyph_files(key, master, size, colour, theme):
    """{archive name: SVG bytes} of one glyph at `size`: the 100 % file and its scale variants."""
    files = {key: glyph_svg(master, size, colour, theme)}
    for percent, factor in FACTORS.items():
        files[variant_key(key, percent)] = glyph_svg(master, size, colour, theme, factor)
    return files


def glyph_svg(master, size, colour, theme="hst", factor=1.0):
    """Shipped SVG of one glyph: pixel-snapped strokes painted as filled outlines.

    Every theme draws the colourful master (hst-modern) in Colibre's colours (colibre-harmony.json),
    the classic master only where none is drawn. Hand-tuned masters drawn in target pixels
    (glyphs/stage-1-16, glyphs/stage-1-24) replace the snapped 24-unit master for that size at 100 %;
    `factor` snaps the glyph natively for that display scale."""
    root, colours = SOURCE, None
    drawn = modern.master(master)
    if drawn is None:
        MISSING_MODERN.add(master.stem)
    else:
        root, master, colours = modern.MODERN, drawn, modern.palette()
        problems = modern.violations(drawn.read_text(encoding="utf-8"), colours)
        if problems:
            raise ValueError(f"{drawn}: " + "; ".join(problems))
    tuned = root / f"glyphs/stage-1-{size}" / master.name
    if colours is not None and not tuned.is_file() and not modern.HEX.search(master.read_text(encoding="utf-8")):
        tuned = SOURCE / f"glyphs/stage-1-{size}" / master.name  # ink-only: the classic tuning is the same art
    native = size in (16, 24) and factor == 1.0 and tuned.is_file()
    if native and colours is not None and tuned.is_relative_to(modern.MODERN):
        problems = modern.violations(tuned.read_text(encoding="utf-8"), colours, size, tuned=True)
        if problems:
            raise ValueError(f"{tuned}: " + "; ".join(problems))
    heavy = theme.startswith("hst_modern") and modern.ink()["heavy16"]
    text = modern.harmonise((tuned if native else master).read_text(encoding="utf-8"), theme.endswith("_dark"))
    svg = snap_svg(text, size, native=native, heavy=heavy, factor=factor)
    return svg.replace("currentColor", colour).encode("utf-8")
