# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Linux collector for ribbon_mockup_geometry: the showing nodes of the ribbon band through AT-SPI (gtk3, Xvfb).

Run as the build user under dbus-run-session with pyatspi available (see check-ribbon-mockup.py).
"""
import pyatspi

import ribbon_tabs_gui as gui

SKIP_ROLES = ("document text", "table", "ruler", "status bar", "menu bar")
BAND_BOTTOM = 230  # the ribbon band of the window: tab row, group captions and buttons
MAX_DEPTH = 16


def _box(node):
    try:
        if node.getState().contains(pyatspi.STATE_SHOWING):
            return tuple(gui.extents(node))
    except Exception:  # noqa: BLE001 - widgets come and go
        pass
    return None


def _collect(node, ancestors, out, depth=0):
    """Appends (role, name, box, ancestor_boxes) for every showing node in the ribbon band."""
    if node is None or depth > MAX_DEPTH:
        return
    try:
        role = node.getRoleName()
        if role in SKIP_ROLES:
            return
        box = _box(node)
        if box is not None and box[1] < BAND_BOTTOM:
            out.append((role, node.name or "", box, list(ancestors)))
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))]
    except Exception:  # noqa: BLE001
        return
    for child in children:
        if child is not None:
            _collect(child, ancestors + [box], out, depth + 1)


def ribbon_nodes():
    """Showing ribbon nodes of the office window, as (role, name, box, ancestor_boxes)."""
    out = []
    _collect(gui.office_app(), [], out)
    return out
