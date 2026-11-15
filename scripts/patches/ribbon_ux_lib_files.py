# SPDX-License-Identifier: AGPL-3.0-only
"""Gla11y suppressions and Vietnamese .po entries of the ribbon UX rework generators (re-exported by
ribbon_ux_lib.py, which documents the generators)."""
from ribbon_ux_lib_core import BUTTON_CLASSES, read


def unlabelled_buttons(root):
    """Ids of toolbox items without a label property (gla11y button-no-label)."""
    return [(o.get("class"), o.get("id")) for o in root.iter("object")
            if o.get("class") in BUTTON_CLASSES and o.get("id")
            and not any(p.get("name") == "label" for p in o.findall("property"))]


def unlabelled_menu_items(root):
    """Ids of menu items without a label property (their command names them; gla11y button-no-label)."""
    return [o.get("id") for o in root.iter("object")
            if o.get("class") == "GtkMenuItem" and o.get("id")
            and not any(p.get("name") == "label" for p in o.findall("property"))]


def suppr(tree, suppr_path, ui_path, root):
    """The module's .suppr with this file's button-no-label lines for the current toolbox items and menu items
    (every other line is kept as it is)."""
    old = read(tree, suppr_path)
    lines = old.splitlines(keepends=True)
    keep_other = [line for line in lines if not (line.startswith(ui_path + ":") and line.rstrip().endswith("button-no-label"))]
    first = next((i for i, line in enumerate(lines) if line.startswith(ui_path + ":") and "button-no-label" in line), None)
    mine = [f"{ui_path}://{k}[@id='{i}'] button-no-label\n" for k, i in unlabelled_buttons(root)]
    mine += [f"{ui_path}://GtkMenuItem[@id='{i}'] button-no-label\n" for i in unlabelled_menu_items(root)]
    if first is None:
        return "".join(keep_other + mine)
    before = sum(1 for line in lines[:first] if line in keep_other)
    return "".join(keep_other[:before] + mine + keep_other[before:])


# --- Vietnamese strings ----------------------------------------------------------------------------------

def po_escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def po_entry(ui_path, context, msgid, msgstr, key="hstUX"):
    return (f'#. {key}\n#: {ui_path}\nmsgctxt "{po_escape(context)}"\nmsgid "{po_escape(msgid)}"\n'
            f'msgstr "{po_escape(msgstr)}"\n\n')


def po_with_entries(text, ui_path, strings, anchor):
    """text of a messages.po with new entries (context, msgid, msgstr) before the entry holding `anchor`
    (a unique line such as 'msgctxt "insertslidesdialog|links"'); an entry whose (context, msgid) already
    exists gets the new msgstr instead."""
    new_entries = []
    for context, msgid, msgstr in strings:
        head = f'msgctxt "{po_escape(context)}"\nmsgid "{po_escape(msgid)}"\n'
        at = text.find(head + "msgstr ")
        if at >= 0:
            start = at + len(head)
            end = text.index("\n", start)
            while text.startswith('\n"', end):  # a msgstr continued on the next lines
                end = text.index("\n", end + 1)
            text = text[:start] + f'msgstr "{po_escape(msgstr)}"' + text[end:]
        else:
            new_entries.append(po_entry(ui_path, context, msgid, msgstr))
    if not new_entries:
        return text
    if text.count(anchor) != 1:
        raise RibbonUxError(f"po anchor {anchor!r}: {text.count(anchor)} matches")
    at = text.find(anchor)
    start = text.rfind("\n\n", 0, at) + 2
    return text[:start] + "".join(new_entries) + text[start:]


def translatable_strings(root):
    """{(context, msgid)} of every translatable property in the tree."""
    return {(p.get("context"), p.text) for p in root.iter("property") if p.get("translatable") == "yes"}
