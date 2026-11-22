# SPDX-License-Identifier: AGPL-3.0-only
"""The v3 ribbon layout applied to the four notebookbar.ui files (helpers of generate-ribbon-v3-ui.py).

Every group of data/ribbon/ribbon-v3.json names its commands in their order and their kind (L large, M small with its
label, S icon only, W box, G gallery). The .ui of each group is rewritten so that every command is one child of the
group's GtkGrid, in that order (a toolbox of several buttons is split into one toolbox per button), and the grid gets
the property "hst-ribbon-layout" that the ribbon's layout code (vcl HstRibbonV3Layout) reads:

    kinds=LSSS;rows=0.1.|.3/4.5;nofill

kinds: one letter per command child in child order; rows: the group's fixed 3-row layout, rows separated by "/",
items by ".", a 6 px gap as "|", items by their index in kinds; nofill: the group keeps its sizes when its tab is
sparse. The caption (a label, or a box with the label and the dialog launcher) and the separator stay as they are.
"""
import copy
import re

from lxml import etree as ET

UI_FILES = {"writer": "sw/uiconfig/swriter/ui/notebookbar.ui", "sheets": "sc/uiconfig/scalc/ui/notebookbar.ui",
            "slides": "sd/uiconfig/simpress/ui/notebookbar.ui", "draw": "sd/uiconfig/sdraw/ui/notebookbar.ui"}
TOOL_ITEMS = {"GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton", "GtkToolItem"}
MENU_BUTTONS = {"svtlo-ManagedMenuButton", "GtkMenuButton"}
TOOLBOX = "sfxlo-NotebookbarToolBox"


def props(obj):
    return {p.get("name"): (p.text or "") for p in obj.findall("property")}


def strip_menu(widget_id):
    return (widget_id or "").split(":")[0]


def is_caption(obj):
    """A group's caption: its label, or the box of its label and launcher."""
    if obj.get("class") == "GtkLabel":
        return True
    return obj.get("class") == "GtkBox" and any(o.get("class") == "GtkLabel" for o in obj.iter("object"))


class Unit:
    """One command of a group as the .ui has it: a tool item (in its toolbox) or a menu button."""

    def __init__(self, key, element, toolbox=None, child=None):
        self.key, self.element, self.toolbox, self.child = key, element, toolbox, child


def units_of(child_obj, child_el):
    """The commands inside one child of a group's grid (a toolbox, a menu button, a box of them)."""
    cls = child_obj.get("class")
    if cls in MENU_BUTTONS:
        return [Unit(strip_menu(child_obj.get("id")), child_obj, child=child_el)]
    if cls == TOOLBOX:
        out = []
        for item_child in child_obj.findall("child"):
            item = item_child.find("object")
            if item is None or item.get("class") not in TOOL_ITEMS:
                continue
            key = props(item).get("action-name", "").replace(".uno:", "").split("?")[0] or item.get("id")
            out.append(Unit(key, item_child, toolbox=child_obj, child=child_el))
        return out
    if cls == "GtkBox":
        out = []
        for sub in child_obj.findall("child"):
            obj = sub.find("object")
            if obj is not None:
                out.extend(units_of(obj, sub))
        return out
    return []


def group_parts(grid):
    """(caption children, separator children, units) of a group's grid."""
    captions, separators, units = [], [], []
    for child in grid.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if obj.get("class") == "GtkSeparator":
            separators.append(child)
        elif is_caption(obj):
            captions.append(child)
        else:
            units.extend(units_of(obj, child))
    return captions, separators, units


def new_unit(item, units, tab="Home"):
    """A command the 1.0.2 ribbon does not have ("new": an owner addition): a copy of the tool item of its neighbour
    ("clone") with its own command and ids (bxV3<id> toolbox, btn<tab>Hst<k> button, the tab as in the group id). An extension's protocol command
    (org.hst.office.vi:...) keeps its name and gets the item's label, tooltip and "icon", as the other HST extension
    buttons of the ribbon; a .uno: command takes them from the command, its image too unless the item names an "icon"."""
    model = next((u for u in units if u.key == item["clone"] and u.toolbox is not None), None)
    if model is None:
        raise KeyError(f"no tool item {item['clone']} to copy for {item['k']}")
    element = copy.deepcopy(model.element)
    obj = element.find("object")
    name = item["k"].split(":")[-1]
    obj.set("id", "btn" + tab + "Hst" + name.removeprefix("Hst"))
    protocol = ":" in item["k"]  # an extension's protocol command (org.hst.office.vi:...), else .uno:
    for prop in obj.findall("property"):
        if prop.get("name") == "action-name":
            prop.text = item["k"] if protocol else ".uno:" + item["k"]
    for prop in [p for p in obj.findall("property") if p.get("name") in ("icon-name", "label", "tooltip-text",
                                                                   "hst-ribbon-label", "hst-ribbon-description")]:
        obj.remove(prop)  # the neighbour's own image or texts, if it has any
    anchor = next(p for p in obj.findall("property") if p.get("name") == "action-name")
    if not protocol:
        # as the .uno: buttons of the .ui files: the command's name, its label and image come from the command
        prop = ET.Element("property", name="label")
        prop.text = item["k"]
        anchor.addprevious(prop)
        if item.get("icon"):  # a command without a 24 px image of its own (e.g. ReadOnlyDoc) names one
            prop = ET.Element("property", name="icon-name")
            prop.text = item["icon"]
            anchor.addnext(prop)
    else:
        # as the other HST extension buttons of the ribbon: its own label, tooltip and image (no command label)
        for key, value in (("icon-name", item.get("icon")), ("label", item["t"]),
                           ("tooltip-text", item.get("tip", item["t"]))):
            if value:
                prop = ET.Element("property", name=key)
                prop.text = value
                anchor.addprevious(prop) if key != "icon-name" else anchor.addnext(prop)
    return Unit(item["k"], element, toolbox=model.toolbox, child=ET.Element("child"))


def match_units(group, units, pool=()):
    """The unit of every item of the v3 group, in the group's order; raises when one is missing or left over. A new
    item copies its "clone" from the group's units or from pool (the other commands of its tab: a new group has none)."""
    left = list(units)
    out = []
    for item in group["items"]:
        if item.get("new"):
            out.append(new_unit(item, list(units) + list(pool), re.match(r"gd([A-Z][a-z]+)", group["id"]).group(1)))
            continue
        found = next((u for u in left if u.key == item["k"]), None)
        if found is None:
            raise KeyError(f"{group['id']}: no .ui command for {item['k']}")
        left.remove(found)
        out.append(found)
    if left:
        raise KeyError(f"{group['id']}: .ui commands not in the v3 data: {[u.key for u in left]}")
    return out


def packing(child_el, left, top, width=1, height=1):
    old = child_el.find("packing")
    if old is not None:
        child_el.remove(old)
    pack = ET.SubElement(child_el, "packing")
    for name, value in (("left-attach", left), ("top-attach", top), ("width", width), ("height", height)):
        ET.SubElement(pack, "property", name=name).text = str(value)


def single_toolbox(unit, used_ids):
    """A grid child holding only unit: its own toolbox when it shared one, else its current child."""
    if unit.toolbox is None:
        return unit.child
    items = [c for c in unit.toolbox.findall("child") if c.find("object") is not None
             and c.find("object").get("class") in TOOL_ITEMS]
    if len(items) == 1 and unit.child.find("object") is unit.toolbox:
        return unit.child
    box = ET.Element("object", attrib={"class": TOOLBOX})
    base = unit.element.find("object").get("id") or unit.key.replace(":", "_").replace(".", "_")
    new_id, n = "bxV3" + base, 2
    while new_id in used_ids:
        new_id, n = f"bxV3{base}{n}", n + 1
    used_ids.add(new_id)
    box.set("id", new_id)
    for prop in unit.toolbox.findall("property"):
        box.append(copy.deepcopy(prop))
    for style in unit.toolbox.findall("style"):
        box.append(copy.deepcopy(style))
    box.append(copy.deepcopy(unit.element))
    child = ET.Element("child")
    child.append(box)
    return child


def fill_cell(obj):
    """A command takes its whole cell (the layout gives every command of a column one width): no 1.0.2 alignment
    or margin is left on it."""
    for prop in obj.findall("property"):
        if prop.get("name") in ("halign", "valign") or prop.get("name", "").startswith("margin"):
            obj.remove(prop)
    anchor = next((p for p in obj.findall("property") if p.get("name") == "can-focus"), None)
    for name in ("valign", "halign"):
        prop = ET.Element("property", name=name)
        prop.text = "fill"
        anchor.addnext(prop) if anchor is not None else obj.insert(0, prop)


def layout_spec(group, kinds):
    index = {item["k"]: i for i, item in enumerate(group["items"])}
    parts = ["kinds=" + "".join(kinds)]
    if group.get("rows"):
        rows = [".".join("|" if k == "|" else str(index[k]) for k in row) for row in group["rows"]]
        parts.append("rows=" + "/".join(rows))
    if group.get("nofill"):
        parts.append("nofill")
    return ";".join(parts)


def rewrite_group(grid, group, used_ids, pool=()):
    """Rebuild grid's children for the v3 group; returns the number of commands placed."""
    captions, separators, units = group_parts(grid)
    ordered = match_units(group, units, pool)
    for child in list(grid.findall("child")):
        grid.remove(child)
    n = len(ordered)
    for i, unit in enumerate(ordered):
        child = single_toolbox(unit, used_ids)
        fill_cell(child.find("object"))
        packing(child, i, 0, 1, 3)
        grid.append(child)
    for child in captions:
        packing(child, 0, 3, max(1, n))
        grid.append(child)
    for child in separators[:1]:  # a second separator (an authoring slip) goes
        packing(child, n, 0, 1, 4)
        grid.append(child)
    # the v3 group has its padding and separator inside (HstRibbonV3Layout): groups abut, at the top of the page,
    # as in the mockup, so the 1.0.2 margins go with the old spec
    for prop in grid.findall("property"):
        if prop.get("name") in ("hst-ribbon-layout", "margin-start", "margin-end", "margin-top", "margin-bottom",
                                "margin-left", "margin-right"):
            grid.remove(prop)
    kinds = [item["kind"] for item in group["items"]]
    spec = ET.Element("property", name="hst-ribbon-layout")
    spec.text = layout_spec(group, kinds)
    last = grid.findall("property")
    (last[-1].addnext(spec) if last else grid.insert(0, spec))
    return n
