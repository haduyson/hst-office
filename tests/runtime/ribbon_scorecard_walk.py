# SPDX-License-Identifier: AGPL-3.0-only
"""Layout reading of the ribbon scorecard's live part: the tab strip, group captions and boxes, chevron, banner and
height, read through AT-SPI with a walk that stays out of the document area."""
import sys
import json
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_tabs_gui as gui  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BAND = 260  # the ribbon lies above this y (window at 0,0)
PARK = (700, 600)  # pointer rest position, over the document


def load_config(path=os.path.join(HERE, "ribbon-scorecard-widths.json")):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _state(node, name):
    import pyatspi
    return node.getState().contains(getattr(pyatspi, name))


def _has_toolbar(panel):
    return any((panel.getChildAtIndex(i) is not None and panel.getChildAtIndex(i).getRoleName() == "tool bar")
               for i in range(min(panel.childCount, 60)))


def group_panel(label):
    """The group a caption belongs to: its parent, or, when the caption sits in a caption row with a launcher, the
    panel above that row (the first ancestor that holds toolbars)."""
    node = label.parent
    for _ in range(3):
        if node is None:
            return None
        if _has_toolbar(node):
            return node
        node = node.parent
    return label.parent


def is_group_caption(node, box):
    """A group caption: a label that names its group (Writer exposes the relation), or, where the relation is not
    exposed (Sheets), a label on the bottom row of a panel that holds toolbars."""
    import pyatspi
    if any(r.getRelationType() == pyatspi.RELATION_LABEL_FOR for r in node.getRelationSet()):
        return True
    parent = group_panel(node)
    if parent is None or parent.getRoleName() != "panel" or not _has_toolbar(parent):
        return False
    px_, py_, pw_, ph_ = gui.extents(parent)
    return box[1] + box[3] >= py_ + ph_ - 4 and box[2] >= pw_ - 60


def ribbon_walk(node, depth=0):
    """Like ribbon_tabs_gui.walk, but it does not enter the document area or the sidebar (everything below the ribbon):
    those trees are large, and a walk through them takes seconds once they hold the focus."""
    if node is None:
        return
    yield node
    try:
        if depth >= 16 or node.getRoleName() in gui.SKIP:
            return
        if depth > 2 and gui.extents(node)[1] >= 200:
            return
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))]
    except Exception:  # noqa: BLE001 - widgets come and go
        return
    for child in children:
        if child is not None:
            yield from ribbon_walk(child, depth + 1)


def popup_nodes():
    """Every node of the office's popup windows and menus (top-level children other than the document frame)."""
    app = gui.office_app()
    for index in range(app.childCount if app else 0):
        try:
            top = app.getChildAtIndex(index)
            if top is None or top.getRoleName() == "frame":
                continue
        except Exception:  # noqa: BLE001
            continue
        yield from gui.walk(top)


def layout():
    """One AT-SPI pass over the ribbon: tabs, groups, chevron, buttons, banner and document-tab row."""
    tabs, groups, buttons, chevron, banner, doc_tabs, frame = [], [], [], None, None, None, None
    for node in ribbon_walk(gui.office_app()):
        try:
            role, name = node.getRoleName(), node.name or ""
            if role == "frame" and frame is None:
                frame = gui.extents(node)[1]
                continue
            if role == "panel" and name == "Thẻ tài liệu":
                doc_tabs = gui.extents(node)[1]
                continue
            if not gui.showing(node):
                continue
            box = list(gui.extents(node))
            if box[1] >= BAND:
                continue
            if role == "page tab" and box[1] < 100:
                tabs.append({"name": name, "box": box, "selected": _state(node, "STATE_SELECTED")})
            elif role == "label" and name and is_group_caption(node, box):
                parent = group_panel(node)
                groups.append({"caption": name, "caption_box": box, "box": list(gui.extents(parent)) if parent else box})
            elif role in ("push button", "toggle button", "menu button"):
                if not name and box[2] <= 30 and box[3] >= 30 and 40 < box[1] < 200:
                    chevron = box
                buttons.append({"name": name, "role": role, "box": box,
                                "checked": _state(node, "STATE_CHECKED") or _state(node, "STATE_PRESSED")})
            elif role == "link" and banner is None and box[2] > 100:
                banner = box
        except Exception:  # noqa: BLE001 - widgets come and go while the ribbon re-lays out
            continue
    tabs.sort(key=lambda t: t["box"][0])
    groups.sort(key=lambda g: g["box"][0])
    height = doc_tabs - frame if doc_tabs is not None and frame is not None else None
    return {"tabs": tabs, "groups": groups, "buttons": buttons, "chevron": chevron, "banner": banner, "height": height}


def _summary(data):
    return json.dumps([[g["caption"], g["box"]] for g in data["groups"]] + [data["chevron"], data["banner"], data["height"]])


def stable_layout(tries=8, pause=1.0):
    """Measure until two passes in a row agree (the ribbon re-lays out for a moment after a resize)."""
    last = layout()
    for _ in range(tries):
        time.sleep(pause)
        now = layout()
        if _summary(now) == _summary(last):
            return now
        last = now
    return last

