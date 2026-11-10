#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF text selection keeps the selected text readable on an INSTALLED HST Office (Windows).

Opens a synthetic text page (pdf_selection_highlight.sample) in HST PDF, selects text with a real mouse drag
(SendInput), screenshots the screen before and after and measures the highlight and the selected glyphs
(pdf_selection_highlight.measure): the highlight stays light and the selected glyphs much darker than it. Before the
fix, Windows with Skia painted the selection as solid (20, 46, 83) bars that hid the text. Runs with the light and then
the dark application appearance (Common/Appearance ApplicationAppearance, the office restarted in between).

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-pdf-selection.py --install DIR --out DIR
[--port 2121]. Evidence: <out>/<appearance>-before.png, <out>/<appearance>-after.png. Exit 1 on any FAIL.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pdf_selection_highlight as selection  # noqa: E402
import png_luma  # noqa: E402
import windows_gui as wg  # noqa: E402

VIEWER = "org.hasontech.comp.PdfViewerController"


def luma(path):
    with open(path, "rb") as handle:
        return png_luma.read(handle.read())[2]


def set_appearance(office, value):
    import uno
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Common/Appearance"
    access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
    uno.invoke(access, "setPropertyValue", ("ApplicationAppearance", uno.Any("short", value)))  # xs:short
    access.commitChanges()


def select_and_measure(check, office, url, out, appearance):
    viewer = office.load(url)
    check("%s: the PDF opens in HST PDF" % appearance, getattr(viewer, "ImplementationName", "") == VIEWER,
          getattr(viewer, "ImplementationName", None))
    frame = viewer.getFrame()
    import uno
    fit = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    fit.Name, fit.Value = "Fit", "width"
    office.service("com.sun.star.frame.DispatchHelper").executeDispatch(frame, ".uno:HSTPdfZoom", "", 0, (fit,))
    time.sleep(3)
    window = wg.find_window(lambda title: title.endswith("HST PDF"), timeout=20)
    check("%s: the HST PDF window is on screen" % appearance, window is not None, window)
    if window is None:
        return
    wg.foreground(window[0])
    left, top, right, bottom = wg.window_rect(window[0])
    width, height = right - left, bottom - top
    start = (left + width * 30 // 100, top + height * 35 // 100)
    end = (left + width * 75 // 100, top + height * 55 // 100)
    wg.mouse_move(left + width // 2, bottom - 5)
    time.sleep(0.5)
    before = wg.screenshot(os.path.join(out, "%s-before.png" % appearance), cursor=False)
    wg.drag(start, end)
    wg.mouse_move(left + width // 2, bottom - 5)
    time.sleep(1.5)
    after = wg.screenshot(os.path.join(out, "%s-after.png" % appearance), cursor=False)
    rows_before, rows_after = luma(before), luma(after)
    box = (max(0, left), max(0, top + 60), min(len(rows_after[0]), right), min(len(rows_after), bottom - 30))
    result = selection.measure(rows_before, rows_after, box)
    toolbar = [v for row in rows_after[top + 35:top + 45] for v in row[left + 10:right - 10]]
    result["toolbar_luma"] = sum(toolbar) // max(1, len(toolbar))
    check.note("%s: selection measure (highlight and glyph luma, 255 white)" % appearance, result)
    check("%s: the selection is a light highlight (luma >= %d) with the selected glyphs at least %d darker"
          % (appearance, selection.HIGHLIGHT_MIN, selection.GLYPH_MARGIN), result["readable"], result)
    frame.close(True)
    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2121)
    args = parser.parse_args()
    out, install = os.path.abspath(args.out), os.path.abspath(args.install)
    check = wg.Results(out, "pdf-selection")
    pdf = selection.write(os.path.join(out, "chon-van-ban.pdf"))
    import uno
    url = uno.systemPathToFileUrl(pdf)
    office = wg.WinOffice(install, os.path.join(out, "profile"), args.port, os.path.join(out, "logs"))
    try:
        office.start(fresh=True)
        check.note("start-up dialog closed first", wg.dismiss_startup(office, os.path.join(out, "startup-dialog.png")))
        select_and_measure(check, office, url, out, "light")
        set_appearance(office, 2)
        office.stop()
        office.start()
        wg.dismiss_startup(office, os.path.join(out, "startup-dialog-2.png"), timeout=15)
        select_and_measure(check, office, url, out, "dark")
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
