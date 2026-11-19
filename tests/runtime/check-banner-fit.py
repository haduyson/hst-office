# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the HASON TECH banner on the ribbon is exactly its artwork: no letterbox, no filler band, no padding.

Usage: python3 tests/runtime/check-banner-fit.py --instdir DIR [--display :171] [--out DIR] [--shots DIR]
           [--apps writer,calc,impress] [--scales 1.0,1.25] [--themes light,dark] [--size 1485x900]

Owner request 19/11/2026: the banner fits snugly. Per app (Tabbed ribbon, the default user interface), per scale
(125 % is the desktop's font scale, Xft.dpi 120 set on the display with xrdb, as check-start-center-redesign.py
does) and per theme (the office's own appearance setting), in a window of --size:
  - exactly one visible banner link "<name> — <tagline>" (AT-SPI); its box is its allocation;
  - the box has the ratio of the bundled artwork it shows (its width is the artwork's at the box's height, within a
    pixel of rounding): a wider box is a filler band, a taller one a letterbox;
  - the box shows that artwork edge to edge: the screenshot inside the box matches the artwork scaled to the whole
    box (no inset, no background around it);
  - the ribbon's body is one surface behind the banner: left of it and right of it the screenshot shows the body's
    colour (the most common colour of the body beside the groups), not the tab control's own background;
  - on every tab of the ribbon (each one opened by a click on it; Tệp tin opens the File panel and is left out) the
    banner stands flush with the right end of the ribbon's content area: its right edge is the window's right edge
    less the 8 px margin, the same box on every tab (owner decision 19/11/2026), the free room left of it.
Writes results.json and one screenshot per case (--shots: also copied there as <app>-<scale>-<theme>.png).
The X display must already run (this script never starts or stops it). Run as root, it runs itself again as the
build user under dbus-run-session (AT-SPI needs a session bus). Exit 1 when a case fails.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from PIL import Image
import numpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_banner_probe as probe  # noqa: E402
import ribbon_tabs_gui as tabs_gui  # noqa: E402
from banner_everywhere_cases import NAMES, visible_boxes  # noqa: E402
from ribbon_banner_run import geometry, xdo  # noqa: E402

MATCH = probe.MATCH  # mean absolute RGB difference of a matching artwork
RIGHT_MARGIN = 8  # px between the banner and the window's right edge (NotebookbarTabControl::HstBannerRight)
SKIP_TABS = ("Tệp tin",)  # opens the File panel


def edge_to_edge(shot_path, box, art_path):
    """Mean absolute RGB difference between the box in the screenshot and the artwork scaled to the whole box."""
    shot = Image.open(shot_path).convert("RGB")
    x, y, w, h = box
    art = Image.open(art_path).convert("RGBA")
    crop = shot.crop((x, y, x + w, y + h))
    expected = Image.alpha_composite(Image.new("RGBA", (w, h), (255, 255, 255, 255)),
                                     art.resize((w, h), Image.LANCZOS)).convert("RGB")
    return float(numpy.abs(numpy.asarray(crop, dtype=float) - numpy.asarray(expected, dtype=float)).mean())


def judge(box, shot_path, catalogue):
    """(ok, detail) for the one visible banner box [x, y, w, h] of a screenshot."""
    x, y, w, h = box
    scores = []
    for item in catalogue:
        art = item["art"][1]
        with Image.open(art) as image:
            ratio_w = round(h * image.width / image.height)
        scores.append((edge_to_edge(shot_path, box, art), item["id"], ratio_w))
    best, ident, ratio_w = min(scores)
    bad = []
    if abs(w - ratio_w) > 1:
        bad.append(f"box {w}x{h} is not the artwork's ratio (width {ratio_w} at height {h})")
    if best > MATCH:
        bad.append(f"the box does not show an artwork edge to edge (best {ident}: {best:.1f} > {MATCH})")
    return not bad, "; ".join(bad) or f"{ident} fills {w}x{h} edge to edge ({best:.1f})"


def flush_right(box, frame):
    """True when the banner box ends RIGHT_MARGIN px before the window's right edge (within a pixel)."""
    return abs((box[0] + box[2]) - (frame[0] + frame[2] - RIGHT_MARGIN)) <= 1


def flush_right_on_every_tab(args, frame):
    """(ok, detail): the banner is flush right, at one place, on every tab of the ribbon."""
    names = [n for n in tabs_gui.visible_names() if n not in SKIP_TABS]
    if not names:
        return False, "no ribbon tabs found"
    seen, bad = {}, []
    for name in names:
        tabs_gui.open_tab(args.display, name)
        time.sleep(1.5)
        boxes = visible_boxes(frame)
        if len(boxes) != 1:
            bad.append(f"{name}: {len(boxes)} banners")
            continue
        seen[name] = tuple(boxes[0])
        if not flush_right(boxes[0], frame):
            bad.append(f"{name}: right edge {boxes[0][0] + boxes[0][2]}, expected {frame[0] + frame[2] - RIGHT_MARGIN}")
    if len(set(seen.values())) > 1:
        bad.append(f"the banner moves between tabs: {sorted(set(seen.values()))}")
    if tabs_gui.visible_names():
        tabs_gui.open_tab(args.display, names[0])
    return not bad, "; ".join(bad) or f"{len(seen)} tabs, banner at {next(iter(seen.values()))}"


def body_continuous(shot_path, box, frame):
    """(ok, detail): the colour just left and just right of the banner is the body's own colour."""
    shot = Image.open(shot_path).convert("RGB")
    x, y, w, h = box
    region = numpy.asarray(shot.crop((frame[0] + 10, y, max(frame[0] + 11, x - 8), y + h)), dtype=int).reshape(-1, 3)
    colours, counts = numpy.unique(region, axis=0, return_counts=True)
    body = tuple(int(v) for v in colours[counts.argmax()])
    mid = y + h // 2
    beside = {"left": shot.getpixel((x - 4, mid)), "right": shot.getpixel((frame[0] + frame[2] - 3, mid))}
    off = {k: v for k, v in beside.items() if max(abs(a - b) for a, b in zip(v, body)) > 6}
    return not off, (f"body {body}, beside the banner {off}" if off else f"body {body} on both sides")


def set_scale(display, scale):
    subprocess.run(["xrdb", "-display", display, "-merge", "-"], input="Xft.dpi: %d\n" % round(96 * scale),
                   text=True, check=False)


def run_case(args, app, scale, theme, catalogue, results):
    case = f"{app}-{round(scale * 100)}-{theme}"
    work = os.path.join(args.out, case)
    appearance = ("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                  {"light": "1", "dark": "2"}[theme])
    set_scale(args.display, scale)
    office = hst_gui.Office(args.instdir, work, hst_gui.free_port(), display=args.display,
                            extra_args=[f"--{app}"], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"), appearance],
                            env={"GTK_THEME": "Adwaita:dark" if theme == "dark" else "Adwaita"})
    office.start()
    try:
        time.sleep(8)
        office.close_welcome()
        wid = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
        xdo(args.display, "windowmove", wid, "0", "0")
        xdo(args.display, "windowsize", wid, str(args.size[0]), str(args.size[1]))
        time.sleep(5)
        frame = geometry(args.display, wid)
        path = os.path.join(work, f"{case}.png")
        ok, detail = False, "no shot"
        for _attempt in range(3):  # a shot taken during the 300 ms cross-fade shows two cards
            office.screenshot(path)
            boxes = visible_boxes(frame)
            if len(boxes) != 1:
                ok, detail = False, f"{len(boxes)} banners visible"
            else:
                ok, detail = judge(boxes[0], path, catalogue)
                same, surface = body_continuous(path, boxes[0], frame)
                ok = ok and same
                detail = f"{detail} at {boxes[0]}; {surface}"
            if ok:
                break
            time.sleep(1.5)
        results.append({"case": case, "status": "PASS" if ok else "FAIL", "detail": detail, "shot": path})
        print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}", flush=True)
        if args.shots:
            os.makedirs(args.shots, exist_ok=True)
            shutil.copy(path, os.path.join(args.shots, f"{case}.png"))
        ok, detail = flush_right_on_every_tab(args, frame)
        results.append({"case": f"{case}-tabs", "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {case}-tabs  {detail}", flush=True)
    finally:
        office.stop()
        set_scale(args.display, 1.0)


def private_atspi_bus():
    """This run's own AT-SPI bus, as check-banner-everywhere.py sets it up (that file's name is not importable)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "banner_everywhere", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-banner-everywhere.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.private_atspi_bus()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":171")
    parser.add_argument("--out", default="tests/output/banner-fit")
    parser.add_argument("--shots", default=None)
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--scales", default="1.0,1.25")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--size", default="1485x900")
    args = parser.parse_args()
    if os.geteuid() == 0:  # as the build user under a session bus of its own (AT-SPI needs one)
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    args.size = tuple(int(v) for v in args.size.split("x"))
    address, launcher = private_atspi_bus()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", AT_SPI_BUS_ADDRESS=address)
    try:
        os.makedirs(args.out, exist_ok=True)
        hst_gui.setup_uno(args.instdir)
        catalogue, _ = probe.items(args.instdir)
        results = []
        for app in args.apps.split(","):
            for scale in (float(s) for s in args.scales.split(",")):
                for theme in args.themes.split(","):
                    try:
                        run_case(args, app, scale, theme, catalogue, results)
                    except Exception as error:  # noqa: BLE001 - one case failing must not hide the others
                        results.append({"case": f"{app}-{scale}-{theme}", "status": "FAIL", "detail": repr(error)})
                        print(f"FAIL  {app}-{scale}-{theme}  {error!r}", flush=True)
        ok = bool(results) and all(r["status"] == "PASS" for r in results)
        with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
            json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
        print(f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} cases pass")
        return 0 if ok else 1
    finally:
        try:
            os.kill(launcher, signal.SIGTERM)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    sys.exit(main())
