# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel checks of check-backstage-flows.py on screenshots of the File panel."""
import os
import re
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
    # three quarters across: inside the coat's pill (inset in the item, and on GTK inside the theme's button
    # padding) and past the label, as inside the earlier look's full-width tint
    point = (box.x + box.width * 3 // 4, box.y + box.height // 2)
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


# the left column in the HST frame coat (hst-ui-coat-backstage.patch): the design tokens' pill and side panel
COAT_PILL = {False: (0xD5, 0xE5, 0xFA), True: (0x26, 0x3B, 0x5E)}
COAT_SIDE = {False: (0xEA, 0xF2, 0xFD), True: (0x18, 0x21, 0x30)}


def rgb(text):
    values = re.findall(r"\d+(?:\.\d+)?", text)
    return tuple(round(float(v)) for v in values[:3]) if len(values) >= 3 else None


def near(colour, expected, tolerance=2):
    return colour is not None and all(abs(a - b) <= tolerance for a, b in zip(colour, expected))


def check_coat_pill(office, frame, out, dark):
    """The selected item (Home, on opening) is a pill of the token colour, an item that is neither selected nor
    hovered shows the side panel. Skipped with the coat off (HST_UI_COAT=0)."""
    if os.environ.get("HST_UI_COAT") == "0":
        gui.record("coat pill (coat off: skipped)", True)
        return
    display = office.display
    gui.reopen(office, frame)
    gui.xdo(display, "mousemove", "800", "600")
    time.sleep(0.6)
    shot = os.path.join(out, "nav-coat.png")
    hst_gui.screenshot(shot, display)
    items = gui.view_items()
    # three quarters across: inside the pill (inset 8 px, and on GTK the theme's button padding), past the label
    for name, expected, label in (("Trang chủ", COAT_PILL[dark], "the selected item is the token pill"),
                                  ("Mới", COAT_SIDE[dark], "an item not selected shows the side panel")):
        box = items[name].queryComponent().getExtents(0)
        colour = rgb(pixel(shot, (box.x + box.width * 3 // 4, box.y + box.height // 2)))
        gui.record(label, near(colour, expected), (name, colour, expected))
