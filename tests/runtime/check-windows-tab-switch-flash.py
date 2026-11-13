#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Switching document tabs never shows the desktop for a moment, on an INSTALLED HST Office (Windows).

A tab switch shows the window of the new tab and hides the old one. Before hst-document-tab-switch-no-flash.patch
the new window had no picture yet when the old one was hidden, so for about one screen refresh the desktop showed
through and the screen flashed on every switch (error report HSTO-000006).

The check grabs the desktop before the office starts (reference), opens three synthetic documents of each module
(HST Sheets, Writer, Slides, Draw, PDF; they become tabs of one window), maximizes it and switches with
.uno:NextDocumentTab while a thread grabs the screen as fast as GDI allows (downscaled). A frame during a switch that
differs from the screen before and after the switch and shows the reference desktop over more than DESKTOP_SHARE of
its pixels is a flash. Per module, any flash fails.

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-tab-switch-flash.py --install DIR --out DIR
[--port 2167] [--modules calc,writer,impress,draw,pdf] [--switches 6]. Evidence: <out>/results.json and
<out>/<module>-flash-<n>.bmp (the flash frames). Exit 1 on any FAIL.
"""
import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402

import screen_grab_gdi as grab  # noqa: E402

MODULES = {  # module -> (factory, extension, filter)
    "calc": ("scalc", "xlsx", "Calc MS Excel 2007 XML"),
    "writer": ("swriter", "docx", "MS Word 2007 XML"),
    "impress": ("simpress", "pptx", "Impress MS PowerPoint 2007 XML"),
    "draw": ("sdraw", "odg", "draw8"),
    "pdf": ("swriter", "pdf", "writer_pdf_Export"),
}



def prop(name, value):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name, p.Value = name, value
    return p


def make_documents(office, module, folder, count=3):
    """Synthetic documents of `module` (cells, paragraphs or shapes; a PDF from a text document)."""
    import uno
    factory, extension, filter_name = MODULES[module]
    os.makedirs(folder, exist_ok=True)
    urls = []
    for n in range(count):
        doc = office.desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0, (prop("Hidden", True),))
        if factory == "scalc":
            sheet = doc.Sheets.getByIndex(0)
            for r in range(40):
                for c in range(12):
                    sheet.getCellByPosition(c, r).setFormula("=%d*%d" % (r + 1, c + n + 1) if c % 3 else "Muc %d" % r)
        elif factory == "swriter":
            text = doc.Text
            for p in range(20):
                text.insertString(text.End, "Tai lieu %d, doan %d. " % (n + 1, p + 1) + "Noi dung mau. " * 8, False)
                text.insertControlCharacter(text.End, 0, False)
        else:
            shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
            doc.DrawPages.getByIndex(0).add(shape)
            shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", 2000 + 1500 * n, 3000)
            shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", 8000, 5000)
            shape.FillColor = 0x3366CC + 0x200000 * n
        url = uno.systemPathToFileUrl(os.path.join(folder, "mau%d.%s" % (n + 1, extension)))
        doc.storeToURL(url, (prop("FilterName", filter_name),))
        doc.close(True)
        urls.append(url)
    return urls


def close_all(office):
    try:
        components = office.desktop.getComponents().createEnumeration()
        while components.hasMoreElements():
            component = components.nextElement()
            try:
                component.setModified(False)
                component.close(True)
            except Exception:  # noqa: BLE001 - the Start Center has no model
                pass
    except Exception:  # noqa: BLE001
        pass


def check_module(office, check, screen, desktop, module, out, switches):
    urls = make_documents(office, module, os.path.join(out, "docs", module))
    for url in urls:
        office.desktop.loadComponentFromURL(url, "_blank", 0, ())
        time.sleep(1.5)
    time.sleep(3)
    for window, _title in wg.dialogs(office):  # tip of the day and the like
        wg.close_dialog(window)
    time.sleep(1)
    office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
    time.sleep(2.5)
    helper = office.service("com.sun.star.frame.DispatchHelper")
    recorder = grab.Recorder(screen)
    recorder.start()
    time.sleep(0.8)
    marks = []
    for _ in range(switches):
        marks.append(time.perf_counter())
        helper.executeDispatch(office.desktop.getCurrentFrame(), ".uno:NextDocumentTab", "", 0, ())
        time.sleep(1.4)
    recorder.stop.set()
    recorder.join(10)
    frames = recorder.frames
    flashes = []
    for k, start in enumerate(marks):
        before = [f for t, f in frames if t < start]
        during = [(t, f) for t, f in frames if start <= t <= start + 1.2]
        if not before or not during:
            continue
        before, after = before[-1], during[-1][1]
        for t, frame in during:
            share = grab.desktop_share(frame, before, after, desktop)
            if share > grab.DESKTOP_SHARE:
                path = os.path.join(out, "%s-flash-%d.bmp" % (module, len(flashes) + 1))
                screen.save_bmp(path, frame)
                flashes.append("switch %d +%d ms: %.0f%% desktop" % (k + 1, (t - start) * 1000, share * 100))
                break
    titles = {office.desktop.getCurrentFrame().Title}
    fps = len(frames) / max(frames[-1][0] - frames[0][0], 0.001) if frames else 0
    check("%s: %d tab switches show no desktop flash" % (module, len(marks)), not flashes and fps >= 10,
          "; ".join(flashes) or "%.0f grabs/s, last tab %s" % (fps, sorted(titles)))
    close_all(office)
    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2167)
    parser.add_argument("--modules", default="writer,impress,draw,pdf,calc")
    parser.add_argument("--switches", type=int, default=6)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    check = wg.Results(out, "tab-switch-flash")
    screen = grab.Screen()
    desktop = screen.grab()  # before the office starts: the picture a flash shows
    screen.save_bmp(os.path.join(out, "desktop.bmp"), desktop)
    office = wg.WinOffice(args.install, os.path.join(out, "profile"), args.port, os.path.join(out, "log"))
    try:
        office.start(fresh=True)
        check.note("start-up dialogs", wg.dismiss_startup(office, os.path.join(out, "startup.png"), timeout=30, settle=5))
        # Measure on a warm profile whose start shows no question any more: loading documents right after a
        # start-up question was ended over UNO has crashed the office on this harness.
        for start in range(2, 5):
            office.stop()
            office.start()
            seen = wg.dismiss_startup(office, os.path.join(out, "startup-%d.png" % start), timeout=15, settle=3)
            check.note("start-up dialogs, start %d" % start, seen)
            if not seen:
                break
        for module in args.modules.split(","):
            for attempt in (1, 2):
                try:
                    check_module(office, check, screen, desktop, module, out, args.switches)
                    break
                except Exception as error:  # noqa: BLE001 - the office went away: once more, else report
                    check.note("%s: attempt %d" % (module, attempt), repr(error))
                    office.stop()
                    office.start()
                    wg.dismiss_startup(office, os.path.join(out, "startup-retry.png"), timeout=15, settle=3)
                    if attempt == 2:
                        check("%s: tab switch check ran" % module, False, repr(error))
    finally:
        close_all(office)
        office.stop()
        screen.close()
    return check.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
