# SPDX-License-Identifier: AGPL-3.0-only
"""Groups of generate-draw-ribbon.py: new groups, the HST look of every group, the tabs' right-hand blocks left out,
and the groups laid out in file order."""
import xml.etree.ElementTree as ET

from draw_ribbon_data import (FIELDS_AFTER, FIELDS_GROUP, HST_CAPTION_STYLE, HST_GROUP_GRID, KEEP_TAB_BLOCKS,
                              OPEN_IN_HST_PDF, PAGES_GROUP, STRINGS, DrawRibbonError)
from draw_ribbon_xml import child_of, find, ids, parent_map, remove_child


def tool_button(bid, command, big):
    """A toolbox holding one button: big (icon over caption, two rows) or small (icon and caption)."""
    box = ET.Element("object", {"class": "sfxlo-NotebookbarToolBox", "id": "bx" + bid[3:]})
    for name, value in (("visible", "True"), ("can-focus", "False")):
        ET.SubElement(box, "property", {"name": name}).text = value
    if big:
        for name, value in (("valign", "center"), ("vexpand", "True"), ("toolbar-style", "both"),
                            ("show-arrow", "False"), ("icon_size", "3")):
            ET.SubElement(box, "property", {"name": name}).text = value
    else:
        for name, value in (("toolbar-style", "both-horiz"), ("show-arrow", "False")):
            ET.SubElement(box, "property", {"name": name}).text = value
    holder = ET.SubElement(box, "child")
    button = ET.SubElement(holder, "object", {"class": "GtkToolButton", "id": bid})
    props = [("visible", "True"), ("can-focus", "False")]
    if command == OPEN_IN_HST_PDF:  # an extension command: its caption, tip and icon are given here
        props += [("label", "Mở trong\nHST PDF" if big else "Mở trong HST PDF"),
                  ("tooltip-text", "Mở bản PDF của bản vẽ trong HST PDF để xem và ký số"),
                  ("action-name", command), ("icon-name", "cmd/32/openinhstpdf.png" if big else "cmd/sc_openinhstpdf.png")]
    else:
        props += [("action-name", command), ("use-underline", "True")]
    for name, value in props:
        ET.SubElement(button, "property", {"name": name}).text = value
    packing = ET.SubElement(holder, "packing")
    ET.SubElement(packing, "property", {"name": "expand"}).text = "False"
    ET.SubElement(packing, "property", {"name": "homogeneous"}).text = "True"
    return box


def group(gid, label_id, context, caption, big, smalls):
    """A captioned group: one big button, small buttons in a column beside it, its caption below."""
    grid = ET.Element("object", {"class": "GtkGrid", "id": gid})
    for name, value in (("visible", "True"), ("can-focus", "False")) + HST_GROUP_GRID:
        ET.SubElement(grid, "property", {"name": name}).text = value

    def place(obj, left, top, width=1, height=1):
        holder = ET.SubElement(grid, "child")
        holder.append(obj)
        packing = ET.SubElement(holder, "packing")
        for name, value in (("left-attach", left), ("top-attach", top), ("width", width), ("height", height)):
            if name in ("left-attach", "top-attach") or value != 1:
                ET.SubElement(packing, "property", {"name": name}).text = str(value)

    command, bid = big
    place(tool_button(bid, command, True), 0, 0, height=2)
    columns = 1
    for i, (command, bid) in enumerate(smalls):
        place(tool_button(bid, command, False), 1 + i // 2, i % 2)
        columns = max(columns, 2 + i // 2)
    separator = ET.Element("object", {"class": "GtkSeparator"})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("orientation", "vertical")):
        ET.SubElement(separator, "property", {"name": name}).text = value
    place(separator, columns, 0, height=3)
    label = ET.Element("object", {"class": "GtkLabel", "id": label_id})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("valign", "end"), ("vexpand", "True")):
        ET.SubElement(label, "property", {"name": name}).text = value
    ET.SubElement(label, "property", {"name": "label", "translatable": "yes", "context": context}).text = caption
    attributes = ET.SubElement(label, "attributes")
    ET.SubElement(attributes, "attribute", {"name": "style", "value": HST_CAPTION_STYLE})
    ET.SubElement(attributes, "attribute", {"name": "scale", "value": "0.9"})
    ET.SubElement(ET.SubElement(label, "accessibility"), "relation", {"type": "label-for", "target": gid})
    place(label, 0, 2, width=columns + 1)
    ET.SubElement(ET.SubElement(grid, "accessibility"), "relation", {"type": "labelled-by", "target": label_id})
    return grid


def caption_of(grid):
    """The caption of a ribbon group, or None: the GtkLabel lb* the group's grid holds, directly or in the
    caption box (bxHstCaption*) that also holds the group's dialog launcher."""
    for holder in grid.findall("child"):
        obj = holder.find("object")
        if obj is None:
            continue
        if obj.get("class") == "GtkLabel" and (obj.get("id") or "").startswith("lb"):
            return obj
        if obj.get("class") == "GtkBox" and (obj.get("id") or "").startswith("bxHstCaption"):
            return next((o for o in obj.iter("object")
                         if o.get("class") == "GtkLabel" and (o.get("id") or "").startswith("lb")), None)
    return None


def hst_group_look(root):
    """Give every captioned group the HST look (HST_GROUP_GRID, HST_CAPTION_STYLE); returns how many changed."""
    changed = 0
    for grid in root.iter("object"):
        caption = caption_of(grid) if grid.get("class") == "GtkGrid" else None
        if caption is None:
            continue
        style = next((a for a in caption.iter("attribute") if a.get("name") == "style"), None)
        props = {p.get("name"): p for p in grid.findall("property")}
        if style is None:
            raise DrawRibbonError(f"caption {caption.get('id')!r} has no style attribute")
        before = (style.get("value"), [(n, props[n].text if n in props else None) for n, _v in HST_GROUP_GRID])
        style.set("value", HST_CAPTION_STYLE)
        for name, value in HST_GROUP_GRID:
            if name not in props:  # after the last margin/spacing property, as the HST groups have it
                props[name] = ET.Element("property", {"name": name})
                last = max(i for i, c in enumerate(grid) if c.tag == "property")
                grid.insert(last + 1, props[name])
            props[name].text = value
        if before != (HST_CAPTION_STYLE, list(HST_GROUP_GRID)):
            changed += 1
    return changed


def drop_tab_blocks(root):
    """Remove the tabs' right-hand blocks (but KEEP_TAB_BLOCKS), then the menus only they opened."""
    blocks = [o for o in root.iter("object")
              if o.get("class") == "sfxlo-DropdownBox" and o.get("id") not in KEEP_TAB_BLOCKS]
    for block in blocks:
        remove_child(root, block)
    while True:  # a menu can be the submenu of another dropped menu only
        used = {p.text for p in root.iter("property")}
        used |= {o.get("id").partition(":")[2] for o in root.iter("object") if ":" in (o.get("id") or "")}
        unused = [o for o in root.findall("object") if o.get("class") == "GtkMenu" and o.get("id") not in used]
        if not unused:
            return len(blocks)
        for menu in unused:
            root.remove(menu)


def claim_ids(grid, taken):
    for oid in [o.get("id") for o in grid.iter("object") if o.get("id")]:
        if oid in taken:
            raise DrawRibbonError(f"new id {oid!r} is taken")
        taken.add(oid)


def place_groups(root, taken):
    """PAGES_GROUP replaces Trang's page group; FIELDS_GROUP goes after FIELDS_AFTER."""
    gid, label_id, big, smalls = PAGES_GROUP
    old = find(root, gid)
    holder = child_of(parent_map(root), old)
    taken -= ids(old)
    grid = group(gid, label_id, *STRINGS[3][:2], big, smalls)
    claim_ids(grid, taken)
    holder[list(holder).index(old)] = grid
    gid, label_id, big, smalls = FIELDS_GROUP
    grid = group(gid, label_id, *STRINGS[9][:2], big, smalls)
    claim_ids(grid, taken)
    parents = parent_map(root)
    after = child_of(parents, find(root, FIELDS_AFTER))
    box = parents[after]
    new_holder = ET.Element("child")
    new_holder.append(grid)
    box.insert(list(box).index(after) + 1, new_holder)


def order_by_position(root):
    """VclBuilder lays a box's children out by their packing position (unset is -1), not by their order in the
    file. Where the two disagree in a merged group box (the groups Draw's tabs gathered from other tabs, or
    added), number the groups in file order, which is the order this script chose."""
    for box in root.iter("object"):
        if box.get("class") != "sfxlo-PriorityMergedHBox":
            continue
        holders = [h for h in box.findall("child") if h.find("object") is not None]

        def position(holder):
            prop = holder.find("packing/property[@name='position']")
            return int(prop.text) if prop is not None else -1
        if [position(h) for h in holders] == sorted(position(h) for h in holders):
            continue
        for index, holder in enumerate(holders):
            packing = holder.find("packing")
            if packing is None:
                packing = ET.SubElement(holder, "packing")
                ET.SubElement(packing, "property", {"name": "expand"}).text = "False"
                ET.SubElement(packing, "property", {"name": "fill"}).text = "True"
            prop = packing.find("property[@name='position']")
            if prop is None:
                prop = ET.SubElement(packing, "property", {"name": "position"})
            prop.text = str(index)


