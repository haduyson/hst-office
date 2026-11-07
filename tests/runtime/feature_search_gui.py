# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-feature-search.py: the HST menu, the search popup and the button of the ribbon."""
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
