# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the ribbon UX rework generators (scripts/patches/generate-ribbon-ux-*.py).

A generator reads a LibreOffice tree with the series applied up to (not including) its own patch, edits the
Tabbed notebookbar.ui of one application as an ElementTree, and writes one patch with the .ui, the Vietnamese
messages.po and the gla11y suppression hunks. serialize_like() writes the edited tree in the file's own
format (glade indentation, "&#10;" line breaks, the glade header), so the diff holds only real changes.

Ribbon-only text (vcl builder, hst-ribbon-ux-engine.patch):
  - "hst-ribbon-label" (translatable) replaces the command's label on the ribbon only (menus and the feature
    search keep the command label);
  - "hst-ribbon-description" (translatable) is the second line of the button's tooltip, under
    "Label (Shortcut)".
"""
import copy
import difflib
import os

import xml.etree.ElementTree as ET

BUTTON_CLASSES = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")


class RibbonUxError(Exception):
    pass


# --- reading and writing ---------------------------------------------------------------------------------

def read(tree, path):
    with open(os.path.join(tree, path), encoding="utf-8") as handle:
        return handle.read()


def parse_text(text):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(text, parser=parser)


def serialize_like(old_text, root):
    """The tree as text in the format of old_text: unchanged lines stay byte-identical."""
    work = copy.deepcopy(root)
    # ElementTree writes a newline inside text as is; glade files write it as a character reference
    for node in work.iter():
        if node.tag is not ET.Comment and node.text and node.text.strip() and "\n" in node.text:
            node.text = node.text.replace("\n", "\ue000")
    ET.indent(work, space="  ")
    # (a file ElementTree wrote, as HST Draw's generated one, keeps literal line breaks)
    newline = "&#10;" if "&#10;" in old_text else "\n"
    body = ET.tostring(work, encoding="unicode").replace("\ue000", newline)
    if '" />' not in old_text:  # glade closes empty elements without the space ElementTree writes
        body = body.replace(" />", "/>")
    head = old_text[:old_text.index("<interface")]
    new_lines = (head + body + "\n").splitlines(keepends=True)
    old_lines = old_text.splitlines(keepends=True)
    # a line that differs from the original only in its indentation keeps the original (glade quirks)
    matcher = difflib.SequenceMatcher(None, [line.strip() for line in old_lines],
                                      [line.strip() for line in new_lines], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        out.extend(old_lines[i1:i2] if tag == "equal" else new_lines[j1:j2])
    return "".join(out)


def file_diff(path, old, new, context=3):
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                      fromfile=f"a/{path}", tofile=f"b/{path}", n=context))
    if not lines:
        raise RibbonUxError(f"{path}: no change")
    return "".join(lines)


def write_patch(out, description, diffs, check=False):
    """Write (or with check, compare) the patch; returns a process exit code."""
    text = description.rstrip("\n") + "\n\nLicense: these upstream files remain under their original license (MPL-2.0).\n---\n" \
        + "".join(diffs)
    if check:
        with open(out, encoding="utf-8") as handle:
            ok = handle.read() == text
        print(("ok: " if ok else "stale: ") + out)
        return 0 if ok else 1
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"wrote {out}")
    return 0


# --- finding ---------------------------------------------------------------------------------------------

def find(root, oid):
    found = [o for o in root.iter("object") if o.get("id") == oid]
    if len(found) != 1:
        raise RibbonUxError(f"object {oid!r}: {len(found)} matches")
    return found[0]


def find_command(root, command, within=None):
    """The one button of `command` (an action-name) inside `within` (default: the whole file)."""
    scope = within if within is not None else root
    found = [o for o in scope.iter("object") if prop(o, "action-name") == command]
    if len(found) != 1:
        raise RibbonUxError(f"command {command!r}: {len(found)} buttons")
    return found[0]


def parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def holder(root, obj):
    """The <child> element that holds obj, and its parent object."""
    parents = parent_map(root)
    hold = parents.get(obj)
    if hold is None or hold.tag != "child":
        raise RibbonUxError(f"{obj.get('id')!r} is not held by a <child>")
    return hold, parents[hold]


def prop(obj, name):
    for p in obj.findall("property"):
        if p.get("name") == name:
            return p.text
    return None


def set_prop(obj, name, value, translatable=None, context=None):
    """Set (or add, before the first <child>) a property; None removes it."""
    existing = [p for p in obj.findall("property") if p.get("name") == name]
    if value is None:
        for p in existing:
            obj.remove(p)
        return
    p = existing[0] if existing else None
    if p is None:
        p = ET.Element("property", {"name": name})
        kids = list(obj)
        first_child = next((i for i, k in enumerate(kids) if k.tag in ("child", "accessibility", "style")), len(kids))
        obj.insert(first_child, p)
    p.text = value
    if translatable:
        p.set("translatable", "yes")
        p.set("context", context)


def packing(child_holder, name, value=None):
    pack = child_holder.find("packing")
    if value is None:
        return None if pack is None else prop(pack, name)
    if pack is None:
        pack = ET.SubElement(child_holder, "packing")
    set_prop(pack, name, str(value))
    return value
