# SPDX-License-Identifier: AGPL-3.0-only
"""The editing helpers of the Slides/Draw ribbon rework (generate-ribbon-ux-impress-draw.py): strings that need
Vietnamese, ribbon-only labels, buttons, menus and menu buttons."""
import xml.etree.ElementTree as ET

import ribbon_ux_lib as L
from ribbon_ux_impress_draw_data import LABEL_CONTEXT, LABELS, STRINGS
from ribbon_ux_impress_draw_groups import BOX, GroupLayout  # noqa: F401 (BOX re-exported for the generator)


class Builder(GroupLayout):
    """The edits of one notebookbar.ui; collects the strings that need Vietnamese."""

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.strings = {}
        self.counter = 0
        self.emptied = set()  # toolboxes buttons were taken from

    # --- strings -----------------------------------------------------------------------------------------
    def string(self, key):
        context, msgid, msgstr = STRINGS[key]
        self.strings[(context, msgid)] = msgstr
        return context, msgid

    def ribbon_label(self, bid, key):
        msgid, msgstr = LABELS[key]
        self.strings[(LABEL_CONTEXT, msgid)] = msgstr
        L.set_prop(L.find(self.root, bid), "hst-ribbon-label", msgid, translatable=True, context=LABEL_CONTEXT)

    def label_command(self, command, key):
        """hst-ribbon-label on every toolbox button of a command."""
        for obj in self.root.iter("object"):
            if obj.get("class") in L.BUTTON_CLASSES and L.prop(obj, "action-name") == command:
                self.ribbon_label(obj.get("id"), key)

    def caption(self, lid, key):
        context, msgid = self.string(key)
        L.set_prop(L.find(self.root, lid), "label", msgid, translatable=True, context=context)

    # --- elements ----------------------------------------------------------------------------------------
    def button(self, bid, command, key=None, klass="GtkToolButton"):
        hold = L.tool_button(bid, command, klass)
        obj = hold.find("object")
        if key:
            msgid, msgstr = LABELS[key]
            self.strings[(LABEL_CONTEXT, msgid)] = msgstr
            L.set_prop(obj, "hst-ribbon-label", msgid, translatable=True, context=LABEL_CONTEXT)
        return hold

    def take(self, *bids):
        """The <child> holders of existing buttons, taken out of their toolboxes."""
        holds = []
        for bid in bids:
            _hold, box = L.holder(self.root, L.find(self.root, bid))
            self.emptied.add(box.get("id"))
            holds.append(L.remove(self.root, L.find(self.root, bid)))
        return holds

    def drop(self, *oids):
        for oid in oids:
            L.remove(self.root, L.find(self.root, oid))

    def menu(self, menu_id, prefix, commands, klass="GtkMenuItem"):
        """A top-level GtkMenu (before the NotebookBar grid) of command items."""
        menu = ET.Element("object", {"class": "GtkMenu", "id": menu_id})
        L.set_prop(menu, "visible", "True")
        L.set_prop(menu, "can-focus", "False")
        for command in commands:
            item = ET.Element("object", {"class": klass, "id": prefix + command.split(":")[-1].split(".")[-1]})
            L.set_prop(item, "visible", "True")
            L.set_prop(item, "can-focus", "False")
            L.set_prop(item, "action-name", command)
            hold = ET.SubElement(menu, "child")
            hold.append(item)
        self._top_level(menu)

    def _top_level(self, obj):
        """Insert a top-level object before the NotebookBar grid (and the glade comment above it)."""
        top = list(self.root)
        at = top.index(L.find(self.root, "NotebookBar"))
        while at > 0 and top[at - 1].tag is ET.Comment:
            at -= 1
        self.root.insert(at, obj)

    def image(self, image_id, icon):
        img = ET.Element("object", {"class": "GtkImage", "id": image_id})
        L.set_prop(img, "visible", "True")
        L.set_prop(img, "can-focus", "False")
        L.set_prop(img, "icon-name", icon)
        self._top_level(img)

    def menu_button(self, bid, menu_id, key, image_id=None):
        """An svtlo-ManagedMenuButton opening menu_id; large (icon above the label) when it has an image."""
        context, msgid = self.string(key)
        obj = ET.Element("object", {"class": "svtlo-ManagedMenuButton", "id": f"{bid}:{menu_id}"})
        L.set_prop(obj, "label", msgid, translatable=True, context=context)
        for name, value in (("visible", "True"), ("can-focus", "True"), ("focus-on-click", "False"),
                            ("receives-default", "False"), ("valign", "center"), ("vexpand", "True"),
                            ("relief", "none")):
            L.set_prop(obj, name, value)
        if image_id:
            L.set_prop(obj, "image", image_id)
            L.set_prop(obj, "image-position", "top")
        return obj
