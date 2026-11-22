#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Which icons the menus show and how sharp they are at 100/125/150/200 %, HST against pristine LibreOffice.

Menu items take the small (16 px) icon of their command. This script lists every command of the
context menus (popupmenu/*.xml) and menu bars (menubar/menubar.xml) of Writer, Sheets, Slides and
Draw, read from the HST-patched tree over the pristine one, and resolves the icon each icon theme
shows for it:
  hst_classic  the default "Cổ điển": the HST overlay where it answers the request (hst_classic_icons),
               else the SVG Colibre;
  hst_modern   the option: the HST glyph where HST draws the command, else the SVG Colibre;
  colibre_png  pristine LibreOffice's PNG Colibre; colibre_svg its SVG Colibre.
Every icon is then rasterised through VCL's own SVG pipeline (hst_vcl_icon_raster, a headless
office of --instdir) along the paths a menu takes:
  win-100      Windows/VCL menu at 100 % and 125 % (CountDPIScaleFactor gives 100 below 121 DPI);
  win-150      150/175 %: SVG at 1.5, the HST @150 variant at 1.0, the PNG nearest-scaled (BmpScaleFlag::Fast);
  win-200      200 %: SVG at 2.0, PNG nearest-doubled;
  native-2x    macOS NSMenu and GTK menus on a 2x display: the 1x raster (Image::GetBitmap, CreateNSImage,
               GtkSalMenu::NativeSetItemIcon) stretched to 2x by the toolkit, modelled as bilinear.
The metric is the fringe share of hst_vcl_icon_raster (partly covered share of inked pixels; a crisp
1 px line has 0). Needs the instdir's Python (pyuno); run as root with an X display, like
check-hst-icon-sharpness.py. A JSON report goes to --json.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_gui  # noqa: E402
from hst_icon_frame_inventory import Resolver, Trees  # noqa: E402
from hst_vcl_icon_raster import fringe_share, median  # noqa: E402

MENU_DIRS = ("sw/uiconfig/swriter", "sc/uiconfig/scalc", "sd/uiconfig/simpress", "sd/uiconfig/sdraw")
PATHS = ("win-100", "win-150", "win-200", "native-2x")


def menu_files(trees):
    """Relative paths of every popup menu and menu bar, from both trees."""
    found = set()
    for base in MENU_DIRS:
        for root in filter(None, (trees.pristine, trees.patched)):
            for sub in ("popupmenu", "menubar"):
                directory = root / base / sub
                if directory.is_dir():
                    found |= {f"{base}/{sub}/{p.name}" for p in directory.glob("*.xml")}
    return sorted(found)


def menu_commands(trees):
    """{command: [menu files]} of the .uno: commands the menus show (parameters stripped)."""
    commands = {}
    for relative in menu_files(trees):
        for command in re.findall(r'menu:id="(\.uno:[A-Za-z0-9]+)', trees.text(relative)):
            commands.setdefault(command, []).append(relative)
    return commands


def scale_nearest(rows, factor):
    """BmpScaleFlag::Fast: nearest neighbour to round(size x factor)."""
    height, width = len(rows), len(rows[0])
    out_h, out_w = round(height * factor), round(width * factor)
    return [[rows[min(height - 1, int(y / factor))][min(width - 1, int(x / factor))] for x in range(out_w)]
            for y in range(out_h)]


def scale_bilinear(rows, factor):
    """A toolkit's smooth stretch of a bitmap (Quartz/Skia/cairo default filters), pixel centres aligned."""
    height, width = len(rows), len(rows[0])
    out = []
    for y in range(round(height * factor)):
        sy = min(max((y + 0.5) / factor - 0.5, 0), height - 1)
        y0, fy = int(sy), sy - int(sy)
        y1 = min(y0 + 1, height - 1)
        line = []
        for x in range(round(width * factor)):
            sx = min(max((x + 0.5) / factor - 0.5, 0), width - 1)
            x0, fx = int(sx), sx - int(sx)
            x1 = min(x0 + 1, width - 1)
            top = rows[y0][x0] * (1 - fx) + rows[y0][x1] * fx
            bottom = rows[y1][x0] * (1 - fx) + rows[y1][x1] * fx
            line.append(top * (1 - fy) + bottom * fy)
        out.append(line)
    return out


def png_rows(path):
    """Alpha rows (0..1) of a Colibre PNG, decoded with the standard library: RGBA, grey+alpha or
    palette (+tRNS) at 1-8 bits, no interlace (what Colibre ships). pyuno's Python has no Pillow."""
    import struct
    import zlib
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, chunks, header, trns = 8, [], None, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            chunks.append(body)
        elif kind == b"tRNS":
            trns = body
        pos += 12 + length
    width, height, depth, colour, _, _, interlace = header
    channels = {6: 4, 4: 2, 3: 1}.get(colour)
    if channels is None or interlace or (colour != 3 and depth != 8):
        raise ValueError(f"{path}: unsupported PNG layout {header}")
    bpp = max(1, channels * depth // 8)  # filter unit in bytes
    stride = (width * channels * depth + 7) // 8
    raw, rows, previous = zlib.decompress(b"".join(chunks)), [], bytearray(stride)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = previous[i], previous[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        if colour == 3:
            per_byte = 8 // depth
            indices = [(line[x // per_byte] >> (8 - depth * (x % per_byte + 1))) & ((1 << depth) - 1)
                       for x in range(width)]
            rows.append([(trns[i] if i < len(trns) else 255) / 255.0 for i in indices])
        else:
            rows.append([line[x * channels + channels - 1] / 255.0 for x in range(width)])
        previous = line
    return rows


class Icons:
    """SVG/PNG bytes of each theme's answer to a 16 px command request."""

    def __init__(self, resolver):
        self.r = resolver

    def classic(self, request):
        target = self.r.classic_links.get(request) or self.r.classic_links.get(request[:-4] + ".svg")
        if target:
            return "hst", self.r.classic_files[target], self.r.classic_files.get(target[:-4] + "@150.svg")
        return self.colibre(request)

    def modern(self, request):
        stem = request[:-4]
        target = self.r.hst_links.get(request) or self.r.hst_links.get(stem + ".svg") or (
            stem + ".svg" if stem + ".svg" in self.r.hst_files else None)
        if target:
            return "hst", self.r.hst_files[target], self.r.hst_files.get(target[:-4] + "@150.svg")
        return self.colibre(request)

    def colibre(self, request):
        real = self.r.colibre_file(request)
        if not real:
            return None, None, None
        return "colibre", (self.r.icon_themes / "colibre_svg" / real).read_bytes(), None

    def colibre_png(self, request):
        stem = str(PurePosixPath(request).with_suffix(""))
        links = self.r.colibre.links
        real = links.get(stem + ".png") or request
        path = self.r.icon_themes / "colibre" / real
        return path if path.is_file() else None


def measure_svg(ctx, raster, svg, variant150, name):
    """fringe per menu path of one SVG icon (16 px logical)."""
    _, _, one = raster.rasterise(ctx, svg, 1.0, name)
    _, _, two = raster.rasterise(ctx, svg, 2.0, name)
    if variant150 is not None:
        _, _, half = raster.rasterise(ctx, variant150, 1.0, name)
    else:
        _, _, half = raster.rasterise(ctx, svg, 1.5, name)
    return {"win-100": fringe_share(one), "win-150": fringe_share(half), "win-200": fringe_share(two),
            "native-2x": fringe_share(scale_bilinear(one, 2.0)), "size": [len(one[0]), len(one)]}


def measure_png(path):
    one = png_rows(path)
    return {"win-100": fringe_share(one), "win-150": fringe_share(scale_nearest(one, 1.5)),
            "win-200": fringe_share(scale_nearest(one, 2.0)), "native-2x": fringe_share(scale_bilinear(one, 2.0)),
            "size": [len(one[0]), len(one)]}


def summarise(rows, theme):
    summary = {}
    for source in sorted({r[theme]["source"] for r in rows if r[theme]["source"]}):
        group = [r[theme] for r in rows if r[theme]["source"] == source]
        summary[source] = {"icons": len(group)}
        for path in PATHS:
            values = [g[path] for g in group if g.get(path) is not None]
            summary[source][path] = round(median(values), 3) if values else None
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lo-tree", type=Path, required=True)
    parser.add_argument("--patched-tree", type=Path)
    parser.add_argument("--instdir", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=22197)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r":\d+", args.display):
        parser.error("--display must look like :97")
    os.environ["DISPLAY"] = args.display
    trees = Trees(args.lo_tree, args.patched_tree)
    commands = menu_commands(trees)
    resolver = Resolver(args.lo_tree / "icon-themes")
    icons = Icons(resolver)
    hst_gui.setup_uno(str(args.instdir.resolve()))
    import hst_vcl_icon_raster as raster
    office = hst_gui.Office(str(args.instdir.resolve()), str(args.work.resolve() / "menu-icons"), args.port,
                            display=args.display, extra_args=["--headless"])
    rows = []
    try:
        office.start()
        for command in sorted(commands):
            request = "cmd/sc_" + command[5:].lower() + ".png"
            row = {"command": command, "menus": commands[command], "request": request}
            for theme, pick in (("hst_classic", icons.classic), ("hst_modern", icons.modern),
                                ("colibre_svg", icons.colibre)):
                source, svg, variant = pick(request)
                row[theme] = {"source": source}
                if svg:
                    row[theme].update(measure_svg(office.ctx, raster, svg, variant, request))
            png = icons.colibre_png(request)
            row["colibre_png"] = {"source": "colibre_png" if png else None, **(measure_png(png) if png else {})}
            rows.append(row)
    finally:
        office.stop()
    report = {"commands": len(rows),
              "menu_files": len(menu_files(trees)),
              "summary": {theme: summarise(rows, theme) for theme in ("hst_classic", "hst_modern", "colibre_svg",
                                                                       "colibre_png")},
              "classic_hst_in_menus": sorted(r["command"] for r in rows if r["hst_classic"]["source"] == "hst"),
              "rows": rows}
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("commands", "menu_files", "summary", "classic_hst_in_menus")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
