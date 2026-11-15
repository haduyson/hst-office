# SPDX-License-Identifier: AGPL-3.0-only
"""Group layout of generate-ribbon-ux-calc.py: two-row group bodies, toolbox styles, new groups."""
import copy
import xml.etree.ElementTree as ET

import ribbon_ux_lib as L

CTX = "TabbedCalc|"


class CalcUxError(L.RibbonUxError):
    pass


class Layout:
    """Methods of the Builder (ribbon_ux_calc_builder.py) that lay groups out."""

    def caption_holder(self, grid):
        for hold in grid.findall("child"):
            if L.packing(hold, "top-attach") == "2":
                return hold
        raise CalcUxError(f"{grid.get('id')}: no caption")

    def place(self, gid, columns):
        """Lay group gid out again: each column is [big item] (two rows) or [top, bottom] (bottom may be None);
        an item is an object (or the id of one) anywhere in the file. The caption spans the columns and one
        separator closes the group."""
        grid = self.find(gid)
        caption = self.caption_holder(grid)
        columns = [[self.find(i) if isinstance(i, str) else i for i in column] for column in columns]
        for column in columns:
            for item in column:
                if item is not None and item in L.parent_map(self.root):
                    self.detach(item)
        for hold in [h for h in grid.findall("child") if h is not caption]:
            grid.remove(hold)
        grid.remove(caption)
        L.insert_child(grid, caption)
        for left, column in enumerate(columns):
            cells = [(column[0], 0, 2)] if len(column) == 1 else [(column[0], 0, 1), (column[1], 1, 1)]
            for item, top, height in cells:
                if item is None:
                    continue
                hold = ET.Element("child")
                hold.extend(self.notes.pop(id(item), []))
                hold.append(item)
                pack = ET.SubElement(hold, "packing")
                L.set_prop(pack, "left-attach", str(left))
                L.set_prop(pack, "top-attach", str(top))
                if height != 1:
                    L.set_prop(pack, "height", str(height))
                L.insert_child(grid, hold)
        pack = caption.find("packing")
        L.set_prop(pack, "width", None if len(columns) == 1 else str(len(columns)))
        sep = ET.Element("object", {"class": "GtkSeparator"})
        for prop, value in (("visible", "True"), ("can-focus", "False"), ("orientation", "vertical")):
            L.set_prop(sep, prop, value)
        hold = ET.Element("child")
        hold.append(sep)
        pack = ET.SubElement(hold, "packing")
        L.set_prop(pack, "left-attach", str(len(columns)))
        L.set_prop(pack, "top-attach", "0")
        L.set_prop(pack, "height", "3")
        L.insert_child(grid, hold)

    def columns_of(self, gid):
        """The current columns of a group (for appending): [[top, bottom] or [big]] by left-attach."""
        grid = self.find(gid)
        cells = {}
        for hold in grid.findall("child"):
            obj = hold.find("object")
            top = L.packing(hold, "top-attach")
            if obj.get("class") == "GtkSeparator" or top == "2":
                continue
            left = int(L.packing(hold, "left-attach"))
            cells.setdefault(left, {})[int(top)] = (obj, L.packing(hold, "height") == "2")
        out = []
        for left in sorted(cells):
            column = cells[left]
            if 0 in column and column[0][1]:
                out.append([column[0][0]])
            else:
                out.append([column.get(0, (None,))[0], column.get(1, (None,))[0]])
        return out

    def style(self, box_id, big):
        box = self.find(box_id)
        for prop in ("valign", "vexpand", "toolbar-style", "show-arrow", "icon_size"):
            L.set_prop(box, prop, None)
        values = ([("valign", "center"), ("vexpand", "True"), ("toolbar-style", "both"), ("show-arrow", "False"),
                   ("icon_size", "3")] if big else [("toolbar-style", "both-horiz"), ("show-arrow", "False")])
        for prop, value in values:
            L.set_prop(box, prop, value)
        return box

    def new_group(self, template_gid, gid, label_id, en, vi, columns, after=None):
        """A copy of a one-column group's frame with a new caption and items, after group `after` (or last)."""
        template = self.find(template_gid)
        grid = copy.deepcopy(template)
        grid.set("id", gid)
        caption = self.caption_holder(grid)
        for hold in [h for h in grid.findall("child") if h is not caption]:
            grid.remove(hold)
        label = next(o for o in caption.iter("object") if o.get("class") == "GtkLabel")
        label.set("id", label_id)
        for rel in label.iter("relation"):
            rel.set("target", gid)
        for rel in grid.findall("accessibility/relation"):
            rel.set("target", label_id)
        self.translatable(label, "label", CTX + "label" + label_id[2:], en, vi)
        box_hold = L.holder(self.root, template)[1]
        hold = ET.Element("child")
        hold.append(grid)
        if after is None:
            L.insert_child(box_hold, hold)
        else:
            kids = [k for k in box_hold if k.tag == "child"]
            index = kids.index(L.holder(self.root, self.find(after))[0]) + 1
            L.insert_child(box_hold, hold, index)
        self.place(gid, columns)
        return grid
