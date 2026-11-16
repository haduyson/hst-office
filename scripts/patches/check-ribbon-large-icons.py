#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Every large button of the four Tabbed ribbons shows a 24 px image (owner rule; Paste alone stays larger).

Usage: scripts/patches/check-ribbon-large-icons.py --tree DIR   (a LibreOffice tree with the whole series applied)

A large button is a tool button in a toolbox drawn large (icon_size 3 or 5, or toolbar-style "both"). It breaks
the rule when its toolbox asks for 32 px images (icon_size 5) or the button names an image other than a 24 px one
(icon-name not cmd/lc_...), and when a large menu button (image above its label) shows a GtkImage other than a
24 px one. Exit code 0 when every ribbon holds, 1 otherwise, 2 on a usage or read error.
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET

RIBBONS = {
    "Writer": "sw/uiconfig/swriter/ui/notebookbar.ui",
    "Sheets": "sc/uiconfig/scalc/ui/notebookbar.ui",
    "Slides": "sd/uiconfig/simpress/ui/notebookbar.ui",
    "Draw": "sd/uiconfig/sdraw/ui/notebookbar.ui",
}
BUTTONS = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")
MENU_BUTTONS = ("svtlo-ManagedMenuButton", "GtkMenuButton")  # large when their image sits above the label
EXEMPT = {".uno:Paste"}  # Paste keeps its 32 px image, as in the reference suite


def properties(obj):
    return {p.get("name"): p.text for p in obj.findall("property")}


def violations(root):
    """(button id, command, reason) of every large button not drawn at 24 px."""
    parent = {child: node for node in root.iter() for child in node}
    out = []
    for button in root.iter("object"):
        if button.get("class") not in BUTTONS:
            continue
        own = properties(button)
        toolbox = parent.get(parent.get(button))
        box = properties(toolbox) if toolbox is not None else {}
        if box.get("icon_size") not in ("3", "5") and box.get("toolbar-style") != "both":
            continue
        if own.get("action-name") in EXEMPT:
            continue
        if box.get("icon_size") == "5":
            out.append((button.get("id"), own.get("action-name"), "toolbox of 32 px images (icon_size 5)"))
        icon = own.get("icon-name")
        if icon and not icon.startswith("cmd/lc_"):
            out.append((button.get("id"), own.get("action-name"), f"names {icon}, not a 24 px cmd/lc_ image"))
    images = {obj.get("id"): properties(obj) for obj in root.iter("object") if obj.get("class") == "GtkImage"}
    for button in root.iter("object"):
        own = properties(button)
        if button.get("class") not in MENU_BUTTONS or own.get("image-position") != "top":
            continue
        icon = images.get(own.get("image"), {}).get("icon-name")
        if icon and not icon.startswith("cmd/lc_"):
            out.append((button.get("id"), own.get("image"), f"image {icon}, not a 24 px cmd/lc_ image"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True)
    args = parser.parse_args(argv)
    failures = 0
    for app, path in RIBBONS.items():
        try:
            root = ET.parse(os.path.join(args.tree, path)).getroot()
        except (OSError, ET.ParseError) as error:
            print(f"cannot read {path}: {error}", file=sys.stderr)
            return 2
        for button, command, reason in violations(root):
            failures += 1
            print(f"{app} {button} ({command}): {reason}")
    print(f"large ribbon icons: {failures} button(s) not at 24 px in {len(RIBBONS)} ribbons")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
