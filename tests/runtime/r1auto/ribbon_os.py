# SPDX-License-Identifier: AGPL-3.0-only
"""The ribbon as the OS accessibility tree shows it (UI Automation on Windows, AX on macOS).

UNO exposes no accessibility for toolkit windows on this engine, so the ribbon checks read the OS tree, as the Linux
checks read AT-SPI. Nodes come from native_tree.py as [role, name, [x, y, w, h]]; roles are normalised here.
Geometry is judged inside the tree's own coordinates. Pointer targets on macOS are mapped to the screen by one
calibration (the ribbon root's top-left onto the frame's client origin): AX reported the ribbon subtree about
150 points above where the screenshot shows it (r1-auto macOS run 42779349486)."""
import json
from support import native

KINDS = {"AXTabGroup": "ribbon", "Tab": "ribbon", "AXRadioButton": "tab", "TabItem": "tab",
         "AXGroup": "group", "Custom": "group", "AXStaticText": "label", "Text": "label",
         "AXButton": "button", "AXMenuButton": "button", "Button": "button", "SplitButton": "button",
         "AXLink": "link", "Hyperlink": "link", "AXTextField": "edit", "AXComboBox": "edit", "Edit": "edit",
         "ComboBox": "edit", "ListItem": "item", "MenuItem": "item", "AXMenuItem": "item", "AXRow": "item",
         "AXCell": "item", "TreeItem": "item", "AXWindow": "window", "Window": "window"}


class Node:
    def __init__(self, raw, name, box):
        self.raw, self.kind, self.name = raw, KINDS.get(raw, raw), (name or "").strip()
        self.x, self.y, self.w, self.h = box if box else (0, 0, 0, 0)

    @property
    def box(self):
        return [self.x, self.y, self.w, self.h]

    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def contains(self, other, slack=2):
        cx, cy = other.center()
        return self.x - slack <= cx <= self.x + self.w + slack and self.y - slack <= cy <= self.y + self.h + slack


def read(e, label=None):
    """Current OS tree of the office (all its windows); kept as evidence when `label` is given."""
    raw = native("tree", 2500, timeout=180)
    if label:
        (e.out / f"os-tree-{label}.log").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return [Node(*row) for row in raw if isinstance(row, list) and len(row) == 3 and row[2]]


def ribbon_frame(nodes):
    frames = [n for n in nodes if n.kind == "ribbon" and n.w > 200]
    return max(frames, key=lambda n: n.w * n.h) if frames else None


def scan(nodes):
    """Groups (with captions), folded group buttons, the chevron and the banner, like ribbon_fit.scan did over UNO."""
    frame = ribbon_frame(nodes)
    if frame is None:
        return dict(frame=None, groups={}, buttons={}, banner=None, chevron=None)
    tabs = [n for n in nodes if n.kind == "tab" and n.h > 0 and frame.contains(n)]
    top = max((t.y + t.h for t in tabs), default=frame.y + 30)
    band = [n for n in nodes if n.w > 0 and n.h > 0 and n.y >= top - 2 and n.y + n.h <= frame.y + frame.h + 8]
    boxes = [n for n in band if n.kind == "group" and 50 <= n.h <= 140]
    groups = {}
    for caption in (n for n in band if n.kind == "label" and n.name):
        holders = [g for g in boxes if g.contains(caption) and g.w >= caption.w - 4]
        if holders:
            groups[caption.name] = min(holders, key=lambda g: g.w * g.h).box
    inside = lambda b: any(b.x >= g[0] - 1 and b.x + b.w <= g[0] + g[2] + 1 for g in groups.values())  # noqa: E731
    buttons = {b.name: b.box for b in band if b.kind == "button" and b.name and b.h >= 60 and not inside(b)}
    chevron = next((b.box for b in band if b.kind == "button" and b.name in ("", "»") and b.w <= 35 and b.h >= 60), None)
    # The banner rotates between products (HASON TECH, AIOS, ...): it is the one tall link (AX) or edit (UIA) of the
    # ribbon, never matched by its name (r1-auto Windows run 42785792856 at 1300 px).
    banner = next((n.box for n in nodes if n.kind in ("link", "edit") and n.w >= 100 and n.h >= 40
                   and frame.contains(n, slack=20)), None)
    return dict(frame=frame.box, groups=groups, buttons=buttons, banner=banner, chevron=chevron)


def screen_mapper(e, nodes, window):
    """(dx, dy) to add to tree coordinates for pointer targets: identity on Windows (UIA is in screen pixels)."""
    if e.office.system != "Darwin":
        return 0, 0
    frame = ribbon_frame(nodes)
    roots = [n for n in nodes if n.kind == "group" and frame and n.w >= frame.w and n.y <= frame.y]
    root = min(roots, key=lambda n: n.y) if roots else frame
    client = window.getPosSize()
    return client.X - root.x, client.Y - root.y


def named(nodes, *texts):
    return [n for n in nodes if any(t in n.name for t in texts)]
