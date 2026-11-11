#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF text selection keeps the selected text readable: a light highlight, glyphs much darker than it.

Opens a synthetic text page (pdf_selection_highlight.sample) in HST PDF on an X display, selects text with a real
mouse drag (xdotool), screenshots the screen before and after and measures the highlight and the selected glyphs
(pdf_selection_highlight.measure), with the light and the dark application appearance (the page view paints the
same colours in both; toolbar_luma shows whether the VCL plugin turned dark). Also checks that the status bar counts
the selected characters, and the toolbar layout (pdf_viewer_toolbar_layout: no control overlaps another or is cut off,
the gaps between controls are plain background), at 96 and 144 DPI (SAL_FORCEDPI: 100% and 150%).
Screenshots go to --workdir.

  check-pdf-selection.py --instdir upstream/libreoffice/instdir --workdir /tmp/pdfsel --display :71
Exit 0 when every run passes, 1 otherwise.
"""
import argparse
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("HST_VCLPLUGIN", "gen")
import hst_gui
import pdf_selection_highlight as selection
import pdf_viewer_toolbar_layout as toolbar_layout
import png_luma
from pdf_viewer_uno import info, open_viewer, signing_props

APPEARANCES = {"light": "1", "dark": "2"}  # Common/Appearance ApplicationAppearance


def xdotool(display, *args):
    return subprocess.run(["xdotool"] + [str(a) for a in args], env={"DISPLAY": display},
                          capture_output=True, text=True, check=True).stdout


def luma(path):
    with open(path, "rb") as handle:
        return png_luma.read(handle.read())[2]


def run(instdir, workdir, display, appearance, dpi):
    out = os.path.join(workdir, "%s-%d" % (appearance, dpi))
    os.makedirs(out, exist_ok=True)
    pdf = selection.write(os.path.join(out, "chon-van-ban.pdf"))
    config = [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", APPEARANCES[appearance])]
    office = hst_gui.Office(instdir, os.path.join(out, "office"), hst_gui.free_port(), display=display, config=config,
                            env={"SAL_FORCEDPI": str(dpi)})
    office.start()
    try:
        frame, _ = open_viewer(office, pdf)
        office.dispatch(frame, ".uno:HSTPdfZoom", signing_props(Fit="width"))
        time.sleep(2)
        window = xdotool(display, "search", "--name", "HST PDF").split()[-1]
        geometry = dict(line.split("=") for line in xdotool(display, "getwindowgeometry", "--shell", window).split())
        x, y, w, h = (int(geometry[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
        # the middle of the page view: text lines run from the top of the page to the bottom
        start, end = (x + w * 30 // 100, y + h * 35 // 100), (x + w * 75 // 100, y + h * 55 // 100)
        xdotool(display, "mousemove", w // 2, h - 5)  # pointer out of the way
        time.sleep(0.5)
        before = hst_gui.screenshot(os.path.join(out, "before.png"), display)
        xdotool(display, "mousemove", *start)
        xdotool(display, "mousedown", 1)
        for step in range(1, 11):
            xdotool(display, "mousemove", start[0] + (end[0] - start[0]) * step // 10,
                    start[1] + (end[1] - start[1]) * step // 10)
            time.sleep(0.05)
        xdotool(display, "mouseup", 1)
        xdotool(display, "mousemove", w // 2, h - 5)
        time.sleep(1.5)
        after = hst_gui.screenshot(os.path.join(out, "after.png"), display)
        data = info(office, frame)
        status = data["StatusText"]
        rows_after = luma(after)
        result = selection.measure(luma(before), rows_after, (x, y + 60, x + w, y + h - 30))
        toolbar = [v for row in rows_after[y + 35:y + 45] for v in row[x + 10:x + w - 10]]
        result["toolbar_luma"] = sum(toolbar) // max(1, len(toolbar))  # shows whether the dark appearance applied
        result["status"] = status
        result["toolbar"] = toolbar_layout.evaluate(data["ToolbarLayout"], data["ToolbarScreen"], luma(before))
        result["toolbar_layout"] = [list(data["ToolbarScreen"])] + list(data["ToolbarLayout"])
        result["selected_in_status"] = "Đã chọn" in status or "selected" in status
        frame.close(True)
        return result
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--dpi", type=int, nargs="+", default=[96, 144], help="SAL_FORCEDPI per run (144: 150%%)")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    os.makedirs(args.workdir, exist_ok=True)
    results = {}
    for dpi in args.dpi:
        for appearance in APPEARANCES:
            try:
                results["%s-%d" % (appearance, dpi)] = run(args.instdir, args.workdir, args.display, appearance, dpi)
            except Exception as error:  # noqa: BLE001 - one run failing must not hide the others
                results["%s-%d" % (appearance, dpi)] = {"readable": False, "error": repr(error)[:400]}
    ok = all(r.get("readable") and r.get("selected_in_status") and r.get("toolbar", {}).get("ok")
             for r in results.values())
    print(json.dumps({"results": results, "pass": ok}, ensure_ascii=False, indent=1))
    with open(os.path.join(args.workdir, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
