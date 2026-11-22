# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Writer: centre a picture like a word processor, and select lines from the left margin (GUI run, Linux).

Usage: python3 tests/runtime/check-image-align-margin-select.py --instdir DIR --docx FILE --out DIR
           [--display :173] [--scale 1.25] [--expect fixed|base]

The .docx has a picture alone on its line (anchored as character, orange border) and a floating picture
anchored to a paragraph (blue border); the borders let the run find them on screen. With real input (xdotool
on the run's own X display) it does, taking a screenshot after each step:
  1. click in the left margin beside the inline picture: the line is selected (text selection over it);
  2. Ctrl+E: the picture's paragraph is centred; Ctrl+Z;
  3. click on the inline picture, Ctrl+E: the paragraph is centred, the picture stays selected; Ctrl+Z;
  4. click on the floating picture, Ctrl+E: its horizontal position becomes centred.
--expect fixed fails when a step does not do that; --expect base records what the build does (before shots).
125 % is the desktop's font scale (Xft.dpi 120 on the display, set and restored here). The display must run.
Writes results.json and step PNGs into --out. Quits the office with .uno:Quit on the main thread.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import numpy
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from ribbon_banner_run import geometry, xdo  # noqa: E402

ORANGE, BLUE = (230, 120, 0), (0, 90, 220)
CENTER, LEFT = 3, 0  # com.sun.star.style.ParagraphAdjust
HORI_CENTER = 2  # com.sun.star.text.HoriOrientation.CENTER


def box_of(shot, colour, top, tol=40):
    """[left, top, right, bottom] of the pixels near colour (a picture's border) below row top (the ribbon above
    shows coloured text too), None when absent."""
    pixels = numpy.asarray(Image.open(shot).convert("RGB"), dtype=int)[top:]
    ys, xs = numpy.nonzero(numpy.abs(pixels - numpy.array(colour)).sum(axis=2) < tol)
    return None if len(xs) < 50 else [int(xs.min()), int(ys.min()) + top, int(xs.max()), int(ys.max()) + top]


def page_left(shot, x, y):
    """The page's left edge on row y: walk left from x while the pixels are page white."""
    row = numpy.asarray(Image.open(shot).convert("RGB"), dtype=int)[y]
    while x > 0 and row[x - 1].min() > 245:
        x -= 1
    return x


class Run:
    def __init__(self, args):
        self.args, self.results, self.step = args, [], 0
        self.office = hst_gui.Office(args.instdir, os.path.join(args.out, "work"), hst_gui.free_port(),
                                     display=args.display, extra_args=["--writer"])

    def shot(self, name):
        self.step += 1
        path = os.path.join(self.args.out, f"{self.step}-{name}.png")
        hst_gui.screenshot(path, self.args.display)
        return path

    def key(self, keys):
        xdo(self.args.display, "key", "--clearmodifiers", keys)
        time.sleep(1.5)

    def click(self, x, y):
        # a separate, synced move and a held button: gtk drops a press that comes with the move
        xdo(self.args.display, "mousemove", "--sync", str(x), str(y))
        time.sleep(0.5)
        xdo(self.args.display, "mousedown", "1")
        time.sleep(0.2)
        xdo(self.args.display, "mouseup", "1")
        time.sleep(1.5)

    def record(self, name, ok, detail):
        self.results.append({"step": name, "ok": bool(ok), "detail": detail})
        print(("PASS  " if ok else "INFO  " if self.args.expect == "base" else "FAIL  ") + f"{name}: {detail}",
              flush=True)

    def run(self):
        work = os.path.join(self.args.out, "work")
        os.makedirs(work, exist_ok=True)
        docx = os.path.join(work, os.path.basename(self.args.docx))
        shutil.copy(self.args.docx, docx)  # never the shared fixture in place
        self.office.start()
        from com.sun.star.beans import PropertyValue  # importable once the bridge is up
        self.ui = self.office.service("com.sun.star.ui.test.UITest")
        arg = PropertyValue()
        arg.Name, arg.Value = "OnMainThread", True
        self.doc = self.office.desktop().loadComponentFromURL("file://" + docx, "_default", 0, (arg,))
        time.sleep(6)
        wid = [w for w, n in hst_gui.toplevels(self.args.display, self.office.pid) if "cau-hoi" in n][0]
        xdo(self.args.display, "windowmove", wid, "0", "0")
        xdo(self.args.display, "windowsize", wid, str(int(1280 * self.args.scale)), str(int(860 * self.args.scale)))
        time.sleep(3)
        settings = self.doc.getCurrentController().getViewSettings()
        settings.ZoomType, settings.ZoomValue = 3, 100
        time.sleep(2)
        start = self.shot("start")
        top = int(200 * self.args.scale)  # below the ribbon and the ruler
        inline, floating = box_of(start, ORANGE, top), box_of(start, BLUE, top)
        print(f"inline picture {inline}, floating picture {floating}", flush=True)
        mid = (inline[1] + inline[3]) // 2
        margin_x = (page_left(start, inline[0] - 2, mid) + inline[0]) // 2
        para = self.picture_paragraph()

        self.click(margin_x, mid)
        selected = self.doc.getCurrentController().getSelection()
        spans = False
        if selected.supportsService("com.sun.star.text.TextRanges"):
            rng = selected.getByIndex(0)
            spans = rng.getText().compareRegionStarts(rng.getStart(), rng.getEnd()) != 0
        self.record("margin click selects the picture's line", spans, f"non-empty text selection {spans}")
        self.shot("margin-click")
        self.key("ctrl+e")
        self.record("then Ctrl+E centres it", para.ParaAdjust == CENTER, f"ParaAdjust {para.ParaAdjust}")
        self.shot("margin-ctrl-e")
        self.key("ctrl+z")

        self.click((inline[0] + inline[2]) // 2, mid)
        self.key("ctrl+e")
        selected = self.doc.getCurrentController().getSelection()
        still = selected.supportsService("com.sun.star.text.TextGraphicObject")
        self.record("selected inline picture + Ctrl+E centres its paragraph", para.ParaAdjust == CENTER and still,
                    f"ParaAdjust {para.ParaAdjust}, picture still selected {still}")
        self.shot("picture-ctrl-e")
        self.key("ctrl+z")

        self.click((floating[0] + floating[2]) // 2, (floating[1] + floating[3]) // 2)
        self.key("ctrl+e")
        graphic = [g for g in self.graphics() if g.AnchorType.value != "AS_CHARACTER"][0]
        self.record("selected floating picture + Ctrl+E centres it", graphic.HoriOrient == HORI_CENTER,
                    f"HoriOrient {graphic.HoriOrient}")
        self.shot("floating-ctrl-e")

    def graphics(self):
        objects = self.doc.getGraphicObjects()
        return [objects.getByIndex(i) for i in range(objects.getCount())]

    def picture_paragraph(self):
        """A text cursor in the inline picture's paragraph (reads its ParaAdjust)."""
        graphic = [g for g in self.graphics() if g.AnchorType.value == "AS_CHARACTER"][0]
        return graphic.getAnchor().getText().createTextCursorByRange(graphic.getAnchor())

    def quit(self):
        try:
            self.doc.setModified(False)
            self.ui.executeCommand(".uno:Quit")  # main thread
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        self.office.ctx = None
        self.office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--docx", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":173")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--expect", choices=("fixed", "base"), default="fixed")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    subprocess.run(["xrdb", "-display", args.display, "-merge", "-"], input="Xft.dpi: %d\n" % round(96 * args.scale),
                   text=True, check=False)
    run = Run(args)
    try:
        run.run()
    finally:
        run.quit()
        subprocess.run(["xrdb", "-display", args.display, "-merge", "-"], input="Xft.dpi: 96\n", text=True, check=False)
        subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"scale": args.scale, "expect": args.expect, "steps": run.results}, handle, ensure_ascii=False,
                  indent=1)
    return 0 if args.expect == "base" or all(r["ok"] for r in run.results) else 1


if __name__ == "__main__":
    sys.exit(main())
