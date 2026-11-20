#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Review sheet and measurements of the HST frame glyphs (icon-themes-src/hst-modern/glyphs/stage-frame).

For every master stage-frame/<name>.svg (24-unit grid) and its hand-tuned 16 px master
stage-frame/16/<name>.svg, this builds the files the icon themes would ship, with the same
pipeline as hst_icon_glyph.glyph_svg: Colibre-harmonised colours (light and dark ink of
metadata/ink.json), pixel snapping at 16/24/32 px, the hand-tuned master at 16 px and 100 %, and
the natively snapped display-scale variants @150/@250. It then writes to --out:

  shipped/<theme>/cmd/{sc_,lc_,32/}<name>[@150|@250].svg   the shipped SVGs (hst = light, hst_dark = dark)
  images_frame_<theme>.zip                                 the 100 % files as an icon archive, for
                                                           tests/runtime/check-hst-icon-sharpness.py rasterise
  measurements.json                                        stroke/ink/fringe/overflow per file
                                                           (check-hst-icon-weight.measure) and the spec
                                                           violations of every master
  --sheet PNG                                              light and dark panels: 16/24/32 px at 100 %, the
                                                           @150/@250 variants, 4x zooms, and the Colibre icon
                                                           of the same frame element where one exists

Rasters are drawn with rsvg-convert: the shipped files are filled outlines on whole pixels, so any
rasteriser that follows the SVG pixel convention (VCL with the HST patches, rsvg) gives the same
pixels. Needs NumPy, Pillow and rsvg-convert. Exit 1 when a master breaks the spec.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hst_modern_icons as modern  # noqa: E402
from hst_icon_glyph import FACTORS, variant_key  # noqa: E402
from hst_icon_snap import snap_svg  # noqa: E402

STAGE = modern.MODERN / "glyphs/stage-frame"
THEMES = {"hst": False, "hst_dark": True}
SIZES = (16, 24, 32)
PREFIX = {16: "cmd/sc_", 24: "cmd/lc_", 32: "cmd/32/"}
BACKGROUND = {"hst": (247, 248, 250), "hst_dark": (31, 34, 40)}
TEXT = {"hst": (40, 44, 52), "hst_dark": (220, 224, 230)}
# Frame glyph -> its element in metadata/frame-inventory.json, whose Colibre icon the sheet shows beside it.
INVENTORY_ELEMENT = {
    "saveas": "backstage-navsaveas",
    "sidebar-property": "sidebar-deck-PropertyDeck",
    "sidebar-style": "sidebar-deck-StyleListDeck",
    "sidebar-navigator": "sidebar-deck-NavigatorDeck",
    "signature-status": "statusbar-signature",
}


def colibre_references():
    """{glyph: Colibre SVG path relative to icon-themes/colibre_svg} from the frame inventory."""
    inventory = json.loads((modern.MODERN / "metadata/frame-inventory.json").read_text(encoding="utf-8"))
    elements = {e["id"]: e for e in inventory["elements"]}
    result = {}
    for glyph, element in INVENTORY_ELEMENT.items():
        images = elements[element]["images"]
        if images and images[0]["colibre_svg"]:
            result[glyph] = images[0]["colibre_svg"]
    return result


def load_weight_check():
    spec = importlib.util.spec_from_file_location("hst_weight_check", HERE / "check-hst-icon-weight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shipped(name, theme):
    """{archive name: SVG text} of one frame glyph in `theme`, as hst_icon_glyph would ship it."""
    dark, ink = THEMES[theme], modern.ink()["dark" if THEMES[theme] else "light"]
    master = (STAGE / f"{name}.svg").read_text(encoding="utf-8")
    tuned_path = STAGE / "16" / f"{name}.svg"
    files = {}
    for size in SIZES:
        key = f"{PREFIX[size]}{name}.svg"
        native = size == 16 and tuned_path.is_file()
        text = modern.harmonise(tuned_path.read_text(encoding="utf-8") if native else master, dark)
        files[key] = snap_svg(text, size, native=native).replace("currentColor", ink)
        for percent, factor in FACTORS.items():
            files[variant_key(key, percent)] = snap_svg(modern.harmonise(master, dark), size,
                                                        factor=factor).replace("currentColor", ink)
    return files


def violations(name):
    colours = modern.palette()
    problems = {f"{name}.svg": modern.violations((STAGE / f"{name}.svg").read_text(encoding="utf-8"), colours)}
    tuned = STAGE / "16" / f"{name}.svg"
    if tuned.is_file():
        problems[f"16/{name}.svg"] = modern.violations(tuned.read_text(encoding="utf-8"), colours, 16, tuned=True)
    return {k: v for k, v in problems.items() if v}


def rasterise(svg_text, pixels):
    """RGBA image of an SVG at `pixels` x `pixels` via rsvg-convert."""
    result = subprocess.run(["rsvg-convert", "-w", str(pixels), "-h", str(pixels), "-f", "png"],
                            input=svg_text.encode("utf-8"), capture_output=True, check=True)
    return Image.open(io.BytesIO(result.stdout)).convert("RGBA")


def colibre_svg(lo_tree, relative, theme):
    if not lo_tree:
        return None
    path = lo_tree / "icon-themes" / ("colibre_dark_svg" if THEMES[theme] else "colibre_svg") / relative
    return path.read_text(encoding="utf-8") if path.is_file() else None


def panel(names, files, theme, lo_tree, font):
    """One theme's panel of the sheet."""
    references = colibre_references()
    columns = [("16", 16, 16, 1), ("24", 24, 24, 1), ("32", 32, 32, 1), ("16@150", 16, 24, 1), ("24@150", 24, 36, 1),
               ("32@150", 32, 48, 1), ("16@250", 16, 40, 1), ("24@250", 24, 60, 1), ("16 x4", 16, 16, 4),
               ("24 x4", 24, 24, 4), ("Colibre 16/24", 0, 0, 1)]
    cell = [max(64, px * zoom + 16) for _, _, px, zoom in columns[:-1]] + [64]
    label_width, row_height, header = 150, 112, 40
    width = label_width + sum(cell) + 12
    image = Image.new("RGB", (width, header + row_height * len(names) + 10), BACKGROUND[theme])
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), "Light (hst)" if theme == "hst" else "Dark (hst_dark)", fill=TEXT[theme], font=font)
    x = label_width
    for (title, *_), w in zip(columns, cell):
        draw.text((x + 4, 24), title, fill=TEXT[theme], font=font)
        x += w
    for row, name in enumerate(names):
        y = header + row * row_height
        draw.text((10, y + row_height // 2 - 6), name, fill=TEXT[theme], font=font)
        x = label_width
        for (title, size, pixels, zoom), w in zip(columns, cell):
            if size:
                key = f"{PREFIX[size]}{name}.svg"
                if "@" in title:
                    key = variant_key(key, int(title.split("@")[1]))
                icon = rasterise(files[theme][name][key], pixels)
                if zoom > 1:
                    icon = icon.resize((pixels * zoom, pixels * zoom), Image.NEAREST)
                image.paste(icon, (x + 4, y + (row_height - icon.height) // 2), icon)
            else:
                reference = colibre_svg(lo_tree, references[name], theme) if name in references else None
                if reference:
                    for offset, pixels in ((0, 16), (22, 24)):
                        icon = rasterise(reference, pixels)
                        image.paste(icon, (x + 4 + offset, y + (row_height - icon.height) // 2), icon)
                else:
                    draw.text((x + 4, y + row_height // 2 - 6), "none", fill=TEXT[theme], font=font)
            x += w
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="directory for shipped files, archives, measurements")
    parser.add_argument("--sheet", type=Path, help="review sheet PNG")
    parser.add_argument("--lo-tree", type=Path, help="pristine LibreOffice tree, for the Colibre reference column")
    args = parser.parse_args()
    names = sorted(p.stem for p in STAGE.glob("*.svg"))
    if not names:
        sys.exit(f"no masters in {STAGE}")
    problems = {}
    for name in names:
        problems.update(violations(name))
    if problems:
        print(json.dumps(problems, indent=1))
        sys.exit("masters break the spec; fix them first")
    weight = load_weight_check()
    files = {theme: {name: shipped(name, theme) for name in names} for theme in THEMES}
    report = {"masters": names, "violations": problems, "themes": {}}
    for theme in THEMES:
        flat = {key: text for name in names for key, text in files[theme][name].items()}
        for key, text in flat.items():
            path = args.out / "shipped" / theme / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        with zipfile.ZipFile(args.out / f"images_frame_{theme}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for key in sorted(k for k in flat if "@" not in k):
                archive.writestr(key, flat[key])
        ink = modern.ink()["dark" if THEMES[theme] else "light"]
        icons = weight.measure_theme({k: v.encode("utf-8") for k, v in flat.items()}, ink)
        report["themes"][theme] = icons
    (args.out / "measurements.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.sheet:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 12)
        except OSError:
            font = ImageFont.load_default()
        panels = [panel(names, files, theme, args.lo_tree, font) for theme in THEMES]
        sheet = Image.new("RGB", (max(p.width for p in panels), sum(p.height for p in panels)), (255, 255, 255))
        y = 0
        for part in panels:
            sheet.paste(part, (0, y))
            y += part.height
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.sheet, optimize=True)
        print(f"sheet: {args.sheet}")
    print(f"{len(names)} glyphs; measurements: {args.out / 'measurements.json'}")


if __name__ == "__main__":
    main()
