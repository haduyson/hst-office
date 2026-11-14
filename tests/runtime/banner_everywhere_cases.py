# SPDX-License-Identifier: AGPL-3.0-only
"""check-banner-everywhere.py: the user interfaces of each app and what makes one banner case pass."""
import ribbon_banner_probe as probe

NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides", "draw": "HST Draw"}
# the user interfaces each app offers in View > User Interface (officecfg ToolbarMode.xcu, experimental ones aside)
MODES = {
    "writer": ("Default", "Single", "Sidebar", "notebookbar.ui", "notebookbar_compact.ui",
               "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui"),
    "calc": ("Default", "Single", "Sidebar", "notebookbar.ui", "notebookbar_compact.ui",
             "notebookbar_groupedbar_compact.ui"),
    "impress": ("Default", "Single", "notebookbar.ui", "notebookbar_compact.ui",
                "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui"),
    "draw": ("Default", "notebookbar.ui", "notebookbar_compact.ui", "notebookbar_groupedbar_compact.ui",
             "notebookbar_single.ui"),
}
MIN_W, MIN_H = 260, 75


LABELS = {"Default": "standard", "Single": "single-toolbar", "Sidebar": "sidebar", "notebookbar.ui": "tabbed",
          "notebookbar_compact.ui": "tabbed-compact", "notebookbar_groupedbar_compact.ui": "groupedbar-compact",
          "notebookbar_single.ui": "contextual-single"}


def mode_label(mode):
    return LABELS.get(mode, mode)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def judge(boxes, frame, shot, catalogue):
    """(ok, detail) for the visible banner boxes [x, y, w, h] of one screenshot of the window frame."""
    if len(boxes) != 1:
        return False, f"{len(boxes)} banners visible"
    x, y, w, h = boxes[0]
    fx, fy, fw, fh = frame
    if w < MIN_W - 1 or h < MIN_H - 1:
        return False, f"banner {w}x{h} smaller than {MIN_W}x{MIN_H}"
    if x < fx or y < fy or x + w > fx + fw or y + h > fy + fh // 2:
        return False, f"banner {boxes[0]} outside the window's top chrome {frame}"
    ident, best, second = probe.recognise(shot, boxes[0], catalogue, 1)
    if ident is None:
        return False, f"banner {boxes[0]} is not a bundled artwork (score {best}, next {second})"
    return True, f"{ident} at {boxes[0]}"


def root_pane_shift(node):
    """gtk3 reports the VCL root pane at the top of its parent, ignoring the native menu bar above it: the
    vertical distance to add to the boxes of the controls inside it (0 without a menu bar)."""
    import pyatspi
    while node is not None and node.getRoleName() != "root pane":
        node = node.parent
    if node is None or node.parent is None:
        return 0
    return (node.parent.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).y
            - node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).y)


def visible_boxes(frame):
    fx, fy, fw, fh = frame
    boxes = []
    for node in probe.banner_nodes():
        record = probe.describe(node)
        if " — " not in (record["name"] or ""):
            continue
        record["box"][1] += root_pane_shift(node)
        x, y, w, h = record["box"]
        if w > 0 and h > 0 and x < fx + fw and y < fy + fh and x + w > fx and y + h > fy:
            boxes.append(record["box"])
    return boxes
