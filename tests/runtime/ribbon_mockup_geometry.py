# SPDX-License-Identifier: AGPL-3.0-only
"""Measures a Writer ribbon tab through AT-SPI and classifies its groups as L, M, S or C (the mockup's ladder).

The measurement is read from the accessible tree of one open window: a group is the nearest ancestor of its caption
label that is at least GROUP_MIN_H tall; its buttons give the state (L: a tall large button, C: one folded button that
is at least FOLDED_MIN_H tall, M: a wide small button, S: an icon-only small button). The classification is a heuristic
until the label widths of phase 0 are available; check-ribbon-mockup.py reports it with that caveat.
"""
import pyatspi

import ribbon_tabs_gui as gui

CAPTIONS = {  # expected-JSON key -> caption text of the group on the Writer ribbon (Trang đầu, Chèn)
    "home": {"clip": "Bảng tạm", "font": "Phông chữ", "para": "Đoạn văn", "edit": "Chỉnh sửa", "viet": "Tiện ích Việt"},
    "insert": {"pages": "Trang", "tables": "Bảng", "illus": "Minh họa", "links": "Liên kết", "comments": "Chú thích",
               "hf": "Đầu trang và chân trang", "text": "Văn bản", "symbols": "Ký hiệu"},
}
FOLDED = {"home": {"styles": "Kiểu"}}  # groups whose only accessible node is a folded or gallery button
GROUP_MIN_H = 90  # the body of a ribbon group is 106 px; its caption sits at its bottom
FOLDED_MIN_H = 90  # a folded group button is 98 px tall
LARGE_MIN_H = 60  # a large button: icon over label, 63 px in the reference
BUTTON_ROLES = ("push button", "toggle button", "push button menu", "menu button")
from ribbon_mockup_rules import LEVEL, compare_states, is_monotonic  # noqa: E402,F401


def _showing(node):
    try:
        return node.getState().contains(pyatspi.STATE_SHOWING) and gui.extents(node)[2] > 0
    except Exception:  # noqa: BLE001 - widgets come and go
        return False


def _collect(node, ancestors, out, depth=0):
    """Appends (node, role, name, box, ancestors) for every showing node in the ribbon band of the window."""
    if node is None or depth > 16:
        return
    try:
        role = node.getRoleName()
        if role in ("document text", "table", "ruler", "status bar", "menu bar"):
            return
        box = gui.extents(node) if node.getState().contains(pyatspi.STATE_SHOWING) else None
        if box is not None and box[1] < 230:
            out.append((node, role, node.name or "", box, ancestors))
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))]
    except Exception:  # noqa: BLE001
        return
    for child in children:
        if child is not None:
            _collect(child, ancestors + [node], out, depth + 1)


def ribbon_nodes():
    """Showing ribbon nodes (node, role, name, box, ancestors) of the Writer window."""
    out = []
    _collect(gui.office_app(), [], out)
    return out


def _inside(box, outer):
    return box[0] >= outer[0] - 1 and box[0] + box[2] <= outer[0] + outer[2] + 1


def _state(buttons, folded):
    """L, M, S or C from the buttons of one group, given its folded flag."""
    if folded or (len(buttons) == 1 and buttons[0][1][3] >= FOLDED_MIN_H):
        return "C"
    if any(box[3] >= LARGE_MIN_H for _n, box in buttons):
        return "L"
    if any(box[2] > 40 for _n, box in buttons):
        return "M"
    return "S"


def groups(nodes, tab):
    """{key: {"state", "box", "caption_bottom", "buttons"}} for the groups of tab ("home" or "insert") that are showing."""
    found = {}
    for key, caption in CAPTIONS[tab].items():
        label = next((n for n in nodes if n[1] == "label" and n[2] == caption and n[3][3] <= 30), None)
        if label is None:
            continue
        group = next((a for a in reversed(label[4]) if gui.extents(a)[3] >= GROUP_MIN_H), None)
        if group is None:
            continue
        gbox = gui.extents(group)
        buttons = [(n[2], n[3]) for n in nodes if n[1] in BUTTON_ROLES and _inside(n[3], gbox)
                   and n[3][1] < label[3][1] + label[3][3] and n[3][1] >= gbox[1]]
        found[key] = {"state": _state(buttons, False), "box": gbox, "caption_bottom": label[3][1] + label[3][3],
                      "buttons": buttons}
    for key, caption in FOLDED.get(tab, {}).items():
        button = next((n for n in nodes if n[1] in BUTTON_ROLES and n[2] == caption and n[3][3] >= 40), None)
        if button is not None:
            found[key] = {"state": _state([(button[2], button[3])], button[3][3] >= FOLDED_MIN_H), "box": button[3],
                          "caption_bottom": button[3][1] + button[3][3], "buttons": [(button[2], button[3])]}
    return found


def named_box(nodes, name, roles=("panel", "push button", "toggle button", "label", "link")):
    """Box of the first showing node with this name (font combo "Tên phông", size "Kích cỡ phông", banner link)."""
    node = next((n for n in nodes if n[2] == name and n[1] in roles), None)
    return node[3] if node else None


def banner(nodes):
    """Box of the banner link: a link wider than 100 px in the ribbon band."""
    node = next((n for n in nodes if n[1] == "link" and n[3][2] > 100), None)
    return node[3] if node else None


def tab_geometry(nodes):
    """Tab row top, body (from the top of a group to its caption's bottom, the mockup's 106 px) and the document strip."""
    tab_top = next((n[3][1] for n in nodes if n[1] == "page tab" and n[2] == "Trang đầu"), None)
    strip = next((n[3] for n in nodes if n[1] == "panel" and n[2] == "Thẻ tài liệu"), None)
    return tab_top, strip
