# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Check the four notebookbar.ui files of a patched tree against the owner-locked v3 ribbon (data/ribbon/ribbon-v3.json).

The v3 layout code (vcl HstRibbonV3Layout, hst-ribbon-v3-layout.patch) lays a group out only when its GtkGrid has a
valid "hst-ribbon-layout" whose kinds match its command children; anything else falls back to the 1.0.2 cells and
breaks the design without a build error. Per app this checks:

- every tab and group of the data is in the .ui, its groups in the data's order, and no other group in that tab's
  merged box has no layout (the File tab and the add-ons box are outside the design);
- each grid's layout is valid ("kinds=" one of L M S W G per command, "rows=" indexes within the kinds, "nofill");
- its children: one command per grid cell in rows 0-2 (left-attach = its index), the commands in the data's order with
  the data's kinds, one caption at row 3, at most one separator;
- the totals: tabs, groups, commands (82 / 329 / 1,607 for the 1.0.3 design with the owner's chemical formula button).

check_tree() returns a list of (app, tab, group, message) problems.
"""
import json
import os
import re

from lxml import etree as ET

import ribbon_v3_ui as v3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data/ribbon/ribbon-v3.json")
SPEC = re.compile(r"^kinds=(?P<kinds>[LMSWG]+)(?:;rows=(?P<rows>[0-9.|/]+))?(?P<nofill>;nofill)?$")
OUTSIDE = {"pmhbFile"}  # merged boxes outside the v3 design (the File tab's backstage groups)


def parse_spec(text):
    """(kinds, rows, nofill) of a layout, or None when it is malformed."""
    match = SPEC.match(text or "")
    if not match:
        return None
    rows = [] if not match["rows"] else [row.split(".") for row in match["rows"].split("/")]
    kinds = match["kinds"]
    for row in rows:
        for item in row:
            if item != "|" and (not item.isdigit() or int(item) >= len(kinds)):
                return None
    return kinds, rows, bool(match["nofill"])


def packing(child):
    pack = child.find("packing")
    values = {} if pack is None else {p.get("name"): p.text for p in pack.findall("property")}
    return int(values.get("left-attach", 0)), int(values.get("top-attach", 0))


def child_key(obj):
    """The command of one grid child: its tool item's action (without .uno: and arguments) or its menu button."""
    units = v3.units_of(obj, None)
    return units[0].key if len(units) == 1 else None


def check_group(grid, group):
    problems = []
    spec_text = v3.props(grid).get("hst-ribbon-layout")
    spec = parse_spec(spec_text)
    if spec is None:
        return [f"layout missing or malformed: {spec_text!r}"]
    kinds, _rows, nofill = spec
    if kinds != "".join(item["kind"] for item in group["items"]):
        problems.append(f"kinds {kinds} are not the data's {''.join(i['kind'] for i in group['items'])}")
    if nofill != bool(group.get("nofill")):
        problems.append("nofill differs from the data")
    commands, captions, separators = [], 0, 0
    for child in grid.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        left, top = packing(child)
        if obj.get("class") == "GtkSeparator":
            separators += 1
        elif top >= 3:
            captions += 1
        else:
            commands.append((left, child_key(obj)))
    if captions != 1:
        problems.append(f"{captions} captions at row 3 (one expected)")
    if separators > 1:
        problems.append(f"{separators} separators")
    if [left for left, _ in commands] != list(range(len(commands))):
        problems.append("commands are not one per column in child order")
    keys = [key for _, key in commands]
    wanted = [item["k"] for item in group["items"]]
    if keys != wanted:
        problems.append(f"commands {keys} are not the data's {wanted}")
    return problems


def check_app(path, app):
    root = ET.parse(path).getroot()
    problems, counts = [], [0, 0, 0]
    grids = {}
    for obj in root.iter("object"):
        if obj.get("class") == "GtkGrid" and "hst-ribbon-layout" in v3.props(obj):
            grids.setdefault((obj.get("id"), _tab_label(obj)), []).append(obj)
    for tab in app["tabs"]:
        counts[0] += 1
        order, box = [], None
        for group in tab["groups"]:
            counts[1] += 1
            counts[2] += len(group["items"])
            found = grids.pop((group["id"], tab["id"]), [])
            if len(found) != 1:
                problems.append((tab["id"], group["id"], f"{len(found)} v3 grids (one expected)"))
                continue
            problems += [(tab["id"], group["id"], text) for text in check_group(found[0], group)]
            order.append(found[0])
            box = found[0].getparent().getparent()
        if box is not None:
            shown = [c.find("object") for c in box.findall("child") if c.find("object") is not None
                     and c.find("object").get("class") == "GtkGrid"]
            if [g.get("id") for g in shown if g in order] != [g.get("id") for g in order]:
                problems.append((tab["id"], "-", "groups are not in the data's order"))
            for grid in shown:
                if grid not in order and box.get("id") not in OUTSIDE:
                    problems.append((tab["id"], grid.get("id"), "a group of the tab without a v3 layout"))
    for (group_id, tab_id), _ in grids.items():
        problems.append((tab_id, group_id, "a v3 grid the data does not have"))
    return problems, counts


def _tab_label(grid):
    """The tab label id of the page holding grid (as generate-ribbon-v3-ui.py's tab_of)."""
    page = grid
    while page is not None and not (page.tag == "child" and page.getparent() is not None
                                    and page.getparent().get("class") == "sfxlo-NotebookbarTabControl"):
        page = page.getparent()
    if page is None:
        return None
    nxt = page.getnext()
    while nxt is not None and nxt.get("type") != "tab":
        nxt = nxt.getnext()
    return nxt.find("object").get("id") if nxt is not None else None


def check_tree(tree, data_path=DATA):
    """Problems (app, tab, group, message) of the tree's four ribbons, and the totals [tabs, groups, commands]."""
    with open(data_path, encoding="utf-8") as handle:
        data = json.load(handle)
    problems, totals = [], [0, 0, 0]
    for app in data["apps"]:
        path = os.path.join(tree, v3.UI_FILES[app["id"]])
        if not os.path.exists(path):
            problems.append((app["id"], "-", "-", f"{v3.UI_FILES[app['id']]} missing"))
            continue
        found, counts = check_app(path, app)
        problems += [(app["id"], *problem) for problem in found]
        totals = [a + b for a, b in zip(totals, counts)]
    return problems, totals
