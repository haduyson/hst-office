# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-nd30-entry.py: the HST menu through AT-SPI, windows and crops of screenshots."""
import os
import re
import subprocess
import time

import hst_gui
import ribbon_tabs_gui as ribbon


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


def crop_ribbon(full, geometry, target, button=None):
    """Top of the Writer window (tabs and Home ribbon) with a red frame around the ND 30 button, for the help guide."""
    from PIL import Image, ImageDraw
    x, y, width, _height = geometry
    image = Image.open(full).convert("RGB")
    bottom = y + 160
    if button:
        bx, by, bw, bh = button
        ImageDraw.Draw(image).rectangle((bx, by, bx + bw, by + bh), outline=(220, 30, 30), width=3)
        bottom = max(bottom, by + bh + 6)
    image.crop((x, y, x + width, bottom)).save(target)


def wait_window(office, pattern, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for wid, name in hst_gui.toplevels(office.display, office.pid):
            if re.search(pattern, name):
                return wid, name
        time.sleep(1)
    return None, None


def home_button(name, timeout=10):
    """Find exactly one visible button in Home's Tools group, using its current accessible bounds."""
    deadline = time.time() + timeout
    while True:
        matches = [box for title, _role, box, _node in ribbon.ribbon_nodes(("push button", "toggle button"))
                   if title == name and box[0] >= 0 and box[1] > 40]
        if len(matches) == 1:
            return matches[0]
        if time.time() >= deadline:
            return None
        time.sleep(0.5)
