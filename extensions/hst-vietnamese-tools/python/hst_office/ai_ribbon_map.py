# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Command map of the HST ribbon for the "Hỏi cách dùng" answer of the Trợ lý AI.

The map is read from the ribbon definition the office really shows: the app's notebookbar.ui (the user's profile copy
when the ribbon was customised, else the installed one), its translated texts (the module's gettext catalogue in
program/resource/<lang>) and the labels of the commands (theUICommandDescription, in the UI language). Nothing is
written by hand, so the answer follows the ribbon of the running build.

One line per group: "Tab › Group: command; command; menu ▾ (item, item)". Contextual tabs are marked, so the answer can
say that the tab appears only when e.g. a table is selected. parse_ribbon() and format_map() are pure; command_map()
(ai_ribbon_map_uno) is the UNO glue: main thread, it reads configuration and the UI command description.
"""
import xml.etree.ElementTree as ET

from .ai_ribbon_ui import MAX_MENU_ITEMS, Command, Reader, _with_menu, clean, visible  # noqa: F401 - re-exported

# document kind (ai_document.kind) -> (module folder in soffice.cfg, gettext domain, module identifier, app name)
APPS = {
    "writer": ("swriter", "sw", "com.sun.star.text.TextDocument", "HST Writer"),
    "calc": ("scalc", "sc", "com.sun.star.sheet.SpreadsheetDocument", "HST Sheets"),
    "impress": ("simpress", "sd", "com.sun.star.presentation.PresentationDocument", "HST Slides"),
    "draw": ("sdraw", "sd", "com.sun.star.drawing.DrawingDocument", "HST Draw"),
}
TAB_CONTROL = "sfxlo-NotebookbarTabControl"
SKIP_TABS = {"FileLabel"}  # the File button opens the backstage view, not a tab of groups


def _caption_child(grid):
    """The caption of a group's grid: a direct GtkLabel, or a direct box whose own children hold the label (and the
    group's dialog launcher)."""
    for child in grid.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if obj.get("class") == "GtkLabel":
            return child, obj
        if obj.get("class") == "GtkBox":
            labels = [o for o in obj.findall("child/object") if o.get("class") == "GtkLabel"]
            if labels:
                return child, labels[0]
    return None, None


def _groups(page, reader):
    """[(caption, [commands])] of one tab page; a group is a grid with a caption, searched outermost first."""
    found = []

    def walk(obj):
        if obj.get("class") == "GtkGrid":
            cap_child, cap_label = _caption_child(obj)
            if cap_label is not None:
                caption = reader.text(cap_label)
                commands = []
                for child in obj.findall("child"):
                    sub = child.find("object")
                    if child is not cap_child and sub is not None:
                        reader.commands(sub, commands)
                if commands and visible(obj):  # a group without caption text still shows its commands
                    found.append((caption, commands))
                return
        for child in obj.findall("child"):
            sub = child.find("object")
            if sub is not None and visible(sub):
                walk(sub)
    walk(page)
    return found


def parse_ribbon(ui_text, translate, command_label):
    """Tabs of a notebookbar.ui: [(tab name, contextual, [(group caption, [Command])])].

    translate(context, msgid) returns the shown text of a translatable label; command_label(".uno:X") the label of a
    command without its own label in the .ui. Tabs without groups (the File backstage) are left out."""
    root = ET.fromstring(ui_text)
    reader = Reader(root, translate, command_label)
    tabs = []
    for control in (o for o in root.iter("object") if o.get("class") == TAB_CONTROL):
        children = control.findall("child")
        for index, child in enumerate(children):
            if child.get("type") == "tab" or child.find("object") is None:
                continue
            label_obj = None
            for nxt in children[index + 1:]:
                if nxt.get("type") == "tab":
                    label_obj = nxt.find("object")
                    break
                if nxt.find("object") is not None:
                    break
            if label_obj is None or label_obj.get("id") in SKIP_TABS:
                continue
            name = reader.text(label_obj)
            groups = _groups(child.find("object"), reader)
            if name and groups:
                tabs.append((name, _contextual(label_obj), groups))
    return tabs


def _contextual(label_obj):
    """A tab shown only for a selection: its label's style classes name a context other than the default/any."""
    style = label_obj.find("style")
    if style is None:
        return False
    names = {c.get("name") for c in style.findall("class")}
    return "context-default" not in names


def format_map(app_name, tabs):
    """The compact text sent in the system prompt."""
    lines = ["Bản đồ ribbon của %s (Thẻ › Nhóm: các lệnh; ▾ là nút có danh sách thả xuống; "
             "[ngữ cảnh] là thẻ chỉ hiện khi chọn đối tượng tương ứng):" % app_name]
    for name, contextual, groups in tabs:
        tag = " [ngữ cảnh]" if contextual else ""
        for caption, commands in groups:
            path = "%s%s › %s" % (name, tag, caption) if caption else name + tag
            lines.append("%s: %s" % (path, "; ".join(c.text for c in commands)))
    return "\n".join(lines)
