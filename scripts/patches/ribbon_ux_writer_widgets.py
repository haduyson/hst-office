# SPDX-License-Identifier: AGPL-3.0-only
"""New widgets of the Writer ribbon UX rework (ribbon_ux_writer_engine.py): menu buttons with their image and
menu, and text labels beside toolboxes."""
import xml.etree.ElementTree as ET

import ribbon_ux_lib as lib


def top_level(engine, obj):
    """A top-level object (menu, image) before the notebookbar itself."""
    main = lib.find(engine.root, "NotebookBar")
    engine.root.insert(list(engine.root).index(main), obj)


def menu_button(engine, bid, menu_id, style, pair, icon):
    """A menu button (svtlo-ManagedMenuButton) with its image and its menu engine.menus[menu_id]."""
    top_level(engine, menu(engine, menu_id, engine.menus[menu_id]))
    image = ET.Element("object", {"class": "GtkImage", "id": "img" + bid[3:]})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("icon-name", icon)):
        lib.set_prop(image, name, value)
    top_level(engine, image)
    obj = ET.Element("object", {"class": "svtlo-ManagedMenuButton", "id": f"{bid}:{menu_id}"})
    engine.set_text(obj, "label", "label", pair)
    props = [("visible", "True"), ("can-focus", "True"), ("focus-on-click", "False"),
             ("receives-default", "False"), ("valign", "center")]
    props += [("vexpand", "True")] if style == "L" else [("halign", "start")]
    props += [("relief", "none"), ("use-underline", "True"), ("image", image.get("id")),
              ("image-position", "top" if style == "L" else "left")]
    for name, value in props:
        lib.set_prop(obj, name, value)
    hold = ET.Element("child")
    hold.append(obj)
    return hold


def menu(engine, menu_id, entries):
    """A GtkMenu: entries are commands, "-" separators, (command, (en, vi)) labelled items or
    (None, (en, vi), entries) submenus."""
    popup = ET.Element("object", {"class": "GtkMenu", "id": menu_id})
    lib.set_prop(popup, "visible", "True")
    lib.set_prop(popup, "can-focus", "False")
    stem = menu_id.replace(" ", "")
    for number, entry in enumerate(entries):
        klass = "GtkSeparatorMenuItem" if entry == "-" else "GtkMenuItem"
        item = ET.SubElement(ET.SubElement(popup, "child"), "object", {"class": klass, "id": f"{stem}-{number}"})
        lib.set_prop(item, "visible", "True")
        lib.set_prop(item, "can-focus", "False")
        if entry == "-":
            continue
        if isinstance(entry, str):
            entry = (entry, None)
        command, pair = entry[0], entry[1]
        if command:
            lib.set_prop(item, "action-name", command)
        if pair:
            engine.set_text(item, "label", "menu", pair)
        if len(entry) > 2:  # a submenu
            sub = ET.SubElement(item, "child", {"type": "submenu"})
            sub.append(menu(engine, f"{menu_id} {number}", entry[2]))
    return popup


def text_label(engine, label_id, pair, targets):
    obj = ET.Element("object", {"class": "GtkLabel", "id": label_id})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("valign", "center")):
        lib.set_prop(obj, name, value)
    engine.set_text(obj, "label", "label", pair)
    access = ET.SubElement(obj, "accessibility")
    for target in targets:
        ET.SubElement(access, "relation", {"type": "label-for", "target": target})
    hold = ET.Element("child")
    hold.append(obj)
    return hold
