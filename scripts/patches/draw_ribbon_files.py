# SPDX-License-Identifier: AGPL-3.0-only
"""The other files of hst-ribbon-draw.patch (generate-draw-ribbon.py): sdraw.suppr, ToolbarMode.xcu, the Vietnamese
strings in sd/messages.po, and the unified diff of each file."""
import difflib
import os
import xml.etree.ElementTree as ET

from draw_ribbon_data import BUTTON_CLASSES, DRAW_SUPPR, DRAW_UI, STRINGS, TOOLBAR_MODE, VI_PO, DrawRibbonError


def suppr(tree, ui_text):
    """sdraw.suppr: other files' lines as they are, this file's lines for its unlabelled buttons."""
    root = ET.fromstring(ui_text)
    lines = []
    for obj in root.iter("object"):
        if obj.get("class") in BUTTON_CLASSES and obj.get("id") \
                and not any(p.get("name") == "label" for p in obj.findall("property")):
            lines.append(f"{DRAW_UI}://{obj.get('class')}[@id='{obj.get('id')}'] button-no-label\n")
    with open(os.path.join(tree, DRAW_SUPPR), encoding="utf-8") as handle:
        old = handle.readlines()
    first = next(i for i, line in enumerate(old) if line.startswith(DRAW_UI + ":"))
    rest = [line for line in old if not line.startswith(DRAW_UI + ":")]
    return "".join(rest[:first] + lines + rest[first:])


def toolbar_mode(tree):
    with open(os.path.join(tree, TOOLBAR_MODE), encoding="utf-8") as handle:
        text = handle.read()
    old = '    <node oor:name="Draw" oor:op="replace">\n      <prop oor:name="Active">\n        <value>Default</value>'
    if text.count(old) != 1:
        raise DrawRibbonError("ToolbarMode.xcu: Draw's active mode is not the tarball's")
    text = text.replace(old, old.replace("Default", "notebookbar.ui"))
    # Draw's Tabbed mode keeps the menu bar upstream; the other apps' Tabbed modes have none
    draw = text.index('    <node oor:name="Draw" oor:op="replace">')
    tabbed = text.index('        <node oor:name="Tabbed" oor:op="replace">', draw)
    end = text.index("\n        </node>", tabbed)
    menubar = '          <prop oor:name="HasMenubar">\n            <value>true</value>'
    at = text.find(menubar, tabbed, end)
    if at < 0:
        raise DrawRibbonError("ToolbarMode.xcu: Draw's Tabbed mode has no menu bar setting to turn off")
    return text[:at] + menubar.replace("true", "false") + text[at + len(menubar):]


def po_entry(context, msgid, msgstr):
    return (f'#. hstDR\n#: {DRAW_UI}\nmsgctxt "{context}"\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n\n')


# The new strings go before this entry: it and the eight lines around it are the same in the tarball's
# sd/messages.po and in a tree whose Vietnamese l10n/ already filled (the TabbedDraw entries are not).
PO_ANCHOR = 'msgctxt "insertslidesdialog|links"'


def po(tree):
    """New entries before PO_ANCHOR's entry of sd/messages.po."""
    with open(os.path.join(tree, VI_PO), encoding="utf-8") as handle:
        text = handle.read()
    at = text.find(PO_ANCHOR)
    start = text.rfind("\n\n", 0, at) + 2 if at >= 0 else -1
    if at < 0 or text.count(PO_ANCHOR) != 1 or not text.startswith("#. ", start):
        raise DrawRibbonError("sd/messages.po: the anchor entry for the new strings is missing")
    entries = "".join(po_entry(*s) for s in STRINGS)
    return text[:start] + entries + text[start:]


def file_diff(tree, path, new, context):
    with open(os.path.join(tree, path), encoding="utf-8") as handle:
        old = handle.read()
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                      fromfile=f"a/{path}", tofile=f"b/{path}", n=context))
    if not lines:
        raise DrawRibbonError(f"{path}: no change")
    return "".join(lines)


