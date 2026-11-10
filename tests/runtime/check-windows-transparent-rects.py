#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Translucent rectangles stay translucent on an INSTALLED HST Office (Windows): Impress edit view and slide show.

VCL on Windows sends a translucent RECTANGLE drawn with OutputDevice::DrawTransparent(tools::PolyPolygon, percent) to
DrawAlphaRect, which with Skia overwrote the pixels with the premultiplied colour (dark boxes) instead of blending. The
slide show draws with the VCL canvas when Skia is on, and the canvas fills translucent shapes that way. A slide with a
blue rectangle at 50% fill transparency on white is shown in the edit view and in the slide show; the rectangle's
centre must be light (about (154, 193, 241)), not dark (about (26, 66, 114)).

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-transparent-rects.py --install DIR --out DIR
[--port 2123]. Evidence: <out>/edit-view.png, <out>/slide-show-N.png. Exit 1 on any FAIL.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import png_luma  # noqa: E402
import windows_gui as wg  # noqa: E402

BLUE = 0x3584E4
LIGHT = 150  # luma of the blue at 50% over white is about 186; the premultiplied (dark) one about 59


def blue_luma(path):
    """Median luma of the bluish pixels of the screenshot (the rectangle), or None."""
    with open(path, "rb") as handle:
        width, height, luma = png_luma.read(handle.read())
    # the rectangle is the large non-white, non-black area in the middle of the slide: take the screen centre band
    values = [luma[y][x] for y in range(height * 2 // 5, height * 3 // 5, 2) for x in range(width // 3, width * 2 // 3, 2)
              if 30 < luma[y][x] < 235]
    values.sort()
    return values[len(values) // 2] if len(values) > 200 else None


def add_rectangle(doc):
    import uno
    page = doc.getDrawPages().getByIndex(0)
    while page.getCount():
        page.remove(page.getByIndex(0))
    width, height = doc.getDrawPages().getByIndex(0).Width, doc.getDrawPages().getByIndex(0).Height
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    page.add(shape)
    shape.setPosition(uno.createUnoStruct("com.sun.star.awt.Point", width // 6, height // 6))
    shape.setSize(uno.createUnoStruct("com.sun.star.awt.Size", width * 2 // 3, height * 2 // 3))
    shape.FillColor = BLUE
    shape.FillTransparence = 50
    shape.LineStyle = uno.Enum("com.sun.star.drawing.LineStyle", "NONE")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2123)
    args = parser.parse_args()
    out, install = os.path.abspath(args.out), os.path.abspath(args.install)
    check = wg.Results(out, "transparent-rects")
    office = wg.WinOffice(install, os.path.join(out, "profile"), args.port, os.path.join(out, "logs"))
    try:
        office.start(fresh=True)
        check.note("start-up dialog closed first", wg.dismiss_startup(office, os.path.join(out, "startup-dialog.png")))
        tips = office.config("/org.openoffice.Office.Common/Misc", None)
        import uno
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Common/Misc"
        update = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        update.setPropertyValue("ShowTipOfTheDay", False)
        update.commitChanges()
        check.note("Tip of the Day was on", tips.getPropertyValue("ShowTipOfTheDay"))
        doc = office.load("private:factory/simpress")
        check.note("dialogs closed after the new presentation",
                   wg.dismiss_startup(office, os.path.join(out, "presentation-dialog.png"), timeout=8, settle=3))
        add_rectangle(doc)
        time.sleep(3)
        window = wg.find_window(lambda title: "HST" in title and "Start" not in title, timeout=10)
        if window:
            wg.foreground(window[0])
        edit = wg.screenshot(os.path.join(out, "edit-view.png"), cursor=False)
        check.note("edit view: rectangle luma (drawinglayer path)", blue_luma(edit))
        doc.getPresentation().start()
        luma = None
        for attempt in range(4):  # the full-screen show window takes a moment to appear and paint
            time.sleep(3)
            show = wg.screenshot(os.path.join(out, "slide-show-%d.png" % attempt), cursor=False)
            luma = blue_luma(show)
            check.note("slide show shot %d: rectangle luma" % attempt, luma)
            if luma is not None:
                break
        check("slide show: the 50%% transparent rectangle stays light (luma >= %d)" % LIGHT,
              luma is not None and luma >= LIGHT, luma)
        doc.getPresentation().end()
        time.sleep(2)
        doc.close(True)
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
