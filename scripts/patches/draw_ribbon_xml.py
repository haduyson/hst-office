# SPDX-License-Identifier: AGPL-3.0-only
"""GtkBuilder XML helpers of generate-draw-ribbon.py: find, move, rename and serialize objects of a notebookbar.ui."""
import copy
import xml.etree.ElementTree as ET

from draw_ribbon_data import DrawRibbonError


def parse(path):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser).getroot()


def find(root, oid):
    for o in root.iter("object"):
        if o.get("id") == oid:
            return o
    raise DrawRibbonError(f"no object {oid!r}")


def parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def child_of(parents, obj):
    """The <child> element that holds obj."""
    holder = parents[obj]
    if holder.tag != "child":
        raise DrawRibbonError(f"{obj.get('id')!r} is not held by a <child>")
    return holder


def ids(root):
    return {o.get("id") for o in root.iter("object") if o.get("id")}


def remove_child(root, obj):
    parents = parent_map(root)
    holder = child_of(parents, obj)
    parents[holder].remove(holder)


def remove_commands(root, commands):
    """Remove the buttons of these commands, and toolboxes that end up empty."""
    for _ in range(2):  # the second pass removes the toolboxes the first one emptied
        parents = parent_map(root)
        for obj in list(root.iter("object")):
            action = next((p.text for p in obj.findall("property") if p.get("name") == "action-name"), None)
            empty_box = obj.get("class") == "sfxlo-NotebookbarToolBox" and not obj.findall("child")
            if action in commands or empty_box:
                holder = parents.get(obj)
                if holder is not None and holder.tag == "child" and holder in parents:
                    parents[holder].remove(holder)


def swap_commands(root, swaps):
    for prop in root.iter("property"):
        if prop.get("name") == "action-name" and prop.text in swaps:
            prop.text = swaps[prop.text]


def rename_ids(element, rename, taken):
    """Give every object of the copy a new id; references inside the copy follow."""
    mapping = {}
    for obj in element.iter("object"):
        old = obj.get("id")
        if not old:
            continue
        name, colon, menu = old.partition(":")  # "button:Menu X" names the menu the button opens
        new = rename(name)
        while new + colon + menu in taken or new + colon + menu in mapping.values():
            new += "X"
        mapping[old] = new + colon + menu
        obj.set("id", mapping[old])
    for node in element.iter():
        for attribute in ("target",):
            if node.get(attribute) in mapping:
                node.set(attribute, mapping[node.get(attribute)])
        if node.tag == "property" and node.text in mapping:
            node.text = mapping[node.text]
    taken.update(mapping.values())
    return mapping


def set_label(label, context, text):
    for prop in label.findall("property"):
        if prop.get("name") == "label":
            prop.set("context", context)
            prop.set("translatable", "yes")
            prop.text = text
            return
    raise DrawRibbonError(f"label {label.get('id')!r} has no text")


def merged_box(page):
    boxes = [o for o in page.iter("object") if o.get("class") == "sfxlo-PriorityMergedHBox"]
    if not boxes:
        raise DrawRibbonError(f"tab page {page.get('id')!r} has no merged group box")
    return boxes[0]


def keep_groups(box, wanted):
    """Keep exactly these groups of a merged box, in this order."""
    holders = {c.find("object").get("id"): c for c in box.findall("child") if c.find("object") is not None}
    missing = [g for g in wanted if g not in holders]
    if missing:
        raise DrawRibbonError(f"{box.get('id')!r} lacks {missing}")
    for child in box.findall("child"):  # the box's own properties (visible, valign) stay
        box.remove(child)
    for gid in wanted:
        box.append(holders[gid])


def tab_pages(container):
    """[(page id, page <child>, tab <child>)] of the tab control."""
    kids = [c for c in container if c.tag == "child"]
    pages = []
    for i, child in enumerate(kids):
        if child.get("type") == "tab":
            continue
        tab = kids[i + 1] if i + 1 < len(kids) and kids[i + 1].get("type") == "tab" else None
        if tab is None:
            raise DrawRibbonError(f"tab page {child.find('object').get('id')!r} has no tab label")
        pages.append((child.find("object").get("id"), child, tab))
    return pages


def tab_label(tab):
    return next(o for o in tab.iter("object") if o.get("class") == "GtkLabel")


def new_tab(template, label_id, context, text, taken):
    """A tab label like Insert's: shown in every context, never the one selected for a context."""
    tab = copy.deepcopy(template)
    label = tab_label(tab)
    if label_id in taken:
        raise DrawRibbonError(f"tab label id {label_id!r} is taken")
    label.set("id", label_id)
    taken.add(label_id)
    set_label(label, context, text)
    return tab


def check_unique(root):
    seen = set()
    for obj in root.iter("object"):
        oid = obj.get("id")
        if oid and oid in seen:
            raise DrawRibbonError(f"duplicate id {oid!r}")
        seen.add(oid)
    for node in root.iter("relation"):
        if node.get("target") not in seen:
            raise DrawRibbonError(f"relation to a missing object {node.get('target')!r}")
    for obj in root.iter("object"):  # VclBuilder makes a widget at its first child: later properties are lost
        kinds = [c.tag for c in obj if c.tag in ("property", "child")]
        if "child" in kinds and "property" in kinds[kinds.index("child"):]:
            raise DrawRibbonError(f"{obj.get('id')!r} has a property after a child")


def serialize(root):
    ET.indent(root, space="  ")
    text = ET.tostring(root, encoding="unicode")
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HST Office: HST Draw ribbon, generated by scripts/patches/generate-draw-ribbon.py -->\n")
    return head + text + "\n"


