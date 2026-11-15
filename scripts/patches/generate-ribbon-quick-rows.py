#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Quick command rows of the compact ribbon: data/ribbon/quick-rows.json and its C++ header.

Usage: scripts/patches/generate-ribbon-quick-rows.py --tree DIR [--fill] [--header OUT] [--check]

--fill (re)makes the generated row of every tab (merged group box) without a hand-made one: up to 10 commands,
each group's main command (its first large button, else its first labelled item; fine-tuning items aside), taken from that app's own notebookbar.ui, so a row never brings a
command into an app that does not have it. Rows already in the file (Writer's Home and Insert from the approved
mockup, or the owner's edits) are kept. --header writes sfx2/source/notebookbar/HstRibbonQuickRows.hxx.
--check only validates: every command of a row must be one of its app's notebookbar.ui ("|" is a separator).
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data/ribbon/quick-rows.json")
UI = {"writer": "sw/uiconfig/swriter/ui/notebookbar.ui", "calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
      "impress": "sd/uiconfig/simpress/ui/notebookbar.ui", "draw": "sd/uiconfig/sdraw/ui/notebookbar.ui"}
SKIP_BOXES = {"pmhbFile"}  # the File tab opens the File page
MAX = 10


# fine-tuning items that never make a tab's main command: alignment and indent steps, spin fields, resets
SKIP_COMMANDS = ("Align", "CellVert", "Textdirection", "ParaMargin", "Spacing", "Indent", "LeftToRight",
                 "RightToLeft", "SetDefault", "ResetAttributes", "Grow", "Shrink", "SubScript", "SuperScript",
                 "FontHeight", "CharFontName", "Paraspace", "LineSpacing", "Increment", "Decrement")


def commands(group):
    """[(command, kind)] of a group in ribbon order: kind "large" (label below), "labelled" (label beside) or
    "icon"; launchers (caption row) and fine-tuning items aside."""
    out = []
    for box in group.iter("object"):
        if "ToolBox" not in (box.get("class") or ""):
            continue
        style = next((p.text for p in box.findall("property") if p.get("name") == "toolbar-style"), "")
        kind = {"both": "large", "both-horiz": "labelled", "text": "labelled"}.get(style, "icon")
        for item in box.iter("object"):
            ident = item.get("id") or ""
            command = next((p.text for p in item.findall("property") if p.get("name") == "action-name"), None)
            if (not command or ident.startswith(("btnHstLaunch", "bxHstCaption"))
                    or any(word in command for word in SKIP_COMMANDS) or command in [c for c, _ in out]):
                continue
            out.append((command, kind))
    return out


def boxes(path):
    """{box id: [[(command, kind)] of each group]} of the merged group boxes of a notebookbar.ui."""
    result = {}
    for box in ET.parse(path).iter("object"):
        if box.get("class") == "sfxlo-PriorityMergedHBox" and box.get("id") not in SKIP_BOXES:
            groups = [c.find("object") for c in box.findall("child") if c.find("object") is not None]
            result[box.get("id")] = [commands(g) for g in groups]
    return result


def primary(group):
    """A group's main command: its first large button, else its first labelled item, else none."""
    for wanted in ("large", "labelled"):
        found = [c for c, kind in group if kind == wanted]
        if found:
            return found[0], wanted
    return None, None


def default_row(groups):
    """Main commands of the groups, large buttons first (ribbon order), then the labelled ones; up to MAX,
    filled with the groups' next large buttons."""
    picks = [primary(g) for g in groups]
    row = [c for c, kind in picks if kind == "large"] + [c for c, kind in picks if kind == "labelled"]
    for group in groups:
        for command, kind in group:
            if kind == "large" and command not in row:
                row.append(command)
    return list(dict.fromkeys(row))[:MAX]


def known_commands(path):
    return {p.text for p in ET.parse(path).iter("property") if p.get("name") == "action-name" and p.text}


def validate(data, tree):
    errors = []
    for row in data["rows"]:
        known = known_commands(os.path.join(tree, UI[row["app"]]))
        errors += [f"{row['app']}/{row['box']}: {c} is not a command of {row['app']}" for c in row["commands"]
                   if c != "|" and c not in known]
    return errors


def header(data):
    def ids(values):
        return ", ".join(f'u"{v}"' for v in values)
    lines = ["/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */", "/*",
             " * This file is part of the LibreOffice project.", " *",
             " * This Source Code Form is subject to the terms of the Mozilla Public",
             " * License, v. 2.0. If a copy of the MPL was not distributed with this",
             " * file, You can obtain one at http://mozilla.org/MPL/2.0/.", " */", "", "#pragma once", "",
             "// HST Office: quick command rows of the compact ribbon. GENERATED by",
             "// scripts/patches/generate-ribbon-quick-rows.py from data/ribbon/quick-rows.json; do not edit.", "",
             "#include <cstddef>", "#include <iterator>", "#include <string_view>", "",
             "namespace hst::ribbon::quick", "{", "struct Row", "{", "    std::u16string_view app;",
             "    std::u16string_view box; // the tab's merged group box", "    const std::u16string_view* commands; // u\"|\": a separator",
             "    std::size_t count;", "};", ""]
    entries = []
    for index, row in enumerate(data["rows"]):
        name = f"row{index}"  # box ids may hold spaces ("pmhbTable Design Tab")
        lines.append(f"inline constexpr std::u16string_view {name}[] = {{ {ids(row['commands'])} }}; // {row['app']} {row['box']}")
        entries.append(f'    {{ u"{row["app"]}", u"{row["box"]}", {name}, std::size({name}) }},')
    lines += ["", "inline constexpr Row all[] = {", *entries, "};", "}", "", "/* vim:set shiftwidth=4 softtabstop=4 expandtab: */"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True)
    parser.add_argument("--fill", action="store_true")
    parser.add_argument("--header")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.load(open(DATA, encoding="utf-8"))
    if args.fill:
        data["rows"] = [r for r in data["rows"] if not r.get("generated")]  # hand-made rows stay
        have = {(r["app"], r["box"]) for r in data["rows"]}
        for app, path in UI.items():
            for box, groups in boxes(os.path.join(args.tree, path)).items():
                if (app, box) not in have and default_row(groups):
                    data["rows"].append({"app": app, "box": box, "commands": default_row(groups), "generated": True})
        json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    errors = validate(data, args.tree)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 2
    if args.header and not args.check:
        open(args.header, "w", encoding="utf-8").write(header(data))
    print(f"{len(data['rows'])} rows ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
