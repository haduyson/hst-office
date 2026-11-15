# SPDX-License-Identifier: AGPL-3.0-only
"""Layout rules of the HST ribbon groups (owner decision of 13/11/2026, approved 1.0.2 mockup of 15/11/2026), shared
by the layout check (check-ribbon-layout.py) and the generator that applies them (generate-ribbon-ux-uniform.py).

A group is a GtkGrid inside a PriorityMergedHBox: its items sit in two rows (rows 0 and 1, the "rows2" of the mockup
for groups with a combo box) or three rows (rows 0 to 2, the mockup's 3-row columns of small labelled buttons:
Clipboard, Editing, Text), an item as high as the rows fills the group's height, and its caption sits in the row
under them. The rules, on the authored (largest) state:
- few: a group of at most FEW_COMMANDS commands and no control (combo box, find box, gallery, label) shows
  every command as a large button filling the group's height, so the groups look alike;
- lone: in the other groups no small one-command button sits alone in its column (an empty cell over or under
  it), and no small one-command button fills the group's height (a small icon floating in the middle);
- grid: a small item sits in one of the group's rows with height 1, so the stacks share the rows of the group;
- stagger: the small buttons of a column fill it from the top row down (no empty cell above one), and in a run
  of columns of single small buttons no column holds more than the one before it (the mockup's grid(): ceil(n/3)
  columns of ceil(n/columns) buttons, top to bottom then left to right), so the icons line up;
- tall: in a group of three rows a large button fills the three rows, as Paste does beside Cut, Copy and Format
  Painter.
"""
import xml.etree.ElementTree as ET

FEW_COMMANDS = 3
# buttons kept large at every size (keepsLarge() of vcl/source/control/HstRibbonLadder.cxx); their group is no "few"
KEEP_LARGE = {"btnHomeHstEditingSortFilter", "btnHomeHstEditingFindSelect", "bxInsertTextBox", "bxUxInsertDrawText",
              "bxHstEditHeaderAndFooter6", "bxDataTextToColumns", "bxHstAutomaticCalculation12", "bxHstUXHomeSlide1",
              "btnHstHomeShapes", "bxHstUXInsertSlide9", "btnHstInsertShapes", "bxInsertInsertGraphic",
              "bxHstUXInsertText12", "bxHstUXInsertText16", "bxHstUXInsertText13"}
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
                    ".uno:ThemeSelectorPanel", ".uno:FontworkGalleryFloater:gallery", ".uno:HstPictureStyles",
                    ".uno:HstTableStyles"}


def prop(obj, name):
    found = obj.find(f"property[@name='{name}']")
    return None if found is None else found.text


def packing(hold, name, default=None):
    found = hold.find(f"packing/property[@name='{name}']")
    return default if found is None else found.text


def is_caption(hold, bottom=2):
    """The group's caption (a label, or a box of the label and the dialog launcher) in the row under the items
    (bottom: the group's lowest row, 2 or 3); a group with one row of items has its caption label (valign end) in
    row 1."""
    obj = hold.find("object")
    top = int(packing(hold, "top-attach", "0"))
    if obj.get("class") == "GtkLabel":
        return top >= 2 or prop(obj, "valign") == "end"
    return top >= 2 and top == bottom and obj.get("class") == "GtkBox" and obj.find(".//object[@class='GtkLabel']") is not None


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
        holds = [h for h in grid.findall("child")
                 if h.find("object") is not None and h.find("object").get("class") != "GtkSeparator"]
        bottom = max((int(packing(h, "top-attach", "0")) for h in holds), default=0)
        for hold in holds:
            if is_caption(hold, bottom):
                self.caption = hold
            else:
                self.items.append(Item(hold))
        self.commands = sum(item.commands for item in self.items)
        # three rows when an item sits in or reaches into row 2 (the caption is under the rows)
        self.rows = 3 if any(item.top + item.height > 2 for item in self.items) else 2

    @property
    def few(self):  # not a 3-row group: its large button beside a column of small labelled ones is the mockup's
        return self.rows == 2 and 0 < self.commands <= FEW_COMMANDS and all(
            item.kind != "control" and item.id.split(":")[0] not in KEEP_LARGE for item in self.items)

    def occupant(self, left, row):
        return next((item for item in self.items if left in item.columns() and row in item.rows()), None)

    def small(self, item):
        return item.kind != "control" and item.commands == 1 and not item.big and item.width == 1


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
    if item.width != 1 or item.top >= group.rows:
        return False
    return all(group.occupant(item.left, row) in (None, item) for row in range(group.rows))


def column_of_smalls(group, left):
    """The number of small one-command buttons stacked in column left, or None when anything else stands in it."""
    holders = {group.occupant(left, row) for row in range(group.rows)} - {None}
    return len(holders) if holders and all(group.small(item) and item.height == 1 for item in holders) else None


def staggered(group):
    """Small buttons of a column under an empty cell, and runs of columns of small buttons whose later column
    holds more buttons than the one before it."""
    out = [item for item in group.items if group.small(item) and item.height == 1 and 0 < item.top < group.rows
           and group.occupant(item.left, item.top - 1) is None]
    last = max((left for item in group.items for left in item.columns()), default=-1)
    before = None
    for left in range(last + 1):
        count = column_of_smalls(group, left)
        if count is not None and before is not None and count > before:
            out += [group.occupant(left, row) for row in range(group.rows) if group.occupant(left, row)]
        before = count
    return out


def violations(group):
    """(rule, items, text) of every layout rule the group breaks."""
    if group.few:
        bad = [item for item in group.items if not item.big or item.height != group.rows or item.top != 0]
        return [("few", bad, f"{group.commands} commands: each a large button filling the group")] if bad else []
    out = [("lone", [item], "a small button alone in its column") for item in group.items if lone(group, item)]
    out += [("grid", [item], "a small item off the rows of its group") for item in group.items
            if item.height == 1 and item.top >= group.rows]
    bad = staggered(group)
    if bad:
        out.append(("stagger", bad, "small buttons not filling their columns from the top, evenly"))
    if group.rows == 3:
        out += [("tall", [item], "a large button not filling the three rows") for item in group.items
                if item.big and (item.top != 0 or item.height != 3)]
    return out


def check_root(root):
    return [(group, rule, items, text) for group in groups(root) for rule, items, text in violations(group)]


def check_file(path):
    return check_root(ET.parse(path).getroot())
