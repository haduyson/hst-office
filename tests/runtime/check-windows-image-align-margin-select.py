#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Writer: centre a picture like a word processor, and select lines from the left margin (INSTALLED HST Office,
Windows; the same steps as check-image-align-margin-select.py on Linux).

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-image-align-margin-select.py --install DIR
           --docx FILE --out DIR [--port 2131] [--expect fixed|base]

Real input (SendInput) on the office window only. Steps, each with a screenshot: hover in the left margin beside the
inline picture (the shot shows the pointer), click there (the line is selected), Ctrl+E (centred), Ctrl+Z; click the
inline picture, Ctrl+E (its paragraph is centred, the picture stays selected), Ctrl+Z; click the floating picture,
Ctrl+E (it is centred). The display scale is the machine's own (the caller sets 100 % or 125 % and restores it).
Quits with .uno:Quit on the main thread. Exit 1 on a FAIL (--expect base: the steps are only recorded).
"""
import argparse
import os
import shutil
import struct
import sys
import time
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import png_luma  # noqa: E402
import windows_gui as wg  # noqa: E402

ORANGE, BLUE = (230, 120, 0), (0, 90, 220)
CENTER, HORI_CENTER = 3, 2
VK_CONTROL = 0x11


def box_of(path, colour, area, tol=40):
    """[left, top, right, bottom] of the pixels near colour inside area (screen box), None when absent."""
    data = open(path, "rb").read()
    pos, idat, header = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", data[pos + 8:pos + 8 + length])
        elif kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    width, height, _depth, kind = header[:4]
    bpp = 4 if kind == 6 else 3
    rows = png_luma._unfilter(zlib.decompress(idat), width, height, bpp)  # noqa: SLF001 - the shared PNG decoder
    found = [(x, y) for y in range(max(0, area[1]), min(height, area[3]))
             for x in range(max(0, area[0]), min(width, area[2]))
             if sum(abs(rows[y][x * bpp + c] - colour[c]) for c in range(3)) < tol]
    if len(found) < 50:
        return None
    xs, ys = [p[0] for p in found], [p[1] for p in found]
    return [min(xs), min(ys), max(xs), max(ys)]


def page_left(path, x, y):
    """The page's left edge on row y: walk left from x while the pixels are page white."""
    _w, _h, luma = png_luma.read(open(path, "rb").read())
    while x > 0 and luma[y][x - 1] > 245:
        x -= 1
    return x


class Run:
    def __init__(self, args):
        self.args, self.step = args, 0
        self.out = os.path.abspath(args.out)
        self.check = wg.Results(self.out, "image-align")
        self.office = wg.WinOffice(os.path.abspath(args.install), os.path.join(self.out, "profile"), args.port,
                                   os.path.join(self.out, "logs"), nodefault=True)

    def shot(self, name, cursor=False):
        self.step += 1
        return wg.screenshot(os.path.join(self.out, "%d-%s.png" % (self.step, name)), cursor=cursor)

    def key(self, letter):
        wg.chord(VK_CONTROL, ord(letter), target=self.hwnd)
        time.sleep(1.5)

    def click(self, x, y):
        wg.click(x, y)
        time.sleep(1.5)

    def record(self, name, ok, detail):
        if self.args.expect == "base":
            self.check.note(name, detail)
        else:
            self.check(name, ok, detail)

    def graphics(self):
        objects = self.doc.getGraphicObjects()
        return [objects.getByIndex(i) for i in range(objects.getCount())]

    def run(self):
        import uno
        docx = os.path.join(self.out, os.path.basename(self.args.docx))
        shutil.copy(self.args.docx, docx)  # never the shared fixture in place
        self.office.start(fresh=True)
        self.ui = self.office.service("com.sun.star.ui.test.UITest")
        wg.dismiss_startup(self.office, os.path.join(self.out, "startup-dialog.png"))
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "OnMainThread", True
        self.doc = self.office.desktop.loadComponentFromURL(uno.systemPathToFileUrl(docx), "_default", 0, (arg,))
        time.sleep(6)
        window = wg.find_window(lambda title: "cau-hoi-anh" in title, timeout=30)
        self.hwnd = window[0]
        wg.user32.ShowWindow(self.hwnd, 3)  # maximised, as a user works
        wg.foreground(self.hwnd)
        settings = self.doc.getCurrentController().getViewSettings()
        settings.ZoomType, settings.ZoomValue = 3, 100
        time.sleep(3)
        left, top, right, bottom = wg.window_rect(self.hwnd)
        start = self.shot("start")
        area = (left, top + (bottom - top) // 5, right - 80, bottom)  # below the ribbon and the ruler
        inline, floating = box_of(start, ORANGE, area), box_of(start, BLUE, area)
        self.check.note("pictures on screen", {"inline": inline, "floating": floating})
        mid = (inline[1] + inline[3]) // 2
        margin_x = (page_left(start, inline[0] - 2, mid) + inline[0]) // 2
        inline_graphic = [g for g in self.graphics() if g.AnchorType.value == "AS_CHARACTER"][0]
        para = inline_graphic.getAnchor().getText().createTextCursorByRange(inline_graphic.getAnchor())

        wg.mouse_move(margin_x, mid)
        time.sleep(1)
        self.shot("margin-hover", cursor=True)
        self.click(margin_x, mid)
        selected = self.doc.getCurrentController().getSelection()
        spans = False
        if selected.supportsService("com.sun.star.text.TextRanges"):
            rng = selected.getByIndex(0)
            spans = rng.getText().compareRegionStarts(rng.getStart(), rng.getEnd()) != 0
        self.record("margin click selects the picture's line", spans, "non-empty text selection %s" % spans)
        self.shot("margin-click")
        self.key("E")
        self.record("then Ctrl+E centres it", para.ParaAdjust == CENTER, "ParaAdjust %s" % para.ParaAdjust)
        self.shot("margin-ctrl-e")
        self.key("Z")

        self.click((inline[0] + inline[2]) // 2, mid)
        self.key("E")
        still = self.doc.getCurrentController().getSelection().supportsService("com.sun.star.text.TextGraphicObject")
        self.record("selected inline picture + Ctrl+E centres its paragraph", para.ParaAdjust == CENTER and still,
                    "ParaAdjust %s, picture still selected %s" % (para.ParaAdjust, still))
        self.shot("picture-ctrl-e")
        self.key("Z")

        self.click((floating[0] + floating[2]) // 2, (floating[1] + floating[3]) // 2)
        self.key("E")
        graphic = [g for g in self.graphics() if g.AnchorType.value != "AS_CHARACTER"][0]
        self.record("selected floating picture + Ctrl+E centres it", graphic.HoriOrient == HORI_CENTER,
                    "HoriOrient %s" % graphic.HoriOrient)
        self.shot("floating-ctrl-e")

    def quit(self):
        try:
            self.doc.setModified(False)
            self.ui.executeCommand(".uno:Quit")  # main thread
            self.office.proc.wait(60)
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        self.office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--docx", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2131)
    parser.add_argument("--expect", choices=("fixed", "base"), default="fixed")
    run = Run(parser.parse_args())
    try:
        run.run()
    except Exception:  # noqa: BLE001
        import traceback
        run.check("harness", False, traceback.format_exc())
    finally:
        run.quit()
    return run.check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
