# SPDX-License-Identifier: AGPL-3.0-only
"""Check direction A on a real GUI build: white panel with a neutral native frame.

Usage: python3 tests/runtime/check-ribbon-panel.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/ribbon-panel] [--display :97] [--plugin gtk3]
Starts a fresh profile (see hst_gui), opens Writer, Sheets and Slides and asserts on the screenshot of each window:
  - the frame at the left edge is neutral and light (every channel >= 110);
  - the panel row next to it is mostly the theme's window colour (white), i.e. the tint does not fill the ribbon.
Run it with --plugin gen as well: that backend draws the panel through TabControl::Paint (hst-ribbon-panel.patch),
as macOS and Windows do. Screenshots go to --out. Exit 1 when a check fails.
"""
import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
MODULES = (("writer", "private:factory/swriter"),
           ("sheets", "private:factory/scalc"),
           ("slides", "private:factory/simpress"))


def window_origin(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    return (max(int(re.search(r"Absolute upper-left X:\s+(-?\d+)", info).group(1)), 0),
            max(int(re.search(r"Absolute upper-left Y:\s+(-?\d+)", info).group(1)), 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/ribbon-panel"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--plugin", default="gtk3")
    args = parser.parse_args()
    from PIL import Image
    hst_gui.setup_uno(args.instdir)
    os.environ["HST_VCLPLUGIN"] = args.plugin
    os.makedirs(args.out, exist_ok=True)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work"), 21993, display=args.display,
                            lang="en_US.UTF-8").start()
    failed = 0
    try:
        for name, url in MODULES:
            doc = office.load(url)
            time.sleep(7)
            shot = office.screenshot(os.path.join(args.out, f"{args.plugin}-{name}.png"))
            wins = [w for w, n in hst_gui.toplevels(args.display, office.pid) if " — HST " in n]
            wx, wy = window_origin(args.display, wins[0]) if wins else (0, 0)
            img = Image.open(shot).convert("RGB")
            frame = (wx + 2, wy + 100, img.getpixel((wx + 2, wy + 100)))
            ok_frame = min(frame[2]) >= 110 and max(frame[2]) - min(frame[2]) <= 10
            row_y = wy + 150
            white = sum(1 for x in range(wx + 20, wx + 420) if min(img.getpixel((x, row_y))) >= 250)
            ok_panel = white >= 120
            for label, ok, detail in ((f"{name}: light neutral frame", ok_frame, frame),
                                      (f"{name}: panel is window-coloured (white px in a 400 px row)", ok_panel, white)):
                failed += not ok
                print(f"{'PASS' if ok else 'FAIL'}  [{args.plugin}] {label}  {detail}")
            try:
                doc.close(True)
            except Exception:  # noqa: BLE001 - the info bar can veto the close
                doc.dispose()
            time.sleep(1)
    finally:
        office.stop()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
