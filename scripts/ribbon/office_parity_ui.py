# SPDX-License-Identifier: AGPL-3.0-only
"""Reading side of the offline ribbon parity check (check-office-parity.py): the vi catalogue and the visible items,
tab menus and group captions of a notebookbar.ui."""
import gettext
import json
import os
import re
import xml.etree.ElementTree as ET

ITEM_CLASSES = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")
LAUNCHER_PREFIX = "btnHstLaunch"


def command_name(action):
    """'.uno:Bold' -> 'Bold', without arguments ('.uno:StyleApply?Style:string=Good' -> 'StyleApply');
    other protocols ('org.hst.office.vi:ReportError') stay whole."""
    return action[len(".uno:"):].split("?", 1)[0] if action.startswith(".uno:") else action


def read_po(path):
    """{(msgctxt, msgid): msgstr} of a gettext .po file (enough of the format for LibreOffice's ui strings)."""
    entries, current, key = {}, {}, None

    def unquote(text):
        return json.loads(text) if text.startswith('"') else text

    def flush():
        if current.get("msgstr"):
            entries[(current.get("msgctxt", ""), current.get("msgid", ""))] = current["msgstr"]

    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                if not line and current:
                    flush()
                    current, key = {}, None
                continue
            match = re.match(r'^(msgctxt|msgid|msgstr)\s+(".*")$', line)
            if match:
                key = match.group(1)
                current[key] = unquote(match.group(2))
            elif line.startswith('"') and key:
                current[key] += unquote(line)
    flush()
    return entries


class Translator:
    """Translate ui strings with a compiled .mo (instdir) or a .po (source tree); identity without either."""

    def __init__(self, mo_path=None, po_path=None):
        self.mo = None
        self.po = {}
        if mo_path and os.path.exists(mo_path):
            with open(mo_path, "rb") as handle:
                self.mo = gettext.GNUTranslations(handle)
        elif po_path and os.path.exists(po_path):
            self.po = read_po(po_path)

    def __call__(self, context, text):
        if self.mo is not None:
            return self.mo.pgettext(context, text)
        return self.po.get((context, text), text)


def clean_label(text):
    return (text or "").replace("~", "").replace("_", "").strip()


def _props(obj):
    return {p.get("name").replace("_", "-"): p for p in obj.findall("property")}


def _text(prop, translate):
    if prop is None:
        return ""
    if prop.get("translatable") == "yes":
        return clean_label(translate(prop.get("context", ""), prop.text or ""))
    return clean_label(prop.text)


def parse_notebookbar(path, translate=lambda _c, t: t):
    """Pages of the Tabbed notebookbar, in order: [{label, id, contexts, groups, commands, menu_commands, launchers}].

    groups: [{id, caption, commands}] in document order (captioned grids only); commands: set of visible ribbon items
    on the page; menu_commands: commands of the page's tab menu; launchers: [{id, command, group}].
    """
    root = ET.parse(path).getroot()
    menus = {o.get("id"): o for o in root.findall("object") if o.get("class") == "GtkMenu"}
    captions = {}
    for label in root.iter("object"):
        if label.get("class") != "GtkLabel":
            continue
        for relation in label.iter("relation"):
            if relation.get("type") == "label-for":
                captions[relation.get("target")] = _text(_props(label).get("label"), translate)
    for grid in root.iter("object"):  # groups whose caption has no relation (Sheets): the label of the bottom row
        if grid.get("class") != "GtkGrid" or grid.get("id") in captions or not grid.get("id"):
            continue
        bottom = None
        for child in grid.findall("child"):
            obj, packing = child.find("object"), child.find("packing")
            if obj is None or packing is None:
                continue
            top = next((int(p.text) for p in packing.findall("property") if p.get("name") == "top-attach"), 0)
            labels = [obj] if obj.get("class") == "GtkLabel" else obj.findall("child/object[@class='GtkLabel']")
            for label in labels:
                prop = _props(label).get("label")
                if prop is not None and prop.get("translatable") == "yes" and top > 0 and (bottom is None or top > bottom[0]):
                    bottom = (top, _text(prop, translate))
        if bottom:
            captions[grid.get("id")] = bottom[1]
    control = next(o for o in root.iter("object") if o.get("class") == "sfxlo-NotebookbarTabControl")
    pages, pending = [], None
    for child in control.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if child.get("type") != "tab":
            pending = obj
            continue
        if pending is None:
            continue
        contexts = [c.get("name").replace("context-", "") for c in obj.findall("style/class") + pending.findall("style/class")
                    if c.get("name", "").startswith("context-")]
        page = {"label": _text(_props(obj).get("label"), translate), "id": obj.get("id"), "contexts": contexts,
                "groups": [], "commands": set(), "menu_commands": set(), "launchers": []}
        _walk_page(pending, page, menus, captions, None, False)
        pages.append(page)
        pending = None
    return pages


def _menu_commands(menu):
    found = set()
    for item in menu.iter("object"):
        action = _props(item).get("action-name")
        if action is not None and action.text:
            found.add(command_name(action.text))
    return found


def _walk_page(obj, page, menus, captions, group, hidden):
    props = _props(obj)
    hidden = hidden or (props.get("visible") is not None and props["visible"].text == "False")
    klass, ident = obj.get("class"), obj.get("id") or ""
    if ident in captions and not hidden:
        group = {"id": ident, "caption": captions[ident], "commands": []}
        page["groups"].append(group)
    if klass in ITEM_CLASSES and not hidden:
        action = props.get("action-name")
        if action is not None and action.text:
            command = command_name(action.text)
            if ident.startswith(LAUNCHER_PREFIX):
                page["launchers"].append({"id": ident, "command": command, "group": group["caption"] if group else None})
            else:
                page["commands"].add(command)
                if group is not None:
                    group["commands"].append(command)
    elif klass == "svtlo-ManagedMenuButton" and not hidden and ":" in ident:
        menu = menus.get(ident.split(":", 1)[1])
        if menu is not None:
            # "btn…" menu buttons are ribbon drop-downs; the others are the tab menu ("≡") of the page
            target = page["commands"] if ident.startswith("btn") else page["menu_commands"]
            target.update(_menu_commands(menu))
    for child in obj.findall("child"):
        for sub in child.findall("object"):
            _walk_page(sub, page, menus, captions, group, hidden)


def page_by_label(pages):
    return {p["label"]: p for p in pages}

