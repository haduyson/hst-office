# SPDX-License-Identifier: AGPL-3.0-only
"""What check-update-lock.py reads from the running office: the state the HST protocol handler reports for a
command, and the entries of the ribbon's ≡ menu.

The Tabbed UI has no "Kiểm tra cập nhật" button on a ribbon tab: the entry sits in the ≡ menu at the right end of
the ribbon (hst-ribbon-hst-commands.patch, popupmenu/notebookbar.xml). That menu leaves out an entry whose command
reports disabled, so under the administrator lock it is one entry shorter than with the manual check allowed.
"""
import os
import re
import subprocess
import time

import hst_gui

BURGER_FROM_RIGHT, BURGER_Y = 29, 22  # the ≡ button, measured from the window's right edge (vi_VN, gtk3)
INK, LINE_GAP = 130, 4  # menu text is darker than INK; text lines are further apart than LINE_GAP pixels


def command_enabled(office, frame, command):
    """IsEnabled that the HST protocol handler reports for `command` (what the menu shows)."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL
    states = []

    class Listener(unohelper.Base, XStatusListener):
        def statusChanged(self, event):
            states.append(event.IsEnabled)

        def disposing(self, event):
            pass

    url = URL()
    url.Complete = command
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if dispatch is None:
        return None
    listener = Listener()
    dispatch.addStatusListener(listener, url)
    time.sleep(1)
    return states[-1] if states else None


def _document_window(office):
    windows = [w for w in hst_gui.toplevels(office.display, office.pid) if "HST" in w[1]]
    if not windows:
        return None
    info = subprocess.run(["xwininfo", "-display", office.display, "-id", windows[0][0]], capture_output=True, text=True).stdout
    width = int(re.search(r"Width:\s+(\d+)", info).group(1))
    return windows[0][0], width


def _root_children(display):
    """{window id: (x, y, width, height)} of the mapped children of the root window (popup menus are among them)."""
    out = subprocess.run(["xwininfo", "-display", display, "-root", "-children"], capture_output=True, text=True).stdout
    found = {}
    for wid, w, h, x, y in re.findall(r"^\s*(0x[0-9a-f]+) .*?: \(.*?\)\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", out, re.M):
        state = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
        if "IsViewable" in state:
            found[wid] = (int(x), int(y), int(w), int(h))
    return found


def burger_menu_rows(office, shot):
    """Number of entries the ribbon's ≡ menu shows, counted as text lines in the popup window that opening it maps;
    `shot` keeps the open menu for review. None when the document window or the popup is not found."""
    from PIL import Image
    found = _document_window(office)
    if found is None:
        return None
    wid, width = found
    env = dict(os.environ, DISPLAY=office.display)
    office.raise_windows()
    time.sleep(0.5)
    before = _root_children(office.display)
    subprocess.run(["xdotool", "mousemove", "--window", wid, str(width - BURGER_FROM_RIGHT), str(BURGER_Y), "click", "1"],
                   env=env, check=False, timeout=10)
    time.sleep(1.5)
    popups = [box for key, box in _root_children(office.display).items() if key not in before and box[3] > 40]
    hst_gui.screenshot(shot, office.display)
    subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
    time.sleep(0.5)
    if not popups:
        return None
    x0, y0, w, h = max(popups, key=lambda box: box[2] * box[3])
    image = Image.open(shot).convert("L")
    lines, inside, gap = 0, False, 0
    for y in range(max(y0, 0), min(y0 + h, image.height)):
        ink = any(image.getpixel((x, y)) < INK for x in range(max(x0, 0) + 8, min(x0 + w * 3 // 5, image.width)))
        if ink:  # labels only: submenu arrows and shortcuts sit in the right part of the menu
            lines += not inside
            inside, gap = True, 0
        elif inside:
            gap += 1
            inside = gap < LINE_GAP
    return lines
