# SPDX-License-Identifier: AGPL-3.0-only
"""Writer sidebar, menus, dialog and Start Center captures of check-hst-icon-theme.py."""
import subprocess
import threading
import time

import hst_gui


def surfaces(tabs, office, window, args, tag):
    """Representative real surfaces; menu/dialog captures include native popups."""
    def shot(name, width=1485):
        tabs.xdo(args.display, "mousemove", "2999", "1799")
        time.sleep(0.7)
        subprocess.run(["import", "-display", args.display, "-window", "root", "-crop",
                        f"{width * args.scale}x{900 * args.scale}+0+0",
                        str(args.out / f"{tag}-{name}.png")], check=True)

    def click(x, y, button="1"):
        tabs.xdo(args.display, "mousemove", str(x * args.scale), str(y * args.scale), "click", button)
        time.sleep(0.8)

    doc = office.desktop().getCurrentComponent()
    doc.Text.String = "HST Office — Kiểm tra biểu tượng, màu chữ và trạng thái chọn."
    cursor = doc.CurrentController.ViewCursor
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    office.dispatch(doc.CurrentController.Frame, ".uno:Copy")
    home = next(t for t in tabs.ribbon_tabs() if t[0] == "Trang đầu")
    tabs.click(args.display, tuple(v * args.scale for v in home[1]))
    shot("selection")
    click(1457, 264)  # Writer sidebar Properties deck, at the measured window size.
    shot("sidebar")
    click(1457, 22)  # notebookbar hamburger: native application menu
    # With no window manager, GTK can place this popup beyond the application's
    # right edge on the larger Xvfb screen. Include that actual popup in the shot.
    shot("menu", width=1850)
    tabs.xdo(args.display, "key", "Escape")
    click(520, 450, "3")
    shot("context-menu")
    tabs.xdo(args.display, "key", "Escape")
    worker = threading.Thread(target=office.dispatch, args=(doc.CurrentController.Frame, ".uno:FontDialog"), daemon=True)
    worker.start()
    deadline = time.monotonic() + 30
    dialog = None
    while time.monotonic() < deadline:
        dialog = next((wid for wid, name in hst_gui.toplevels(args.display, office.pid)
                       if any(word in name for word in ("Phông", "Ký tự", "Font", "Character"))), None)
        if dialog:
            break
        time.sleep(0.3)
    if not dialog:
        raise RuntimeError(f"Font dialog did not appear: {hst_gui.toplevels(args.display, office.pid)}")
    time.sleep(1)
    shot("font-dialog")
    tabs.xdo(args.display, "windowfocus", dialog)
    tabs.xdo(args.display, "key", "Escape")
    worker.join(timeout=15)
    if worker.is_alive():
        raise RuntimeError("Font dialog did not close")
    doc.setModified(False)
