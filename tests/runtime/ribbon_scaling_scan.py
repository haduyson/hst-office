# SPDX-License-Identifier: AGPL-3.0-only
"""What check-ribbon-scaling.py reads from the ribbon at one width: group toolbars and panels, the chevron, the banner
and the ribbon height, through AT-SPI."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_banner_probe as probe  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402


def showing(node):
    import pyatspi
    return node.getState().contains(pyatspi.STATE_SHOWING)


def caption(panel):
    """The caption of a group panel: its label child (a group button carries the same text)."""
    try:
        for index in range(panel.childCount):
            child = panel.getChildAtIndex(index)
            if child is not None and child.getRoleName() == "label" and child.name:
                return child.name
        return panel.name or ""
    except Exception:  # noqa: BLE001
        return ""


def scan(display):
    """{toolbar key: box} of the ribbon groups, the chevron box or None, the banner box or None, ribbon height.

    The toolbar boxes come with three entries: "__groups__" {group key: panel box}, "__names__" {group
    key: caption} and "__buttons__" {caption: box} of the groups shown as their button (collapsed groups).

    The ribbon groups are the toolbars between the tab row and the bottom of the banner slot (which is
    centred on the ribbon page), so the formula bar and the drawing toolbar below the ribbon are not."""
    found, chevron, banner, buttons = [], None, None, {}
    for node in gui.walk(gui.office_app()):
        try:
            if not showing(node):
                continue
            role, name, box = node.getRoleName(), node.name or "", gui.extents(node)
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
        if role == "tool bar" and 40 <= box[1] and box[1] + box[3] <= 260 and box[2] > 0:
            names = []
            for index in range(min(node.childCount, 3)):
                try:
                    names.append(node.getChildAtIndex(index).name or "?")
                except Exception:  # noqa: BLE001
                    names.append("?")
            key = "|".join(names) + f"@{node.childCount}"
            try:  # the group is the toolbar's parent panel (the grid of one ribbon group)
                parent = node.parent
                group = gui.extents(parent) if parent is not None else None
            except Exception:  # noqa: BLE001
                parent, group = None, None
            # the caption sits in the group's grid, which may hold the toolbar through a box
            name, holder = "", parent
            for _level in range(3):
                if holder is None or name:
                    break
                name, holder = caption(holder), holder.parent
            found.append((key, box, group, name))
        elif role == "push button" and not name and box[2] <= 30 and box[3] >= 60 and box[1] < 260:
            chevron = box
        elif role == "push button" and name and box[3] >= 60 and 40 <= box[1] < 260:
            buttons[name] = box  # a group collapsed into its button (caption and arrow)
        elif role == "link" and box[1] < 260 and box[3] >= 40:
            banner = box
    limit = banner[1] + banner[3] + 8 if banner else 175
    inside = [entry for entry in found if entry[1][1] + entry[1][3] <= limit]
    bars = {key: box for key, box, _group, _caption in inside}
    # each group by the sorted keys of its toolbars, with the width of the group panel
    members, captions = {}, {}
    for key, _box, group, name in inside:
        if group:
            members.setdefault(tuple(group), []).append(key)
            captions[tuple(group)] = name
    groups = {"+".join(sorted(keys)): list(box) for box, keys in members.items()}
    bars["__groups__"] = groups
    bars["__names__"] = {"+".join(sorted(keys)): captions[box] for box, keys in members.items()}
    bars["__buttons__"] = buttons
    top, tabs = probe.doc_tabs_top(display, timeout=5)
    return bars, chevron, banner, (tabs - top) if tabs is not None else None
