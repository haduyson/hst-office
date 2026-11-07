#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime sharpness check of the HST icon themes, measured on VCL's own rasters.

The metric is the fringe share: of the inked pixels of an icon (alpha >= 8 %), the share that is
only partly covered (alpha < 80 %). A pixel-snapped glyph scores near 0; the unsnapped beta.5
glyphs scored a median of 0.68 at 16 px. Two modes, both through VCL, never rsvg:

  cache      Start the product GUI (GTK3 on an existing X display, GDK_SCALE 1 and 2) with a
             fresh profile, open Writer, Sheets and Slides so their ribbons rasterise, then read
             the PNGs VCL wrote to <profile>/cache/<theme>/<scale>/. Checks the median fringe
             share per logical size, that 200 % rasters are twice the size (HiDPI rasterised, not
             stretched), that fallbacks come from the SVG Colibre rather than the PNG one, and
             that the cache directories carry the product version stamp.
  rasterise  Rasterise every command icon of images_<theme>.zip through VCL's SVG pipeline in a
             headless instance (com.sun.star.graphic.SvgTools + Primitive2DTools, the calls of
             vcl::bitmap::loadFromSvg) at each scale. Full coverage, no GUI needed.

Exit status 1 when a median exceeds --max-median (default 0.35) at 16 or 24 px, or a cache
contract fails. A JSON report goes to --json.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_gui  # noqa: E402
from hst_vcl_icon_raster import logical_size, summarise  # noqa: E402

STAMP = "hst-icon-cache-version"


def run_rasterise(args):
    hst_gui.setup_uno(str(args.instdir))
    import hst_vcl_icon_raster as raster
    archive = args.archive or args.instdir / "share/config" / f"images_{args.theme}.zip"
    with zipfile.ZipFile(archive) as z:
        names = sorted(n for n in z.namelist() if n.startswith("cmd/") and n.endswith(".svg") and logical_size(n))
        data = {n: z.read(n) for n in names}
    office = hst_gui.Office(str(args.instdir), str(args.work / f"rasterise-{args.theme}"), args.port,
                           display=args.display, extra_args=["--headless"])
    report, failures = {"mode": "rasterise", "theme": args.theme, "archive": str(archive), "scales": {}}, []
    try:
        office.start()
        for scale in args.scales:
            rows = []
            for name in names:
                width, height, alpha = raster.rasterise(office.ctx, data[name], scale, name)
                size = logical_size(name)
                if (width, height) != (round(size * scale), round(size * scale)):
                    failures.append(f"{name} at {scale}x is {width}x{height}")
                rows.append({"name": name, "size": size, "fringe": raster.fringe_share(alpha)})
            summary, failed = summarise(rows, args.max_median)
            report["scales"][str(scale)] = summary
            failures += [f"{scale}x: {f}" for f in failed]
    finally:
        office.stop()
    return report, failures


def read_cache(profile, theme, scale_percent):
    """Rows of the rasters VCL cached for `theme` at `scale_percent`."""
    import hst_vcl_icon_raster as raster
    rows = []
    for base in (profile / "cache", profile / "user" / "cache"):
        directory = base / theme / str(scale_percent)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.png")):
            name = path.relative_to(directory).as_posix()
            size = logical_size(name)
            if size is None:
                continue
            alpha = raster.png_alpha_rows(path)
            rows.append({"name": name, "size": size, "fringe": raster.fringe_share(alpha),
                         "pixels": [len(alpha[0]) if alpha else 0, len(alpha)]})
    return rows


def cache_dirs(profile):
    found = {}
    for base in (profile / "cache", profile / "user" / "cache"):
        if base.is_dir():
            for theme in sorted(p for p in base.iterdir() if p.is_dir()):
                # Icon themes only: <theme>/<scale>[-dark]/...; other cache users keep their own layout.
                if not any(re.fullmatch(r"\d+(?:-dark)?", v.name) for v in theme.iterdir() if v.is_dir()):
                    continue
                found[theme.name] = {"variants": sorted(p.name for p in theme.iterdir() if p.is_dir()),
                                     "stamp": (theme / STAMP).read_text() if (theme / STAMP).is_file() else None}
    return found


def run_cache(args):
    if os.geteuid() == 0:
        user = os.environ.get("HST_BUILD_USER", "hstbuild")
        args.work.mkdir(parents=True, exist_ok=True)
        subprocess.run(["chown", "-R", user, str(args.work)], check=True)
        if args.json:  # the report is written after the privileges are dropped
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.touch()
            subprocess.run(["chown", user, str(args.json)], check=True)
        os.execvp("runuser", ["runuser", "-u", user, "--", "env", f"HST_BUILD_USER={user}", f"DISPLAY={args.display}",
                              "dbus-run-session", "--", sys.executable, *sys.argv])
    hst_gui.setup_uno(str(args.instdir))
    dark = args.theme.endswith("_dark")
    config = [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2" if dark else "1"),
              ("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]
    report, failures = {"mode": "cache", "theme": args.theme, "scales": {}}, []
    for scale in args.scales:
        workdir = args.work / f"cache-{args.theme}-{int(scale * 100)}"
        office = hst_gui.Office(str(args.instdir), str(workdir), args.port, display=args.display,
                               nodefault=False, config=config, extra_args=["--writer"],
                               env={"GTK_THEME": "Adwaita:dark" if dark else "Adwaita",
                                    "GDK_SCALE": str(int(scale)), "GDK_DPI_SCALE": "1"})
        try:
            office.start()
            for url in ("private:factory/scalc", "private:factory/simpress"):
                office.load(url)
            time.sleep(args.settle)
        finally:
            office.stop()
        profile = workdir / "profile"
        percent = int(round(scale * 100))
        rows = read_cache(profile, args.theme, percent)
        dirs = cache_dirs(profile)
        summary, failed = summarise(rows, args.max_median)
        report["scales"][str(scale)] = {"rasters": len(rows), "sizes": summary, "cache_dirs": dirs}
        failures += [f"{scale}x: {f}" for f in failed]
        if len(rows) < args.min_rasters:
            failures.append(f"{scale}x: only {len(rows)} {args.theme} rasters cached (expected >= {args.min_rasters})")
        wrong = [r["name"] for r in rows if r["pixels"] != [round(r["size"] * scale)] * 2]
        if wrong:
            failures.append(f"{scale}x: {len(wrong)} rasters are not {scale}x their logical size, e.g. {wrong[:3]}")
        if percent > 100 and "colibre" in dirs and str(percent) in dirs["colibre"]["variants"]:
            failures.append(f"{scale}x: fallbacks were scaled from the PNG Colibre (cache/colibre/{percent})")
        unstamped = [name for name, info in dirs.items() if not info["stamp"]]
        if unstamped:
            failures.append(f"{scale}x: icon cache directories without a version stamp: {unstamped}")
    return report, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("cache", "rasterise"))
    parser.add_argument("--instdir", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=22197)
    parser.add_argument("--theme", default="hst", choices=("hst", "hst_dark", "hst_modern", "hst_modern_dark"))
    parser.add_argument("--archive", type=Path, help="rasterise mode: an images_<theme>.zip other than the instdir's")
    parser.add_argument("--scales", default="1,2", type=lambda v: [float(x) for x in v.split(",")])
    parser.add_argument("--max-median", type=float, default=0.35)
    parser.add_argument("--min-rasters", type=int, default=50, help="cache mode: fewer cached rasters fail")
    parser.add_argument("--settle", type=float, default=8.0, help="cache mode: seconds for the ribbons to paint")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r":\d+", args.display):
        parser.error("--display must look like :97")
    os.environ["DISPLAY"] = args.display
    args.instdir = args.instdir.resolve()
    args.work = args.work.resolve()
    report, failures = (run_cache if args.mode == "cache" else run_rasterise)(args)
    report["failures"] = failures
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n")
    print(text)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
