# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-nd30-entry.py: the HST menu through AT-SPI, windows and crops of screenshots."""
import os
import re
import subprocess
import time

import hst_gui


def walk(accessible, out=None, depth=0):
    out = out if out is not None else []
    try:
        out.append((depth, accessible.getRoleName(), accessible.name, accessible))
        for index in range(accessible.childCount):
            walk(accessible.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            return app
    return None


def hst_menu(app):
    """(menu accessible, [item names]) of the HST menu in the current window, or (None, [])."""
    nodes = walk(app)
    for position, (depth, role, name, node) in enumerate(nodes):
        if role == "menu" and name == "HST":
            items = []
            for later_depth, later_role, later_name, _ in nodes[position + 1:]:
                if later_depth <= depth:
                    break
                if later_depth == depth + 1 and "item" in later_role and later_name:
                    items.append(later_name)
            return node, items
    return None, []


def window_geometry(wid, display):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    values = [int(re.search(label + r":\s+(-?\d+)", info).group(1)) for label in
              ("Absolute upper-left X", "Absolute upper-left Y", "Width", "Height")]
    return tuple(values)


def open_menu_screenshot(menu, office, args, target):
    """Click the HST menu (position from AT-SPI) and save a screenshot of the open menu; never fails the run."""
    import pyatspi
    try:
        box = menu.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        env = dict(os.environ, DISPLAY=args.display)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        subprocess.run(["xdotool", "mousemove", str(box.x + box.width // 2), str(box.y + box.height // 2), "click", "1"], env=env, check=False)
        time.sleep(1.5)
        hst_gui.screenshot(target, args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False)
        time.sleep(1)
    except Exception as error:  # noqa: BLE001
        print("menu screenshot skipped:", error)


def crop_window(full, geometry, target):
    from PIL import Image
    x, y, width, height = geometry
    Image.open(full).crop((max(x, 0), max(y, 0), x + width, y + height)).save(target)


def crop_ribbon(full, geometry, target):
    """Top of the Writer window (tabs and Home ribbon) with a red frame around the ND 30 button, for the help guide."""
    from PIL import Image, ImageDraw
    x, y, width, _height = geometry
    image = Image.open(full).convert("RGB")
    left = x + width - 150  # button measured on the 1366x768 test display
    ImageDraw.Draw(image).rectangle((left, y + 122, x + width - 6, y + 148), outline=(220, 30, 30), width=3)
    image.crop((x, y, x + width, y + 160)).save(target)


def wait_window(office, pattern, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for wid, name in hst_gui.toplevels(office.display, office.pid):
            if re.search(pattern, name):
                return wid, name
        time.sleep(1)
    return None, None


def _windows(display):
    """{window id: (x, y, width, height)} of the direct children of the root window."""
    out = subprocess.run(["xwininfo", "-display", display, "-root", "-children"], capture_output=True, text=True).stdout
    found = {}
    for match in re.finditer(r"(?m)^\s*(0x[0-9a-f]+) .*?\s(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\s", out):
        found[match.group(1)] = (int(match.group(4)), int(match.group(5)), int(match.group(2)), int(match.group(3)))
    return found


def open_home_block(office, display):
    """The block at the right of the Home tab folds into a button when the groups need the room: open it.
    Returns (x, y, width, height) of its popup, or None when the block is not folded."""
    top = office.service("org.libreoffice.uitest.UITest").getTopFocusWindow()
    if "Home-Menu" not in top.getChildren():
        return None
    state = {p.Name: p.Value for p in top.getChild("Home-Menu").getState()}
    x, y = (int(v) for v in state["AbsPosition"].split("x"))
    width, height = (int(v) for v in state["Size"].split("x"))
    if width > 40:  # shown in full, not folded
        return None
    before = _windows(display)
    subprocess.run(["xdotool", "mousemove", str(x + width - 7), str(y + height // 2), "click", "1"],
                   env=dict(os.environ, DISPLAY=display), check=False)
    time.sleep(1.5)
    fresh = [box for wid, box in _windows(display).items() if wid not in before and box[2] > 100 and box[0] >= 0]
    return fresh[0] if fresh else None


def click_in_home_block(office, display, from_right):
    """Click on the bottom row of the folded block, this many pixels from its right end. Returns the popup box, or None."""
    popup = open_home_block(office, display)
    if popup:
        subprocess.run(["xdotool", "mousemove", str(popup[0] + popup[2] - from_right), str(popup[1] + popup[3] - 22), "click", "1"],
                       env=dict(os.environ, DISPLAY=display), check=False)
    return popup
