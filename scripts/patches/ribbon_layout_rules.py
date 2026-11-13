# SPDX-License-Identifier: AGPL-3.0-only
"""Layout rules of the HST ribbon groups (owner decision of 13/11/2026), shared by the layout check
(check-ribbon-layout.py) and the generator that applies them (generate-ribbon-ux-uniform.py).

A group is a GtkGrid inside a PriorityMergedHBox: its items sit in rows 0 and 1 (an item of height 2 fills the
group's height) and its caption in the row under them. The rules, on the authored (largest) state:
- few: a group of at most FEW_COMMANDS commands and no control (combo box, find box, gallery, label) shows
  every command as a large button filling the group's height, so the groups look alike;
- lone: in the other groups no small one-command button sits alone in its column (an empty cell over or under
  it), and no small one-command button fills the group's height (a small icon floating in the middle);
- grid: a small item sits in row 0 or 1 with height 1, so the stacks share the two rows of the group.
"""
import xml.etree.ElementTree as ET

FEW_COMMANDS = 3
# the Tabbed ribbons of the four apps (the other notebookbar variants are not offered)
RIBBONS = {
    "Writer": "sw/uiconfig/swriter/ui/notebookbar.ui",
    "Sheets": "sc/uiconfig/scalc/ui/notebookbar.ui",
    "Slides": "sd/uiconfig/simpress/ui/notebookbar.ui",
    "Draw": "sd/uiconfig/sdraw/ui/notebookbar.ui",
}
BUTTONS = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")
MENU_BUTTONS = ("svtlo-ManagedMenuButton", "GtkMenuButton")
TOOLBOX = "sfxlo-NotebookbarToolBox"
# toolbox commands drawn as a control rather than a button (their controllers put a box in the toolbox)
CONTROL_COMMANDS = {".uno:CharFontName", ".uno:FontHeight", ".uno:NumberFormatType", ".uno:StylesPreview",
                    ".uno:FillStyle", ".uno:HstSetTransitionAdvance", ".uno:HstSetTransitionDuration",
                    "vnd.sun.star.findbar:FocusToFindbar", ".uno:Zoom", ".uno:ZoomSlider", ".uno:LineStyle",
                    ".uno:ThemeSelectorPanel", ".uno:FontworkGalleryFloater:gallery"}


def prop(obj, name):
    found = obj.find(f"property[@name='{name}']")
    return None if found is None else found.text


def packing(hold, name, default=None):
    found = hold.find(f"packing/property[@name='{name}']")
    return default if found is None else found.text


def is_caption(hold):
    """The group's caption (a label, or a box of the label and the dialog launcher) under the two rows; a group
    with one row of items has its caption label (valign end) in row 1."""
    obj = hold.find("object")
    return int(packing(hold, "top-attach", "0")) >= 2 or (obj.get("class") == "GtkLabel" and prop(obj, "valign") == "end")


class Item:
    """One cell of a group: the object, its packing and what it shows."""

    def __init__(self, hold):
        self.hold = hold
        self.obj = hold.find("object")
        self.id = self.obj.get("id")
        self.klass = self.obj.get("class")
        self.left = int(packing(hold, "left-attach", "0"))
        self.top = int(packing(hold, "top-attach", "0"))
        self.height = int(packing(hold, "height", "1"))
        self.width = int(packing(hold, "width", "1"))
        buttons = [o for o in self.obj.iter("object") if o.get("class") in BUTTONS]
        self.commands = len(buttons)
        self.big = None
        if self.klass == TOOLBOX and not any(prop(b, "action-name") in CONTROL_COMMANDS for b in buttons):
            self.kind = "toolbox"
            self.big = prop(self.obj, "icon_size") == "3" or prop(self.obj, "toolbar-style") == "both"
        elif self.klass in MENU_BUTTONS:
            self.kind = "menu"
            self.commands = 1
            image = prop(self.obj, "image")
            self.big = prop(self.obj, "image-position") == "top" if image else prop(self.obj, "vexpand") == "True"
        else:  # a box of controls, a combo box, a find box, an inline label: no size rule
            self.kind = "control"
            self.commands = max(1, self.commands)

    def rows(self):
        return range(self.top, self.top + self.height)

    def columns(self):
        return range(self.left, self.left + self.width)

    def __repr__(self):
        return f"{self.id}@{self.left},{self.top}"


class Group:
    def __init__(self, grid, tab):
        self.grid = grid
        self.id = grid.get("id")
        self.tab = tab
        self.items, self.caption = [], None
        for hold in grid.findall("child"):
            obj = hold.find("object")
            if obj is None or obj.get("class") == "GtkSeparator":
                continue
            if is_caption(hold):
                self.caption = hold
            else:
                self.items.append(Item(hold))
        self.commands = sum(item.commands for item in self.items)

    @property
    def few(self):
        return 0 < self.commands <= FEW_COMMANDS and all(item.kind != "control" for item in self.items)

    def occupant(self, left, row):
        return next((item for item in self.items if left in item.columns() and row in item.rows()), None)


def groups(root):
    """Every group of a ribbon .ui, with the id of its tab's group box (pmhb<Tab>)."""
    out = []
    for box in root.iter("object"):
        if box.get("class") == "sfxlo-PriorityMergedHBox":
            out += [Group(grid, box.get("id")) for grid in box.findall("child/object") if grid.get("class") == "GtkGrid"]
    return out


def lone(group, item):
    """A small one-command button alone in its column, or filling the group's height on its own."""
    if item.kind == "control" or item.commands != 1 or item.big:
        return False
    if item.height >= 2:
        return True
    other = 1 - item.top if item.top in (0, 1) else None
    return item.width == 1 and other is not None and group.occupant(item.left, other) is None


def violations(group):
    """(rule, items, text) of every layout rule the group breaks."""
    if group.few:
        bad = [item for item in group.items if not item.big or item.height != 2 or item.top != 0]
        return [("few", bad, f"{group.commands} commands: each a large button filling the group")] if bad else []
    out = [("lone", [item], "a small button alone in its column") for item in group.items if lone(group, item)]
    out += [("grid", [item], "a small item off the two rows") for item in group.items
            if item.height == 1 and item.top not in (0, 1)]
    return out


def check_root(root):
    return [(group, rule, items, text) for group in groups(root) for rule, items, text in violations(group)]


def check_file(path):
    return check_root(ET.parse(path).getroot())
