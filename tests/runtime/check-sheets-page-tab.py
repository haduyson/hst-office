#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The Page tab of Sheets on GTK3, as a user sees it: print scaling above the page format, in each scaling mode.

Usage: python3 tests/runtime/check-sheets-page-tab.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/sheets-page-tab] [--shots tests/output/screenshots-sheets-page-tab] [--display :97]

The display should be 1366x768: the dialog must fit it. Values come from the page style (as in an existing file), so each
screenshot also shows them being read. A person opens the screenshots. Exit 1 when the dialog does not fit or does not open.
The edits themselves are checked by check-dialogs-sheets.py page-scaling.
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

MODES = (("percent", {"PageScale": 75}), ("width-height", {"ScaleToPagesX": 2, "ScaleToPagesY": 3}), ("pages", {"ScaleToPages": 4}))
TITLE = re.compile(r"Kiểu dáng trang|Trang")


def geometry(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    return {k: int(re.search(rf"{p}:\s+(-?\d+)", info).group(1)) for k, p in
            (("x", "Absolute upper-left X"), ("y", "Absolute upper-left Y"), ("w", "Width"), ("h", "Height"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/sheets-page-tab"))
    parser.add_argument("--shots", default=os.path.join(hst_gui.ROOT, "tests/output/screenshots-sheets-page-tab"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.shots, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, 22002, display=args.display,
                            config=[("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]).start()
    failed = 0
    env = dict(os.environ, DISPLAY=args.display)
    try:
        doc = office.load("private:factory/scalc")
        time.sleep(3)
        frame = doc.getCurrentController().getFrame()
        style = doc.getStyleFamilies().getByName("PageStyles").getByName(doc.getSheets().getByIndex(0).PageStyle)
        for name, values in MODES:
            for key in ("PageScale", "ScaleToPages", "ScaleToPagesX", "ScaleToPagesY"):
                setattr(style, key, 0)
            for key, value in values.items():
                setattr(style, key, value)
            before = {w for w, _n in hst_gui.toplevels(args.display, office.pid)}
            worker = threading.Thread(target=office.dispatch, args=(frame, ".uno:PageFormatDialog"), daemon=True)
            worker.start()
            time.sleep(4)
            new = [(w, n) for w, n in hst_gui.toplevels(args.display, office.pid) if w not in before]
            if not new:
                print(f"FAIL  {name}: dialog did not open", flush=True)
                failed += 1
                continue
            wid, title = new[0]
            box = geometry(args.display, wid)
            fits = box["h"] <= 768 and box["w"] <= 1366 and box["x"] >= 0 and box["y"] >= 0 and box["y"] + box["h"] <= 768
            print(f"{'PASS' if fits else 'FAIL'}  {name}: {title!r} {box['w']}x{box['h']} at {box['x']},{box['y']} fits 1366x768", flush=True)
            failed += not fits
            subprocess.run(["xdotool", "windowraise", wid], env=env, check=False, timeout=10)
            time.sleep(0.5)
            hst_gui.screenshot(os.path.join(args.shots, f"page-tab-{name}.png"), args.display)
            if name == "pages":  # the left column's Sheet tab, to see what is left on it
                subprocess.run(["xdotool", "mousemove", "--window", wid, "80", "157", "click", "1"], env=env, check=False, timeout=10)
                time.sleep(1)
                hst_gui.screenshot(os.path.join(args.shots, "sheet-tab.png"), args.display)
            subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Escape"], env=env, check=False, timeout=15)
            worker.join(15)
        doc.setModified(False)
    finally:
        office.stop()
    print(f"sheets page tab: {failed} failed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
