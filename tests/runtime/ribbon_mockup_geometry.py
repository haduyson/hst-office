# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Classifies the groups of a Writer ribbon tab as L, M, S or C (the mockup's ladder) from measured accessible nodes.

Input is a list of nodes (role, name, box, ancestor_boxes): box is (x, y, w, h) in pixels, ancestor_boxes the boxes of
the node's ancestors, nearest last. Collectors: ribbon_mockup_atspi.py (Linux) and ribbon_mockup_uno.py (Windows).
A group is the nearest ancestor of its caption label that is at least GROUP_MIN_H tall; its buttons give the state
(L: a tall large button, C: one folded button at least FOLDED_MIN_H tall, M: a wide small button, S: an icon-only
small button). Heuristic until the label widths of phase 0 are available.
"""
from ribbon_mockup_rules import LEVEL, compare_states, is_monotonic  # noqa: F401  re-exported for the checkers

CAPTIONS_BY_APP = {  # app -> tab -> expected-JSON key -> caption text of the group on that app's ribbon
    "writer": {
        "home": {"clip": "Bảng tạm", "font": "Phông chữ", "para": "Đoạn văn", "edit": "Chỉnh sửa", "viet": "Tiện ích Việt"},
        "insert": {"pages": "Trang", "tables": "Bảng", "illus": "Minh họa", "links": "Liên kết", "comments": "Chú thích",
                   "hf": "Đầu trang và chân trang", "text": "Văn bản", "symbols": "Ký hiệu"},
    },
    "calc": {  # Sheets: the cell styles (cellstyles) are part of Kiểu, the owner's decision; Ô is the cells group
        "home": {"clip": "Bảng tạm", "font": "Phông chữ", "align": "Căn chỉnh", "number": "Số", "edit": "Chỉnh sửa",
                 "cells": "Ô"},
        "insert": {"tables": "Bảng", "illus": "Minh họa", "charts": "Biểu đồ", "links": "Liên kết",
                   "comments": "Chú thích", "text": "Văn bản", "symbols": "Ký hiệu"},
    },
}
CAPTIONS = CAPTIONS_BY_APP["writer"]  # kept for the Writer callers
FOLDED_BY_APP = {  # groups whose only accessible node is a folded or gallery button, when folded
    "writer": {"home": {"styles": "Kiểu"}},
    "calc": {"home": {"styles": "Kiểu", "cells": "Ô", "edit": "Chỉnh sửa"}},
}
FOLDED = FOLDED_BY_APP["writer"]
GROUP_MIN_H = 90  # the body of a ribbon group is 106 px; its caption sits at its bottom
FOLDED_MIN_H = 90  # a folded group button is 98 px tall
LARGE_MIN_H = 40  # a large button: icon over label, 63 px in the reference
BUTTON_ROLES = ("push button", "toggle button", "push button menu", "menu button")
CAPTION_MAX_H = 30  # a caption label is one text line


def _inside(box, outer):
    return box[0] >= outer[0] - 1 and box[0] + box[2] <= outer[0] + outer[2] + 1


def _state(buttons, folded):
    """L, M, S or C from the buttons of one group: [(name, box)], and whether the group is a folded button."""
    if folded or (len(buttons) == 1 and buttons[0][1][3] >= FOLDED_MIN_H):
        return "C"
    if any(box[3] >= LARGE_MIN_H for _name, box in buttons):
        return "L"
    if any(box[2] > 40 for _name, box in buttons):
        return "M"
    return "S"


def groups(nodes, tab, app="writer"):
    """{key: {"state", "box", "caption_bottom", "buttons"}} for the groups of tab ("home" or "insert") that are showing."""
    found = {}
    for key, caption in CAPTIONS_BY_APP[app][tab].items():
        label = next((n for n in nodes if n[0] == "label" and n[1] == caption and n[2][3] <= CAPTION_MAX_H), None)
        if label is None:
            continue
        gbox = next((a for a in reversed(label[3]) if a is not None and a[3] >= GROUP_MIN_H), None)
        if gbox is None:
            continue
        bottom = label[2][1] + label[2][3]
        buttons = [(n[1], n[2]) for n in nodes if n[0] in BUTTON_ROLES and _inside(n[2], gbox)
                   and gbox[1] <= n[2][1] < bottom]
        found[key] = {"state": _state(buttons, False), "box": gbox, "caption_bottom": bottom, "buttons": buttons}
    for key, caption in FOLDED_BY_APP[app].get(tab, {}).items():
        button = next((n for n in nodes if n[0] in BUTTON_ROLES and n[1] == caption and n[2][3] >= 40), None)
        if button is not None:
            box = button[2]
            found[key] = {"state": _state([(button[1], box)], box[3] >= FOLDED_MIN_H), "box": box,
                          "caption_bottom": box[1] + box[3], "buttons": [(button[1], box)]}
    return found


def named_box(nodes, name, roles=("panel", "push button", "toggle button", "label", "link")):
    """Box of the first node with this name (font combo "Tên phông", size "Kích cỡ phông")."""
    node = next((n for n in nodes if n[1] == name and n[0] in roles), None)
    return node[2] if node else None


def banner(nodes):
    """Box of the banner link: a link wider than 100 px in the ribbon band."""
    # the document title button of the Tệp tin page (P4: id hst-file-title, a push button) is not the banner
    node = next((n for n in nodes if n[0] == "link" and n[2][2] > 100 and "— Tệp tin" not in n[1]), None)
    return node[2] if node else None


def tab_geometry(nodes):
    """(top of the Trang đầu page tab, box of the document tab strip)."""
    tab_top = next((n[2][1] for n in nodes if n[0] == "page tab" and n[1] == "Trang đầu"), None)
    strip = next((n[2] for n in nodes if n[0] == "panel" and n[1] == "Thẻ tài liệu"), None)
    return tab_top, strip


PAGE_TOP_OFFSET = (30, 42)  # the tab page starts 36 px under the tab row's top (P4: page y=44 under tab row y=8)
PAGE_MIN_W = 600


def page_box(nodes, tab_top):
    """Box of the selected tab's page (P4 definition of the 106 px body): the wide panel under the tab row."""
    if tab_top is None:
        return None
    for n in nodes:
        box = n[2]
        if n[0] == "panel" and PAGE_TOP_OFFSET[0] <= box[1] - tab_top <= PAGE_TOP_OFFSET[1] \
                and box[2] >= PAGE_MIN_W and box[3] >= 60:
            return box
    return None

