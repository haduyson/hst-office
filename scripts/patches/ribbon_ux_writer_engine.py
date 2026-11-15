# SPDX-License-Identifier: AGPL-3.0-only
"""Layout engine of generate-ribbon-ux-writer.py: takes toolboxes and buttons out of the Writer notebookbar.ui,
builds groups from columns of them (2-row bodies, caption below, separator at the end), menu buttons with their
menus, and orders the groups of each tab. Item specs (tuples, first element is the kind):

  ("box", toolbox_id[, style])          an existing toolbox, moved (and restyled when style is given)
  ("btn", button_id, style)             an existing button, moved into a toolbox of its own ("bxUx<id>")
  ("new", button_id, command, style, options)   a new button; options: label (fixed text), tlabel (en, vi)
                                        translatable label, icon, klass
  ("menu", button_id, menu_id, style, (en, vi), icon)   a menu button opening the new GtkMenu menu_id
  ("label", label_id, (en, vi), [toolbox ids])          a text label for the toolboxes beside it
  ("widget", object_id)                 an existing non-toolbox child (a menu button), moved

Styles: "L" large (icon over label, both body rows), "S" small with label, "I" icon only.
"""
import copy
import xml.etree.ElementTree as ET

import ribbon_ux_lib as lib
import ribbon_ux_writer_widgets as widgets

UI = "sw/uiconfig/swriter/ui/notebookbar.ui"
CTX = {"group": "TabbedWriter|hstUxGroup", "label": "TabbedWriter|hstUxLabel", "tip": "TabbedWriter|hstUxTip",
       "menu": "TabbedWriter|hstUxMenu", "tab": "TabbedWriter|hstUxTab"}
STYLE_PROPS = {"L": (("valign", "center"), ("vexpand", "True"), ("toolbar-style", "both"), ("show-arrow", "False"),
                     ("icon_size", "3")),
               "S": (("toolbar-style", "both-horiz"), ("show-arrow", "False")),
               "I": (("toolbar-style", "icons"), ("show-arrow", "False"))}
LAYOUT_PROPS = ("valign", "vexpand", "halign", "hexpand", "toolbar-style", "show-arrow", "icon_size")


def box_id(button_id):
    """Id of the toolbox made for one moved or new button."""
    return "bxUx" + (button_id[3:] if button_id.startswith("btn") else button_id.replace("-", ""))


class Engine:
    def __init__(self, root):
        self.root = root
        self.strings = []  # (context, msgid, msgstr)
        self.template = lib.find(root, "gdHomeClipboard")
        self.caption_template = lib.find(root, "lbHomeClipboard")
        self.menus = {}  # menu id: entries (see ribbon_ux_writer_widgets.menu)

    def text(self, kind, pair):
        self.strings.append((CTX[kind], pair[0], pair[1]))
        return CTX[kind], pair[0]

    def set_text(self, obj, name, kind, pair):
        context, msgid = self.text(kind, pair)
        lib.set_prop(obj, name, msgid, translatable=True, context=context)

    # --- taking items out of the tree ---------------------------------------------------------------------
    def restyle(self, box, style):
        for name in LAYOUT_PROPS:
            lib.set_prop(box, name, None)
        for name, value in STYLE_PROPS[style]:
            lib.set_prop(box, name, value)

    def toolbox(self, box_id, style, holds):
        box = ET.Element("object", {"class": "sfxlo-NotebookbarToolBox", "id": box_id})
        lib.set_prop(box, "visible", "True")
        lib.set_prop(box, "can-focus", "False")
        self.restyle(box, style)
        box.extend(holds)
        hold = ET.Element("child")
        hold.append(box)
        return hold

    def detach(self, obj):
        hold = lib.remove(self.root, obj)
        packing = hold.find("packing")
        if packing is not None and obj.get("class") not in lib.BUTTON_CLASSES:
            hold.remove(packing)
        return hold

    def take(self, spec):
        kind = spec[0]
        if kind == "box":
            hold = self.detach(lib.find(self.root, spec[1]))
            if len(spec) > 2:
                self.restyle(hold.find("object"), spec[2])
            return hold
        if kind == "widget":
            return self.detach(lib.find(self.root, spec[1]))
        if kind == "btn":
            button = lib.find(self.root, spec[1])
            box_hold, box = lib.holder(self.root, button)
            hold = self.detach(button)
            if not [o for o in box.findall("child/object") if o.get("class") in lib.BUTTON_CLASSES]:
                self.detach(box)  # the toolbox it leaves empty goes too
            return self.toolbox(box_id(spec[1]), spec[2], [hold])
        if kind == "new":
            _kind, bid, command, style, options = spec
            hold = lib.tool_button(bid, command, klass=options.get("klass", "GtkToolButton"),
                                   label=options.get("label"))
            button = hold.find("object")
            if "tlabel" in options:
                self.set_text(button, "label", "label", options["tlabel"])
            if "icon" in options:
                lib.set_prop(button, "icon-name", options["icon"])
            return self.toolbox(box_id(bid), style, [hold])
        if kind == "menu":
            return widgets.menu_button(self, *spec[1:])
        if kind == "label":
            return widgets.text_label(self, *spec[1:])
        raise lib.RibbonUxError(f"unknown item {spec!r}")

    # --- groups ---------------------------------------------------------------------------------------------
    def caption(self, grid):
        for hold in grid.findall("child"):
            obj = hold.find("object")
            if obj is not None and (obj.get("id") or "").startswith(("lb", "bxHstCaption")):
                return hold
        return None

    def new_grid(self, gid, pair):
        grid = ET.Element("object", {"class": "GtkGrid", "id": gid})
        for prop in self.template.findall("property"):
            grid.append(copy.deepcopy(prop))
        label = copy.deepcopy(self.caption_template)
        label.set("id", "lb" + gid[2:])
        label.find("accessibility/relation").set("target", gid)
        self.set_text(label, "label", "group", pair)
        hold = ET.SubElement(grid, "child")
        hold.append(label)
        ET.SubElement(ET.SubElement(grid, "accessibility"), "relation", {"type": "labelled-by", "target": "lb" + gid[2:]})
        return grid

    @staticmethod
    def is_large(hold):
        obj = hold.find("object")
        return (lib.prop(obj, "toolbar-style") == "both" or lib.prop(obj, "image-position") == "top"
                or obj.get("class") == "GtkLabel")

    def lay_out(self, grid, columns=None, cells=None):
        """Rebuild grid's body from columns of item holders, or from cells (holder, left, top, width); its
        caption stays below, across the columns."""
        if cells is None:
            cells = []
            for left, column in enumerate(columns):
                for top, hold in enumerate(column):
                    tall = len(column) == 1 and self.is_large(hold)
                    cells.append((hold, left, top, 1, 2 if tall else 1))
        else:
            cells = [cell + (1,) for cell in cells]
        ncols = max(left + width for _hold, left, _top, width, _height in cells)
        caption = self.caption(grid)
        for hold in grid.findall("child"):
            grid.remove(hold)
        at = next((i for i, k in enumerate(grid) if k.tag != "property"), len(grid))
        grid.insert(at, caption)
        separator = ET.Element("object", {"class": "GtkSeparator"})
        for name, value in (("visible", "True"), ("can-focus", "False"), ("orientation", "vertical")):
            lib.set_prop(separator, name, value)
        sep_hold = ET.Element("child")
        sep_hold.append(separator)
        cells.append((sep_hold, ncols, 0, 1, 3))
        for hold, left, top, width, height in cells:
            lib.insert_child(grid, hold)
            for key, value in (("left-attach", left), ("top-attach", top), ("width", width), ("height", height)):
                if key.endswith("attach") or value > 1:
                    lib.packing(hold, key, value)
        pack = caption.find("packing")
        if pack is not None:
            caption.remove(pack)
        for key, value in (("left-attach", 0), ("top-attach", 2), ("width", ncols)):
            lib.packing(caption, key, value)
