# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the HASON TECH banner is visible in every app and every user interface (gtk3, real GUI).

Usage: python3 tests/runtime/check-banner-everywhere.py --instdir DIR [--display :171] [--out DIR]
           [--apps writer,calc,impress,draw,pdf] [--sizes 1366x768,1920x1080] [--shots DIR]

Owner decision 14/11/2026 (docs/BANNERS.md, "Every window"): no user interface hides the banner. Per app
(Writer, Sheets, Slides, Draw) every user interface the app offers is chosen in turn (.uno:ToolbarMode, as
View > User Interface does), and at every window size the screenshot must show exactly one banner:
  - exactly one visible accessible link named "<name> — <tagline>" (AT-SPI, as a screen reader finds it);
  - at least 260 x 75 logical px, inside the window, in its top chrome (above the document's middle);
  - drawn as one of the bundled artworks (recognised in the screenshot, never a text card).
HST PDF: the viewer's BannerScreen (HSTPdfInfo) is at least 260 x 75 and shows a bundled artwork.
Writes results.json and one screenshot per case (--shots: also copied there as <app>-<mode>-<size>.png);
exit 1 when any case has no banner, more than one, a small one or one that is not the artwork.
The X display must already run (this script never starts or stops it).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_banner_probe as probe  # noqa: E402
from ribbon_banner_run import geometry, xdo  # noqa: E402

NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides", "draw": "HST Draw"}
# the user interfaces each app offers in View > User Interface (officecfg ToolbarMode.xcu, experimental ones aside)
MODES = {
    "writer": ("Default", "Single", "Sidebar", "notebookbar.ui", "notebookbar_compact.ui",
               "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui"),
    "calc": ("Default", "Single", "Sidebar", "notebookbar.ui", "notebookbar_compact.ui",
             "notebookbar_groupedbar_compact.ui"),
    "impress": ("Default", "Single", "notebookbar.ui", "notebookbar_compact.ui",
                "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui"),
    "draw": ("Default", "notebookbar.ui", "notebookbar_compact.ui", "notebookbar_groupedbar_compact.ui",
             "notebookbar_single.ui"),
}
MIN_W, MIN_H = 260, 75


def mode_label(mode):
    return mode.replace("notebookbar_", "").replace("notebookbar", "tabbed").replace(".ui", "")


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def judge(boxes, frame, shot, catalogue):
    """(ok, detail) for the visible banner boxes [x, y, w, h] of one screenshot of the window frame."""
    if len(boxes) != 1:
        return False, f"{len(boxes)} banners visible"
    x, y, w, h = boxes[0]
    fx, fy, fw, fh = frame
    if w < MIN_W - 1 or h < MIN_H - 1:
        return False, f"banner {w}x{h} smaller than {MIN_W}x{MIN_H}"
    if x < fx or y < fy or x + w > fx + fw or y + h > fy + fh // 2:
        return False, f"banner {boxes[0]} outside the window's top chrome {frame}"
    ident, best, second = probe.recognise(shot, boxes[0], catalogue, 1)
    if ident is None:
        return False, f"banner {boxes[0]} is not a bundled artwork (score {best}, next {second})"
    return True, f"{ident} at {boxes[0]}"


def visible_boxes(frame):
    fx, fy, fw, fh = frame
    boxes = []
    for node in probe.banner_nodes():
        record = probe.describe(node)
        if " — " not in (record["name"] or ""):
            continue
        x, y, w, h = record["box"]
        if w > 0 and h > 0 and x < fx + fw and y < fy + fh and x + w > fx and y + h > fy:
            boxes.append(record["box"])
    return boxes


def record(results, shots, case, path, ok, detail):
    results.append({"case": case, "status": "PASS" if ok else "FAIL", "detail": detail, "shot": path})
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}", flush=True)
    if shots:
        os.makedirs(shots, exist_ok=True)
        shutil.copy(path, os.path.join(shots, f"{case}.png"))


def run_app(args, app, catalogue, results):
    work = os.path.join(args.out, app)
    office = hst_gui.Office(args.instdir, work, hst_gui.free_port(), display=args.display,
                            extra_args=[f"--{app}"], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    try:
        time.sleep(8)
        office.close_welcome()
        wid = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
        xdo(args.display, "windowmove", wid, "0", "0")
        frame = office.desktop().getCurrentFrame()
        for mode in MODES[app]:
            office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", mode),))
            time.sleep(4)
            for width, height in args.sizes:
                xdo(args.display, "windowsize", wid, str(width), str(height))
                time.sleep(4)
                box = geometry(args.display, wid)
                case = f"{app}-{mode_label(mode)}-{width}x{height}"
                path = os.path.join(work, f"{case}.png")
                office.screenshot(path)
                ok, detail = judge(visible_boxes(box), box, path, catalogue)
                record(results, args.shots, case, path, ok, detail)
        # back to the tabbed ribbon, so a later run starts as users do
        office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", "notebookbar.ui"),))
        time.sleep(2)
    finally:
        office.stop()


def run_pdf(args, catalogue, results):
    import pdf_selection_highlight as selection
    from pdf_viewer_uno import info, open_viewer
    work = os.path.join(args.out, "pdf")
    os.makedirs(work, exist_ok=True)
    pdf = selection.write(os.path.join(work, "banner.pdf"))
    office = hst_gui.Office(args.instdir, os.path.join(work, "office"), hst_gui.free_port(), display=args.display)
    office.start()
    try:
        frame, _ = open_viewer(office, pdf)
        time.sleep(2)
        wid = subprocess.run(["xdotool", "search", "--name", "HST PDF"], capture_output=True, text=True,
                             env=dict(os.environ, DISPLAY=args.display), check=True).stdout.split()[-1]
        xdo(args.display, "windowmove", wid, "0", "0")
        for width, height in args.sizes:
            xdo(args.display, "windowsize", wid, str(width), str(height))
            time.sleep(4)
            box = geometry(args.display, wid)
            case = f"pdf-toolbar-{width}x{height}"
            path = os.path.join(work, f"{case}.png")
            hst_gui.screenshot(path, args.display)
            banner = info(office, frame).get("BannerScreen")
            boxes = [list(banner)] if banner else []
            ok, detail = judge(boxes, box, path, catalogue)
            record(results, args.shots, case, path, ok, detail)
        frame.close(True)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":171")
    parser.add_argument("--out", default="tests/output/banner-everywhere")
    parser.add_argument("--apps", default="writer,calc,impress,draw,pdf")
    parser.add_argument("--sizes", default="1366x768,1920x1080")
    parser.add_argument("--shots", default=None)
    args = parser.parse_args()
    args.sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes.split(",")]
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    catalogue, _ = probe.items(args.instdir)
    results = []
    for app in args.apps.split(","):
        try:
            if app == "pdf":
                run_pdf(args, catalogue, results)
            else:
                run_app(args, app, catalogue, results)
        except Exception as error:  # noqa: BLE001 - one app failing must not hide the others
            results.append({"case": app, "status": "FAIL", "detail": repr(error)[:400]})
            print(f"FAIL  {app}  {error!r}", flush=True)
    ok = bool(results) and all(r["status"] == "PASS" for r in results)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
    print(f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} cases pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
