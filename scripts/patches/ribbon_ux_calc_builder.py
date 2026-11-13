# SPDX-License-Identifier: AGPL-3.0-only
"""The edited notebookbar.ui of generate-ribbon-ux-calc.py: finding and moving objects, new toolboxes,
buttons and drop-down menus, the translatable strings they bring (for sc/messages.po)."""
import xml.etree.ElementTree as ET

import ribbon_ux_lib as L
from ribbon_ux_calc_data import CAPTIONS, LABELS
from ribbon_ux_calc_layout import CTX, CalcUxError, Layout
from ribbon_ux_calc_menus import MENUS
from ribbon_ux_calc_tips import DESCRIPTIONS


class Builder(Layout):
    def __init__(self, text):
        self.text = text
        self.root = L.parse_text(text)
        self.strings = []
        self.notes = {}  # comments of a moved item's old <child> holder go with it
        self.top_index = list(self.root).index(L.find(self.root, "NotebookBar"))

    # --- strings -----------------------------------------------------------------------------------------
    def string(self, context, msgid, msgstr):
        entry = (context, msgid, msgstr)
        for c, m, s in self.strings:
            if (c, m) == (context, msgid) and s != msgstr:
                raise CalcUxError(f"{context}: two Vietnamese texts for {msgid!r}")
        if entry not in self.strings:
            self.strings.append(entry)

    def translatable(self, obj, name, context, en, vi):
        L.set_prop(obj, name, en, translatable=True, context=context)
        self.string(context, en, vi)

    # --- finding and moving -------------------------------------------------------------------------------
    def find(self, oid):
        return L.find(self.root, oid)

    def detach(self, obj):
        """obj out of its <child> holder (the holder is dropped)."""
        hold = L.remove(self.root, obj)
        hold.remove(obj)
        self.notes[id(obj)] = [node for node in hold if node.tag is ET.Comment]
        return obj

    def drop(self, *ids):
        for oid in ids:
            L.remove(self.root, self.find(oid))

    def take_button(self, bid):
        """The <child> holding a toolbox item, out of its toolbox."""
        return L.remove(self.root, self.find(bid))

    # --- new objects ---------------------------------------------------------------------------------------
    def toolbox(self, box_id, holders, big):
        box = ET.Element("object", {"class": "sfxlo-NotebookbarToolBox", "id": box_id})
        props = [("visible", "True"), ("can-focus", "True")]
        props += ([("valign", "center"), ("vexpand", "True"), ("toolbar-style", "both"), ("show-arrow", "False"),
                   ("icon_size", "3")] if big else [("toolbar-style", "both-horiz"), ("show-arrow", "False")])
        for name, value in props:
            L.set_prop(box, name, value)
        for hold in holders:
            box.append(hold)
        return box

    def button(self, bid, command, klass="GtkToolButton", label=None, icon=None, tooltip=None, translate=None):
        """A toolbox item holder; label: literal (extension command) or, with translate=(en, vi), translatable."""
        hold = L.tool_button(bid, command, klass=klass, icon=icon)
        obj = hold.find("object")
        if translate is not None:
            self.translatable(obj, "label", CTX + bid, *translate)
            L.set_prop(obj, "action-name", None)
            L.set_prop(obj, "action-name", command)
            if icon:
                L.set_prop(obj, "icon-name", None)
                L.set_prop(obj, "icon-name", icon)
        elif label is not None:
            # literal Vietnamese (product policy for the HST extension's commands), before the action
            props = list(obj)
            obj.insert(props.index(obj.find("property[@name='action-name']")), ET.Element("property", {"name": "label"}))
            obj.find("property[@name='label']").text = label
        if tooltip:
            at = list(obj).index(obj.find("property[@name='action-name']"))
            tip = ET.Element("property", {"name": "tooltip-text"})
            tip.text = tooltip
            obj.insert(at, tip)
        return hold

    def menu_button(self, name):
        """The drop-down button of MENUS[name] and its GtkMenu (and GtkImage) at the top of the file."""
        bid, en, vi, image, big, items = MENUS[name]
        menu = ET.Element("object", {"class": "GtkMenu", "id": f"Menu {name}"})
        L.set_prop(menu, "visible", "True")
        L.set_prop(menu, "can-focus", "False")
        for n, item in enumerate(items):
            hold = ET.SubElement(menu, "child")
            if item is None:
                sep = ET.SubElement(hold, "object", {"class": "GtkSeparatorMenuItem", "id": f"Menu{name}-separator{n}"})
                L.set_prop(sep, "visible", "True")
                L.set_prop(sep, "can-focus", "False")
                continue
            slug, command, item_en, item_vi = item
            mid = f"Menu{name}-{slug}"
            obj = ET.SubElement(hold, "object", {"class": "GtkMenuItem", "id": mid})
            L.set_prop(obj, "visible", "True")
            L.set_prop(obj, "can-focus", "False")
            L.set_prop(obj, "action-name", command)
            if item_en is None:  # a function name: the same in every language
                L.set_prop(obj, "label", slug.upper())
            else:
                self.translatable(obj, "label", CTX + mid, item_en, item_vi)
        new_top = [menu]
        btn = ET.Element("object", {"class": "svtlo-ManagedMenuButton", "id": f"{bid}:Menu {name}"})
        for prop, value in (("visible", "True"), ("can-focus", "True"), ("focus-on-click", "False"),
                            ("receives-default", "False"), ("valign", "center")):
            L.set_prop(btn, prop, value)
        if big:
            L.set_prop(btn, "vexpand", "True")
        L.set_prop(btn, "relief", "none")
        self.translatable(btn, "label", CTX + bid, en, vi)
        if image:
            img = ET.Element("object", {"class": "GtkImage", "id": "img" + bid[3:]})
            L.set_prop(img, "visible", "True")
            L.set_prop(img, "can-focus", "False")
            L.set_prop(img, "icon-name", image)
            new_top.insert(0, img)
            L.set_prop(btn, "image", img.get("id"))
            L.set_prop(btn, "image-position", "top" if big else "left")
        for obj in new_top:
            self.root.insert(self.top_index, obj)
            self.top_index += 1
        return btn

    # --- layout --------------------------------------------------------------------------------------------
    # --- labels --------------------------------------------------------------------------------------------
    def apply_strings(self):
        for bid, (en, vi) in LABELS.items():
            obj = self.find(bid)
            self.translatable(obj, "hst-ribbon-label", CTX + bid, en, vi)
            self.move_after_label(obj, "hst-ribbon-label")
        for bid, (en, vi) in DESCRIPTIONS.items():
            obj = self.find(bid)
            self.translatable(obj, "hst-ribbon-description", CTX + bid, en, vi)
            self.move_after_label(obj, "hst-ribbon-description")
        for label_id, (en, vi) in CAPTIONS.items():
            label = self.find(label_id)
            context = next(p for p in label.findall("property") if p.get("name") == "label").get("context")
            self.translatable(label, "label", context, en, vi)

    @staticmethod
    def move_after_label(obj, name):
        """Keep the ribbon-only properties right after the label (or after can-focus) in the property list."""
        prop = obj.find(f"property[@name='{name}']")
        obj.remove(prop)
        props = [p for p in obj if p.tag == "property"]
        anchor_names = ("hst-ribbon-label", "label", "can-focus", "visible")
        at = None
        for anchor in anchor_names:
            found = [p for p in props if p.get("name") == anchor]
            if found:
                at = list(obj).index(found[-1]) + 1
                break
        obj.insert(at if at is not None else 0, prop)

