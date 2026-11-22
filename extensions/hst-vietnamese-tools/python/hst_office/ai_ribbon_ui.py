# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Commands and labels of a notebookbar.ui as the ribbon shows them (helpers of ai_ribbon_map). Pure."""

TOOL_ITEMS = {"GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton", "GtkToolItem"}
MENU_BUTTONS = {"svtlo-ManagedMenuButton", "GtkMenuButton"}
MENU_ITEMS = {"GtkMenuItem", "GtkCheckMenuItem", "GtkRadioMenuItem"}
MAX_MENU_ITEMS = 12  # a long dropdown is cut ("…") to keep the prompt compact


def ui_props(obj):
    return {p.get("name"): p for p in obj.findall("property")}


def visible(obj):
    prop = ui_props(obj).get("visible")
    return prop is None or (prop.text or "").strip().lower() != "false"


def clean(label):
    """A label as shown: no mnemonic marker (~ or _), no trailing dots or colon, single spaces."""
    text = (label or "").replace("~", "").replace("_", "")
    text = " ".join(text.split()).rstrip(".…:").strip()
    return text


class Reader:
    """Labels of one .ui: translate(context, msgid) for translatable texts, command_label(command) for the rest."""

    def __init__(self, root, translate, command_label):
        self.translate, self.command_label = translate, command_label
        self.menus = {o.get("id"): o for o in root.iter("object") if o.get("class") == "GtkMenu"}

    def text(self, obj, name="label"):
        prop = ui_props(obj).get(name)
        if prop is None or not (prop.text or "").strip():
            return ""
        if prop.get("translatable") == "yes":
            return clean(self.translate(prop.get("context") or "", prop.text))
        return clean(prop.text)

    def item_label(self, obj):
        """Label of a tool item, menu item or menu button as the ribbon shows it: the HST ribbon's own label, the
        item's label (a placeholder equal to the command name does not count), the command's label, its tooltip or
        accessible name."""
        props = ui_props(obj)
        label = self.text(obj, "hst-ribbon-label")
        command = (props["action-name"].text or "").strip() if "action-name" in props else ""
        if not label:
            label = self.text(obj)
            if command and label == command.split(":")[-1].split("?")[0]:
                label = ""
        if not label and command:
            label = clean(self.command_label(command.split("?")[0]))
        if not label:
            label = self.text(obj, "tooltip-text")
        if not label:
            for atk in obj.iter("object"):
                if atk.get("class") == "AtkObject":
                    label = self.text(atk, "AtkObject::accessible-name")
                    break
        return label

    def menu_entries(self, menu_id):
        menu = self.menus.get(menu_id)
        if menu is None:
            return []
        out = []
        for child in menu.findall("child"):
            item = child.find("object")
            if item is not None and item.get("class") in MENU_ITEMS and visible(item):
                label = self.item_label(item)
                if label and label not in out:
                    out.append(label)
        return out

    def commands(self, obj, out):
        """Collect the commands below obj in document order as Command(key, text): key is the command without
        ".uno:" and arguments (a menu button: its widget id), text the label with its dropdown entries."""
        cls = obj.get("class")
        if not visible(obj):
            return
        if cls in TOOL_ITEMS | MENU_BUTTONS:
            widget_id = obj.get("id") or ""
            action = ui_props(obj).get("action-name")
            key = (action.text or "").strip() if action is not None else ""
            key = key.replace(".uno:", "").split("?")[0] or widget_id.split(":")[0]
            if cls in MENU_BUTTONS:
                entries = self.menu_entries(widget_id.split(":", 1)[1]) if ":" in widget_id else []
            else:
                menu = ui_props(obj).get("menu")
                entries = self.menu_entries(menu.text) if menu is not None else []
            label = self.item_label(obj) or key  # never drop a command: its name beats a hole in the map
            if key:
                out.append(Command(key, _with_menu(label, entries, dropdown=cls in MENU_BUTTONS)))
            return
        for child in obj.findall("child"):
            sub = child.find("object")
            if sub is not None:
                self.commands(sub, out)


class Command:
    """One command of a group: key (".uno:" stripped, or a menu button's id) and text (what the map shows)."""
    __slots__ = ("key", "text")

    def __init__(self, key, text):
        self.key, self.text = key, text

    def __repr__(self):
        return "Command(%r, %r)" % (self.key, self.text)


def _with_menu(label, entries, dropdown=False):
    if not entries:
        return label + (" ▾" if dropdown else "")
    shown = entries[:MAX_MENU_ITEMS] + (["…"] if len(entries) > MAX_MENU_ITEMS else [])
    return "%s ▾ (%s)" % (label, ", ".join(shown))
