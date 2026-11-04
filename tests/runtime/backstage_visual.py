# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel checks of check-backstage-flows.py on screenshots of the File view."""
import os
import subprocess
import time

import backstage_gui as gui
import hst_gui


def pixel(path, point):
    return subprocess.run(["convert", path, "-format", "%%[pixel:p{%d,%d}]" % point, "info:"], capture_output=True,
                          text=True, check=False).stdout


def check_hover(office, frame, out):
    display = office.display
    gui.reopen(office, frame)
    box = gui.view_items()["Mới"].queryComponent().getExtents(0)
    point = (box.x + box.width - 12, box.y + box.height // 2)
    before = os.path.join(out, "nav-thuong.png")
    hover = os.path.join(out, "nav-hover.png")
    gui.xdo(display, "mousemove", "800", "600")
    time.sleep(0.6)
    hst_gui.screenshot(before, display)
    gui.xdo(display, "mousemove", str(point[0]), str(point[1]))
    time.sleep(0.6)
    hst_gui.screenshot(hover, display)
    colours = pixel(before, point), pixel(hover, point)
    gui.record("the left column shows the hover", colours[0] != colours[1], colours)
    gui.xdo(display, "mousemove", "800", "600")
    time.sleep(0.6)
    hst_gui.screenshot(before, display)
    gui.record("the hover ends when the pointer leaves", pixel(before, point) == colours[0])
