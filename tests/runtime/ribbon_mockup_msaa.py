# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Windows collector for ribbon_mockup_geometry: parses the TSV of windows-ribbon-nodes.ps1 (MSAA through oleacc).

Each line is: index, parent index, depth, MSAA role, MSAA state, x, y, w, h, name. The boxes are made relative to the
window root (the first node of the dump), so the ribbon band is the same whatever the window's screen position.
"""
MSAA_ROLES = {37: "page tab", 43: "push button", 44: "toggle button", 56: "push button menu", 57: "menu button",
              41: "label", 30: "link", 16: "panel", 15: "document text", 42: "text", 22: "tool bar",
              21: "separator", 23: "status bar", 2: "menu bar", 24: "table", 33: "list", 34: "list item"}
INVISIBLE, OFFSCREEN = 0x8000, 0x10000
BAND_BOTTOM = 230
SKIP_ROLES = ("document text", "table", "status bar", "menu bar")


def parse(text):
    """[(role, name, box, ancestor_boxes)] of the showing ribbon band nodes, boxes relative to the window root."""
    rows = []
    for line in text.splitlines():
        parts = line.split("\t", 9)
        if len(parts) < 10:
            continue
        index, parent, depth, role, state, x, y, w, h = (int(v) for v in parts[:9])
        rows.append({"index": index, "parent": parent, "role": MSAA_ROLES.get(role, "other"), "state": state,
                     "box": (x, y, w, h), "name": parts[9]})
    if not rows:
        return []
    ox, oy = rows[0]["box"][0], rows[0]["box"][1]
    by_index = {r["index"]: r for r in rows}
    out = []
    for r in rows:
        if r["state"] & (INVISIBLE | OFFSCREEN) or r["box"][2] <= 0 or r["role"] in SKIP_ROLES:
            continue
        x, y, w, h = r["box"]
        box = (x - ox, y - oy, w, h)
        if box[1] >= BAND_BOTTOM:
            continue
        chain, p = [], r["parent"]
        while p in by_index:
            px, py, pw, ph = by_index[p]["box"]
            chain.append((px - ox, py - oy, pw, ph))
            p = by_index[p]["parent"]
        out.append((r["role"], r["name"], box, list(reversed(chain))))
    return out
