#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Command parity of the v3 ribbons with 1.0.2: hst-ribbon-v3-ui.patch may move commands, never drop one.

Usage: scripts/patches/check-ribbon-v3-parity.py --tree DIR      (a tree with the whole series applied)

The four notebookbar.ui files of DIR are compared with themselves before hst-ribbon-v3-ui.patch (the patch reversed in
a temporary copy): every command item (action-name) and every menu item must still be there, and the only added
commands are ADDED, the owner's additions to the locked design. Exit 1 on any difference.
"""
import argparse
import collections
import os
import shutil
import subprocess
import sys
import tempfile

from lxml import etree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ribbon_v3_ui as v3  # noqa: E402

PATCH = os.path.join(HERE, "..", "..", "patches", "libreoffice", "hst-ribbon-v3-ui.patch")
# the owner's additions: the chemical formula button (Home > Font) and the formula buttons beside the insert-formula
# button (Insert > Symbols), all commands of the HST extension
FORMULAS = {"org.hst.office.vi:ConvertFormulas": 1, "org.hst.office.vi:FormulaTemplates": 1}
# Writer only: the TeX toggle beside the formula buttons (Insert > Symbols), a command of the HST extension
WRITER_TEX = {"org.hst.office.vi:TexToggle": 1}
# the 1.0.3 features attached to the ribbon: the "Trợ lý AI" group of Phần mở rộng (Sheets adds the formula pair), and
# Sheets' Flash Fill (Dữ liệu > Công cụ dữ liệu) and table options (contextual Thiết kế bảng)
AI = {"org.hst.office.ai:Writing": 1, "org.hst.office.ai:Help": 1, "org.hst.office.ai:Options": 1}
SHEETS_FEATURES = {"org.hst.office.ai:FormulaWrite": 1, "org.hst.office.ai:FormulaExplain": 1, ".uno:FlashFill": 1,
                   ".uno:HstTableAutoExpand": 1, ".uno:HstTableCalculatedColumns": 1, ".uno:HstTableUndoAutoExpand": 1}
ADDED = {"writer": {"org.hst.office.vi:ChemFormula": 1, **FORMULAS, **AI, **WRITER_TEX},
         "sheets": {**FORMULAS, **AI, **SHEETS_FEATURES},
         "slides": {"org.hst.office.vi:ChemFormula": 1, **FORMULAS, **AI},
         "draw": {"org.hst.office.vi:ChemFormula": 1, **FORMULAS, **AI}}
MENU_ITEMS = ("GtkMenuItem", "GtkCheckMenuItem", "GtkRadioMenuItem")


def inventory(path):
    """(command items by action-name, menu item count) of a .ui file."""
    root = ET.parse(path).getroot()
    commands, menus = collections.Counter(), 0
    for obj in root.iter("object"):
        for prop in obj.findall("property"):
            if prop.get("name") == "action-name" and prop.text:
                commands[prop.text] += 1
        menus += obj.get("class") in MENU_ITEMS
    return commands, menus


def check(tree, patch=PATCH):
    """[(app, message)] differences, and {app: (commands before, after)}."""
    problems, counts = [], {}
    with tempfile.TemporaryDirectory() as before:
        for rel in v3.UI_FILES.values():
            os.makedirs(os.path.dirname(os.path.join(before, rel)), exist_ok=True)
            shutil.copy(os.path.join(tree, rel), os.path.join(before, rel))
        with open(patch, encoding="utf-8") as handle:
            reverse = subprocess.run(["patch", "-R", "-p1", "-s", "--fuzz=0", "-d", before], stdin=handle,
                                     capture_output=True, text=True)
        if reverse.returncode:
            return [("-", f"{os.path.basename(patch)} does not reverse on the tree: {reverse.stdout.strip()}")], {}
        for app, rel in v3.UI_FILES.items():
            old, old_menus = inventory(os.path.join(before, rel))
            new, new_menus = inventory(os.path.join(tree, rel))
            lost, gained = old - new, new - old
            if lost:
                problems.append((app, f"commands lost: {dict(lost)}"))
            if dict(gained) != ADDED[app]:
                problems.append((app, f"commands added {dict(gained)}, expected {ADDED[app]}"))
            if old_menus != new_menus:
                problems.append((app, f"menu items {old_menus} -> {new_menus}"))
            counts[app] = (sum(old.values()), sum(new.values()), old_menus, new_menus)
    return problems, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True)
    args = parser.parse_args()
    problems, counts = check(args.tree)
    for app, (old, new, old_menus, new_menus) in counts.items():
        print(f"{app}: command items {old} -> {new}, menu items {old_menus} -> {new_menus}")
    for app, text in problems:
        print(f"{app}: {text}")
    print(f"ribbon v3 parity: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
