#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""List, per ribbon tab, the commands reachable only through the tab's trailing block (its tab menu "Tab ▾" and the
small icons beside it), and the block icons that duplicate a command shown elsewhere on the ribbon.

Usage: scripts/ribbon/tab-menu-commands.py (--src TREE | --instdir DIR) [--apps writer,calc,impress] [--json OUT]

"Elsewhere on the ribbon" is any visible ribbon item outside the trailing blocks, on any tab (contextual tabs
included) and in any ribbon drop-down; a group's launcher arrow is not counted. A block whose tab menu and icons hold no such only-here command can go
without losing a command; the classic menu bar and the feature search (Alt+Q) keep every command regardless.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from office_parity_ui import LAUNCHER_PREFIX, command_name  # noqa: E402

UI = {"writer": "sw/uiconfig/swriter/ui/notebookbar.ui", "calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
      "impress": "sd/uiconfig/simpress/ui/notebookbar.ui"}
MODULE = {"writer": "swriter", "calc": "scalc", "impress": "simpress"}
ITEMS = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")


def _prop(obj, name):
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return prop.text
    return None


def _visible(obj):
    return _prop(obj, "visible") != "False"


def _menu_commands(menu):
    return {command_name(a) for a in (_prop(o, "action-name") for o in menu.iter("object")) if a}


def analyse(path):
    """{block id: {tab, menu, icons, only_here, duplicate_icons}} for the trailing blocks of one notebookbar.ui."""
    root = ET.parse(path).getroot()
    menus = {o.get("id"): o for o in root.findall("object") if o.get("class") == "GtkMenu"}
    control = next(o for o in root.iter("object") if o.get("class") == "sfxlo-NotebookbarTabControl")
    ribbon, blocks = set(), {}

    def walk(obj, tab, block, hidden):
        hidden = hidden or not _visible(obj)
        klass, ident = obj.get("class"), obj.get("id") or ""
        if klass == "sfxlo-DropdownBox":
            block = blocks.setdefault(ident, {"tab": tab, "menu": set(), "icons": [], "hidden": hidden})
        if klass in ITEMS and not hidden:
            action = _prop(obj, "action-name")
            if action and block is not None:
                block["icons"].append(command_name(action))
            elif action and not ident.startswith(LAUNCHER_PREFIX):
                ribbon.add(command_name(action))  # a group's launcher arrow does not count as the command's button
        elif klass == "svtlo-ManagedMenuButton" and ":" in ident and not hidden:
            menu = menus.get(ident.split(":", 1)[1])
            if menu is not None:
                if block is not None and not ident.startswith("btn"):
                    block["menu"] |= _menu_commands(menu)
                else:
                    ribbon.update(_menu_commands(menu))  # a ribbon drop-down
        for child in obj.findall("child"):
            for sub in child.findall("object"):
                walk(sub, tab, block, hidden)

    pending = None
    for child in control.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if child.get("type") != "tab":
            pending = obj
            continue
        if pending is not None:
            walk(pending, obj.get("id"), None, False)
        pending = None
    for block in blocks.values():
        block["only_here"] = sorted((block["menu"] | set(block["icons"])) - ribbon)
        block["duplicate_icons"] = [c for c in block["icons"] if c in ribbon]
        block["menu"] = sorted(block["menu"])
    return blocks


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--src")
    source.add_argument("--instdir")
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--json")
    args = parser.parse_args()
    report = {}
    for app in args.apps.split(","):
        path = (os.path.join(args.src, UI[app]) if args.src else
                os.path.join(args.instdir, "share/config/soffice.cfg/modules", MODULE[app], "ui/notebookbar.ui"))
        report[app] = analyse(path)
        for ident, block in report[app].items():
            state = "hidden" if block["hidden"] else ("remove" if not block["only_here"] else "keep")
            print(f"{app:8} {ident:16} {block['tab'] or '':18} {state:6} only-here {len(block['only_here']):2} "
                  f"{', '.join(block['only_here'])[:90]}  dup-icons {', '.join(block['duplicate_icons'])}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
