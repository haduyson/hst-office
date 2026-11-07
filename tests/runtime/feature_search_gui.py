# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-feature-search.py: the HST menu, the search popup and the search box of the ribbon tab row."""
import os
import subprocess
import time

import hst_gui
from nd30_entry_gui import office_app


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=20)


def walk(node, out, depth=0):
    """(depth, role, name, node) of the UI widgets; document content (a sheet exposes every cell) is skipped."""
    try:
        role = node.getRoleName()
        out.append((depth, role, node.name, node))
        if role.startswith("document") or node.childCount > 500:
            return out
        for index in range(node.childCount):
            walk(node.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def nodes(app):
    return walk(app, []) if app is not None else []


def hst_menu(app):
    """(menu accessible, [item names]) of the HST menu, like check-nd30-entry.py but with the pruned walk."""
    found = nodes(app)
    for position, (depth, role, name, node) in enumerate(found):
        if role == "menu" and name == "HST":
            items = []
            for later_depth, later_role, later_name, _ in found[position + 1:]:
                if later_depth <= depth:
                    break
                if later_depth == depth + 1 and "item" in later_role and later_name:
                    items.append(later_name)
            return node, items
    return None, []


def extents(node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    return box.x, box.y, box.width, box.height


BOX_NAMES = ("Tìm tính năng", "Search features")


def search_box(office, app=None):
    """Box (x, y, width, height) of the shown search box of the ribbon tab row, or None. AT-SPI lists the box as a push
    button of the page tab list; without it, the UITest service finds it by its id "hst-tab-search" (AbsPosition is
    relative to the frame, which sits at the screen origin under Xvfb without a window manager)."""
    for _depth, role, _name, node in nodes(app) if app is not None else []:
        if role != "page tab list":
            continue
        for index in range(node.childCount):
            child = node.getChildAtIndex(index)
            if child is not None and child.getRoleName() == "push button" and (child.name or "").startswith(BOX_NAMES):
                box = extents(child)
                return box if box[2] > 0 else None
    for _ in range(5):  # the document window may take a moment to become the focused top window
        top = office.service("org.libreoffice.uitest.UITest").getTopFocusWindow()
        if "hst-tab-search" in top.getChildren():
            state = {p.Name: p.Value for p in top.getChild("hst-tab-search").getState()}
            if state.get("ReallyVisible") != "true":
                return None
            x, y = (int(v) for v in state["AbsPosition"].split("x"))
            width, height = (int(v) for v in state["Size"].split("x"))
            return (x, y, width, height) if width > 0 else None
        time.sleep(1)
    return None


def tab_boxes(app):
    """Boxes of the showing ribbon tabs (the tab row lies above y 100)."""
    found = []
    for _depth, role, _name, node in nodes(app):
        try:
            if role == "page tab" and 0 < extents(node)[2] and extents(node)[1] < 100:
                found.append(extents(node))
        except Exception:  # noqa: BLE001
            continue
    return found


def under(popup, box):
    """The popup's entry opens right under the box and starts within its width."""
    if popup is None or box is None:
        return False
    entry = extents(popup)
    return box[1] + box[3] - 4 <= entry[1] <= box[1] + box[3] + 120 and box[0] - 20 <= entry[0] < box[0] + box[2]


def popup_entry(app):
    """The search entry of the open popup (its placeholder makes it the only focused text entry), or None."""
    import pyatspi
    for _depth, role, _name, node in nodes(app):
        if role == "text" and node.getState().contains(pyatspi.STATE_FOCUSED):
            return node
    return None


def results(app):
    """Labels of the result rows shown by the popup (table cells of its tree view)."""
    return [name for _depth, role, name, _node in nodes(app) if role == "table cell" and name]


def search(office, display, query, shot):
    xdo(display, "key", "shift+Escape")
    time.sleep(1.5)
    xdo(display, "type", "--delay", "60", query)
    time.sleep(2)
    rows = results(office_app())
    hst_gui.screenshot(shot, display)
    return rows


def close_popup(display):
    xdo(display, "key", "Escape")
    time.sleep(1)
