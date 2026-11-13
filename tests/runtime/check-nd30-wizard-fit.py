#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The ND30 wizard ("Văn bản hành chính") fits the screen's work area: on a small screen (1366x768 at 125 %: about
708 px of work area) it drops the preview column and, still too tall, scrolls its form while the check boxes and the
OK/Cancel buttons stay in view (wizard_scroll_band). Shows the real dialog over a Writer window, measures it, scrolls
every form control into view, saves a screenshot, cancels.

Linux (Xvfb; the display must run and is never started here; HST dialogs need a D-Bus session, so run it under
dbus-run-session as the build user):
    <instdir>/program/python tests/runtime/check-nd30-wizard-fit.py --display :173 --instdir <instdir> --out DIR
        [--scale 1.25]       # GDK_DPI_SCALE for the office: 125 % on an Xvfb of 1366x768 (a panel margin is kept)
Windows (in an interactive session, see windows-own-session-task.ps1; the shot is taken with PrintWindow, which
works in a disconnected session):
    <instdir>\\program\\python.exe tests\\runtime\\check-nd30-wizard-fit.py --windows --instdir <instdir> --out DIR
        [--force-small]      # treat the work area as too small (a disconnected session keeps its 1920x1080)
Prints PASS/FAIL rows and a JSON summary; exit 1 on failure.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions", "hst-vietnamese-tools", "python")]
import hst_gui  # noqa: E402

ROWS = []


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:240]), flush=True)


def capture_windows(title, path):
    """BMP of the top-level window titled `title` through PrintWindow (works in a disconnected session), and of the
    whole desktop next to it (`desktop.bmp`, only in a connected session: shows the dialog against the taskbar).
    Returns the window rectangle (left, top, right, bottom) or None."""
    import ctypes
    user32 = ctypes.windll.user32
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # device pixels, as the office uses them
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    rect = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, rect)
    _bitmap(hwnd, rect[2] - rect[0], rect[3] - rect[1], path, window=True)
    _bitmap(None, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1), os.path.join(os.path.dirname(path), "desktop.bmp"))
    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE: Cancel
    return tuple(rect)


def _bitmap(hwnd, width, height, path, window=False):
    import ctypes
    import struct
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    screen = user32.GetDC(hwnd)
    memory, bitmap = gdi32.CreateCompatibleDC(screen), gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(memory, bitmap)
    if window:
        user32.PrintWindow(hwnd, memory, 2)  # PW_RENDERFULLCONTENT
    elif not gdi32.BitBlt(memory, 0, 0, width, height, screen, 0, 0, 0x00CC0020):  # SRCCOPY
        return
    header = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, pixels, header, 0)
    with open(path, "wb") as out:
        out.write(b"BM" + struct.pack("<IHHI", 54 + len(pixels.raw), 0, 0, 54) + header + pixels.raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", default=":173")
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-wizard-fit"))
    parser.add_argument("--port", type=int, default=2319)
    parser.add_argument("--scale", help="Linux: GDK_DPI_SCALE of the office, e.g. 1.25")
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--force-small", action="store_true", help="treat the work area as too small for the dialog")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    if args.windows:
        import hst_gui_windows
        hst_gui_windows.install()
        os.environ["HST_WINDOWS_UI"] = "1"
    hst_gui.setup_uno(args.instdir)
    env = {"GDK_DPI_SCALE": args.scale} if args.scale else None
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display, env=env).start()
    summary = {}
    try:
        from hst_office import dialogs, wizard_scroll_band
        from hst_office.data_files import load_locale
        from hst_office.wizard_nd30 import Nd30Wizard
        if args.force_small:
            dialogs.Dialog._exceeds_screen = lambda self, toolkit: True
            wizard_scroll_band.max_height = lambda dialog: int(dialog.model.Height * 0.7)
        doc = office.load("private:factory/swriter")
        time.sleep(3)
        wizard = Nd30Wizard(office.ctx, load_locale("vi"))
        runner = threading.Thread(target=wizard.run, args=(doc.getCurrentController().getFrame().getContainerWindow(),), daemon=True)
        runner.start()
        time.sleep(12)
        from hst_office import screen_work_area
        toolkit = office.service("com.sun.star.awt.Toolkit")
        area = screen_work_area.work_area(toolkit)  # taskbar excluded (getWorkArea() is the whole display)
        size = wizard.d.dialog.getPeer().getPosSize()
        model = wizard.d.model
        summary = {"display": [toolkit.getWorkArea().Width, toolkit.getWorkArea().Height], "workArea": list(area),
                   "dialogPx": [size.Width, size.Height], "units": [model.Width, model.Height], "compact": wizard.compact,
                   "scrolls": wizard.band is not None}
        check("dialog fits the work area with its title bar", not screen_work_area.exceeds(toolkit, size), summary)
        for name in ("applyPage", "pageNumbers", "duplex", "btnOk", "btnCancel"):
            item = model.getByName(name)
            check("%s stays in view" % name, item.EnableVisible and item.PositionY + item.Height <= model.Height,
                  (item.PositionY, item.Height, model.Height))
        if wizard.band:
            unreachable = []
            for name in wizard.band.names:
                if model.getByName(name).EnableVisible is False and name in ("l_preview", "preview"):
                    continue
                wizard.band.reveal(name)
                if not model.getByName(name).EnableVisible:
                    unreachable.append(name)
            check("every form control scrolls into view", not unreachable, unreachable)
            wizard.band.scroll_to(0)
        time.sleep(2)
        if args.windows:
            rect = capture_windows(model.Title, os.path.join(out, "wizard.bmp"))
            summary["windowRect"] = rect
            # the window itself (frame and title bar included) inside the taskbar-free work area
            check("window inside the work area", rect and rect[1] >= 0 and rect[3] <= area[1] and rect[2] - rect[0] <= area[0],
                  (rect, area))
        else:
            shot = os.path.join(out, "wizard.png")
            subprocess.run(["import", "-window", "root", shot], env=dict(os.environ, DISPLAY=args.display), check=False)
            check("screenshot", os.path.exists(shot), shot)
            subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=args.display), check=False)
        runner.join(20)
        check("Cancel closes the wizard", not runner.is_alive())
        doc.setModified(False)
        doc.close(True)
    finally:
        office.stop()
        with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=1)
    print(json.dumps(summary), flush=True)
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
