# SPDX-License-Identifier: AGPL-3.0-only
"""Group layout of the Slides/Draw ribbon rework (generate-ribbon-ux-impress-draw.py): toolboxes, 2-row
group grids, captions and the order of a tab's groups."""
import xml.etree.ElementTree as ET

import ribbon_ux_lib as L
from ribbon_ux_impress_draw_data import DESCRIPTION_CONTEXT, DESCRIPTIONS

BOX = "sfxlo-NotebookbarToolBox"


class GroupLayout:
    """Mixed into Builder: needs self.root, self.counter, self.strings and self.string()."""

    def _toolbox(self, gid, style, holders, large):
        self.counter += 1
        box = ET.Element("object", {"class": BOX, "id": f"bxHstUX{gid[2:]}{self.counter}"})
        L.set_prop(box, "visible", "True")
        L.set_prop(box, "can-focus", "False")
        if large:
            L.set_prop(box, "valign", "center")
            L.set_prop(box, "vexpand", "True")
        L.set_prop(box, "toolbar-style", style)
        L.set_prop(box, "show-arrow", "False")
        if large:
            L.set_prop(box, "icon_size", "3")
        for hold in holders:
            L.packing(hold, "homogeneous", "False" if large else "True")
            box.append(hold)
        return box

    @staticmethod
    def _place(grid, obj, left, top, height=None, width=None):
        hold = ET.Element("child")
        hold.append(obj)
        pack = ET.SubElement(hold, "packing")
        L.set_prop(pack, "left-attach", str(left))
        L.set_prop(pack, "top-attach", str(top))
        if width:
            L.set_prop(pack, "width", str(width))
        if height:
            L.set_prop(pack, "height", str(height))
        L.insert_child(grid, hold)

    def layout(self, grid, columns):
        """Fill grid with columns: ("L", item) spans both rows with a large button; ("S", row0, row1, style)
        holds two rows (row1 may be None). An item is a list of button holders (a toolbox) or a widget."""
        gid = grid.get("id")
        for left, column in enumerate(columns):
            if column[0] == "L":
                item = column[1]
                obj = item if isinstance(item, ET.Element) and item.tag == "object" \
                    else self._toolbox(gid, "both", item, True)
                self._place(grid, obj, left, 0, height=2)
            else:
                _kind, row0, row1, style = column
                for top, item in ((0, row0), (1, row1)):
                    if item is None:
                        continue
                    obj = item if isinstance(item, ET.Element) and item.tag == "object" \
                        else self._toolbox(gid, style, item, False)
                    self._place(grid, obj, left, top)
        sep = ET.Element("object", {"class": "GtkSeparator"})
        for name, value in (("visible", "True"), ("can-focus", "False"), ("orientation", "vertical")):
            L.set_prop(sep, name, value)
        self._place(grid, sep, len(columns), 0, height=3)
        return len(columns)

    def refill(self, gid, columns, caption_key=None):
        """Empty an existing group but its caption, then lay out columns."""
        grid = L.find(self.root, gid)
        caption_hold = None
        for hold in [c for c in grid if c.tag == "child"]:
            obj = hold.find("object")
            oid = obj.get("id") or ""
            if obj.get("class") == "GtkLabel" or oid.startswith("bxHstCaption"):
                caption_hold = hold
            grid.remove(hold)
        for node in [c for c in grid if c.tag is ET.Comment]:
            grid.remove(node)
        if caption_hold is None:
            raise L.RibbonUxError(f"{gid}: no caption")
        width = self.layout(grid, columns)
        for name, value in (("left-attach", 0), ("top-attach", 2), ("width", width)):
            L.packing(caption_hold, name, value)
        L.insert_child(grid, caption_hold)
        if caption_key:
            label = caption_hold.find("object")
            if label.get("class") != "GtkLabel":
                label = next(o for o in label.iter("object") if o.get("class") == "GtkLabel")
            self.caption(label.get("id"), caption_key)
        self._clear_parent_comment(grid)
        return grid

    def _clear_parent_comment(self, grid):
        hold, _parent = L.holder(self.root, grid)
        for node in [c for c in hold if c.tag is ET.Comment and "n-columns" in (c.text or "")]:
            hold.remove(node)

    def new_group(self, gid, lid, caption_key, columns):
        """A new group (GtkGrid with its caption) as a <child> for a merged box."""
        context, msgid = self.string(caption_key)
        grid = ET.Element("object", {"class": "GtkGrid", "id": gid})
        for name, value in (("visible", "True"), ("can-focus", "False"), ("margin-start", "4"), ("margin-end", "2"),
                            ("margin-top", "6"), ("margin-bottom", "6"), ("row-spacing", "3"),
                            ("column-spacing", "4")):
            L.set_prop(grid, name, value)
        width = self.layout(grid, columns)
        label = ET.Element("object", {"class": "GtkLabel", "id": lid})
        for name, value in (("visible", "True"), ("can-focus", "False"), ("valign", "end"), ("vexpand", "True")):
            L.set_prop(label, name, value)
        L.set_prop(label, "label", msgid, translatable=True, context=context)
        attrs = ET.SubElement(label, "attributes")
        ET.SubElement(attrs, "attribute", {"name": "style", "value": "normal"})
        ET.SubElement(attrs, "attribute", {"name": "scale", "value": "0.9"})
        acc = ET.SubElement(label, "accessibility")
        ET.SubElement(acc, "relation", {"type": "label-for", "target": gid})
        self._place(grid, label, 0, 2, width=width)
        acc = ET.SubElement(grid, "accessibility")
        ET.SubElement(acc, "relation", {"type": "labelled-by", "target": lid})
        hold = ET.Element("child")
        hold.append(grid)
        pack = ET.SubElement(hold, "packing")
        for name, value in (("expand", "False"), ("fill", "True"), ("position", "0")):
            L.set_prop(pack, name, value)
        return hold

    def insert_group(self, box_id, hold, after=None, first=False):
        box = L.find(self.root, box_id)
        kids = [c for c in box if c.tag == "child"]
        if first:
            index = 0
        elif after:
            index = kids.index(L.holder(self.root, L.find(self.root, after))[0]) + 1
        else:
            index = None
        L.insert_child(box, hold, index)

    def renumber(self):
        for box in self.root.iter("object"):
            if box.get("class") == "sfxlo-PriorityMergedHBox":
                for index, hold in enumerate(c for c in box if c.tag == "child"):
                    if L.packing(hold, "position") is not None:
                        L.packing(hold, "position", index)

    def expand_gallery(self, gid, toolbox):
        """The group and its toolbox take the room the tab leaves (the gallery item already expands)."""
        grid = L.find(self.root, gid)
        L.set_prop(grid, "hexpand", "True")
        L.set_prop(L.find(self.root, toolbox), "hexpand", "True")
        L.packing(L.holder(self.root, grid)[0], "expand", "True")

    def describe(self, skip=()):
        for obj in self.root.iter("object"):
            command = L.prop(obj, "action-name")
            if obj.get("class") in L.BUTTON_CLASSES and command in DESCRIPTIONS and command not in skip:
                msgid, msgstr = DESCRIPTIONS[command]
                self.strings[(DESCRIPTION_CONTEXT, msgid)] = msgstr
                L.set_prop(obj, "hst-ribbon-description", msgid, translatable=True, context=DESCRIPTION_CONTEXT)
