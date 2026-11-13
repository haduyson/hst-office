# SPDX-License-Identifier: AGPL-3.0-only
"""The model of check-access-keys.py: menus and Tabbed notebookbars of the source tree, with their labels."""
from pathlib import Path
import xml.etree.ElementTree as ET

from po_io import parse_po
from access_keys_labels import LANG, MENU, OOR, UI_PO, escape, resolve, strip_mnemonics, unescape

APPS = (
    ("Writer", "sw/uiconfig/swriter", "WriterCommands", "text.TextDocument"),
    ("Calc", "sc/uiconfig/scalc", "CalcCommands", "sheet.SpreadsheetDocument"),
    ("Impress", "sd/uiconfig/simpress", "DrawImpressCommands", "presentation.PresentationDocument"),
    ("Draw", "sd/uiconfig/sdraw", "DrawImpressCommands", "drawing.DrawingDocument"),
    ("Start Center", "framework/uiconfig/startmodule", "GenericCommands", "frame.StartModule"),
)


class ModelBuilder:
    def __init__(self, tree):
        self.tree, self.po, self.commands, self.containers = Path(tree), {}, {}, []

    def label(self, english, file=None, context=None, vi="", markers="~", name=False):
        msgid = escape(english)
        if file and file not in self.po:
            path = self.tree / "translations/source/vi" / file
            self.po[file] = {(unescape(e["msgctxt"]), e["msgid"]): e
                             for e in parse_po(path)}
        entry = self.po.get(file, {}).get((context, msgid), {})
        return dict(file=file, msgctxt=context, msgid=msgid, english=english,
                    vi=entry.get("msgstr", escape(vi)), fuzzy=entry.get("fuzzy", False),
                    markers=markers, name=name)

    def command(self, module, command, mode="menu"):
        for config in dict.fromkeys((module, "GenericCommands")):
            if config not in self.commands:
                table = self.commands[config] = {}
                path = self.tree / "officecfg/registry/data/org/openoffice/Office/UI" / (config + ".xcu")
                if path.exists():
                    root = ET.parse(path).getroot()
                    # Commands win over Popups (emplace); module wins as a whole.
                    for section in ("Commands", "Popups"):
                        for node in root.findall(f"./node/node[@{OOR}name='{section}']/node"):
                            props = {}
                            for prop in node.findall("prop"):
                                value = prop.find(f"value[@{LANG}='en-US']")
                                if value is not None:
                                    kind = prop.get(OOR + "name")
                                    ctx = (f"{config}.xcu\n..{config}.UserInterface.{section}."
                                           f"{node.get(OOR + 'name')}\n{kind}\nvalue.text")
                                    props[kind] = self.label(value.text or "", UI_PO, ctx)
                            table.setdefault(node.get(OOR + "name"), props)
            if command in self.commands[config]:
                props = self.commands[config][command]
                order = {"menu": ("ContextLabel", "Label"),
                         "popup": ("PopupLabel", "ContextLabel", "Label"),
                         "name": ("Label",)}[mode]
                return [dict(props[p], name=mode == "name", markers="" if mode == "name" else "~")
                        for p in order if p in props]
        return []

    def container(self, path, kind, app):
        container = dict(path=path, type=kind, app=app, strict=kind != "controls", items=[])
        self.containers.append(container)
        return container

    @staticmethod
    def item(identifier, labels, command="", **extra):
        return dict(id=identifier, command=command, labels=labels, **extra)

    def menus(self, element, path, app, module, owner=""):
        container = self.container(path, "menus", app)
        container["owner"] = owner
        for node in element:
            if node.tag not in (MENU + "menu", MENU + "menuitem"):
                continue
            command = node.get(MENU + "id", "")
            explicit = node.get(MENU + "label", "")
            labels = ([self.label(explicit)] if explicit else []) + self.command(module, command)
            item = self.item(command, labels, command, auto=True)
            container["items"].append(item)
            popup = node.find(MENU + "menupopup")
            if popup is not None:
                title = strip_mnemonics(resolve(item, {}, True)[0]).rstrip(".…") or command
                self.menus(popup, path + " > " + title, app, module, command)
        return container

    def addons(self, root, app, module, bar, help_menu):
        def add(parent, container):
            for node in parent.findall("node"):
                def value(prop, lang=None):
                    suffix = f"[@{LANG}='{lang}']" if lang else ""
                    return node.findtext(f"prop[@{OOR}name='{prop}']/value{suffix}", "")
                context, command = value("Context"), value("URL")
                if (context and module not in context) or command == "private:separator":
                    continue
                title = value("Title", "en-US") or value("Title")
                labels = [self.label(title, vi=value("Title", "vi") or title)]
                item = self.item(node.get(OOR + "name"), labels, command, auto=True)
                submenu = node.find(f"node[@{OOR}name='Submenu']")
                if submenu is not None:
                    sub = self.container(container["path"] + " > " + strip_mnemonics(title), "menus", app)
                    add(submenu, sub)
                    if not sub["items"]:
                        self.containers.remove(sub)
                        continue
                container["items"].append(item)
        for section, container in (("OfficeMenuBar", bar), ("OfficeHelp", help_menu)):
            parent = root.find(f"./node[@{OOR}name='AddonUI']/node[@{OOR}name='{section}']")
            if parent is not None and container is not None:
                add(parent, container)

    def notebook(self, path, app, module, po):
        root = ET.parse(path).getroot()

        def ui_item(obj, tab=False, menu=False):
            props = {p.get("name"): p for p in obj.findall("property")}
            command = props["action-name"].text if "action-name" in props else ""
            prop = props.get("label")
            labels = []
            tool = obj.get("class", "") in ("GtkToolButton", "GtkMenuToolButton",
                                             "GtkToggleToolButton", "GtkRadioToolButton")
            if prop is not None:
                translatable = prop.get("translatable") == "yes"
                labels = [self.label(prop.text or "", po if translatable else None,
                                     prop.get("context"), markers="~" if tab or tool else "~_")]
            if tool:
                # ToolBox uses stripped Name first; HST's builder falls back to UI.
                labels = self.command(module, command, "name") + labels
            elif menu:
                labels += self.command(module, command, "popup")
            return self.item(obj.get("id", ""), labels, command or "", auto=menu)

        def controls(obj, container):
            if obj.get("class") == "GtkMenu":
                return  # Each GtkMenu gets its own container below.
            item = ui_item(obj)
            if item["labels"]:
                container["items"].append(item)
            for child in obj.findall("child/object"):
                controls(child, container)

        for notebook in root.iter("object"):
            tabs = notebook.findall("child[@type='tab']")
            if not tabs:
                continue
            bar = self.container(app + " > Tabs", "tab-bars", app)
            page = None
            for child in notebook.findall("child"):
                obj = child.find("object")
                if child.get("type") != "tab":
                    page = obj
                elif obj is not None and page is not None:
                    item = ui_item(obj, tab=True)
                    contexts = [s.get("name") for s in obj.findall("style/class")
                                if s.get("name", "").startswith("context-")]
                    item["contextual"] = bool(contexts) and "context-any" not in contexts
                    bar["items"].append(item)
                    title = strip_mnemonics(resolve(item, {}, True)[0]) or item["id"]
                    controls(page, self.container(app + " > Ribbon > " + title, "controls", app))
        for menu in root.findall(".//object[@class='GtkMenu']"):
            container = self.container(app + " > Ribbon > " + menu.get("id"), "controls", app)
            for obj in menu.findall("child/object"):
                if obj.get("class") in ("GtkMenuItem", "GtkCheckMenuItem", "GtkRadioMenuItem"):
                    container["items"].append(ui_item(obj, menu=True))


def build_model(tree):
    """Menus and notebookbars from the source tree (what the snapshot stores; no add-on menus)."""
    builder = ModelBuilder(tree)
    for app, prefix, module, service in APPS:
        path = Path(tree) / prefix / "menubar/menubar.xml"
        if not path.exists():
            continue  # Also permits small, partial source fixtures.
        builder.menus(ET.parse(path).getroot(), app, app, module)
        path = Path(tree) / prefix / "ui/notebookbar.ui"
        if app in ("Writer", "Calc", "Impress", "Draw") and path.exists():
            builder.notebook(path, app, module, prefix.split("/")[0] + "/messages.po")
    if not builder.containers:
        raise ValueError("no menubars found in tree")
    return finish(builder.containers)


def finish(containers):
    for container in containers:
        container["items"].sort(key=lambda item: (item["id"], item["command"]))
    return dict(version=2, containers=sorted(containers, key=lambda c: (c["type"], c["path"])))
