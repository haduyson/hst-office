# SPDX-License-Identifier: AGPL-3.0-only
"""Editing helpers of the ribbon UX rework generators (re-exported by ribbon_ux_lib.py)."""
import xml.etree.ElementTree as ET

from ribbon_ux_lib_core import RibbonUxError, holder, packing, parse_text, set_prop


# --- editing ---------------------------------------------------------------------------------------------

def remove(root, obj):
    hold, parent = holder(root, obj)
    parent.remove(hold)
    return hold


def remove_ids(root, ids):
    for oid in ids:
        remove(root, find(root, oid))


def move_into(root, obj, target, index=None, pack=None):
    """Move obj (with its <child> holder) into target object, at child index (None: last)."""
    hold = remove(root, obj)
    if pack is not None:
        for key, value in pack.items():
            packing(hold, key, value)
    insert_child(target, hold, index)
    return hold


def insert_child(target, hold, index=None):
    kids = [k for k in target if k.tag == "child"]
    if index is None or index >= len(kids):
        after = kids[-1] if kids else None
        pos = list(target).index(after) + 1 if after is not None else len(list(target))
        # keep <accessibility>/<style> last
        trailing = [k for k in target if k.tag in ("accessibility", "style")]
        if trailing:
            pos = min(pos, list(target).index(trailing[0]))
        target.insert(pos, hold)
    else:
        target.insert(list(target).index(kids[index]), hold)


def fragment(xml):
    """Parse an XML fragment (one or more <child> elements) into a list of elements."""
    return list(parse_text(f"<interface>{xml}</interface>"))


def check_unique(root):
    seen = set()
    for obj in root.iter("object"):
        oid = obj.get("id")
        if oid and oid in seen:
            raise RibbonUxError(f"duplicate id {oid!r}")
        seen.add(oid)
    for node in root.iter("relation"):
        if node.get("target") not in seen:
            raise RibbonUxError(f"relation to a missing object {node.get('target')!r}")
    for obj in root.iter("object"):  # VclBuilder makes a widget at its first child: later properties are lost
        kinds = [c.tag for c in obj if c.tag in ("property", "child")]
        if "child" in kinds and "property" in kinds[kinds.index("child"):]:
            raise RibbonUxError(f"{obj.get('id')!r} has a property after a child")


def tool_button(bid, command, klass="GtkToolButton", label=None, context=None, ribbon_label=None,
                description=None, icon=None, visible=True):
    """A <child> holding a toolbox item. label: the .ui label (English, translatable when context is
    given); ribbon_label/description: the ribbon-only label and the tooltip's second line (translatable)."""
    obj = ET.Element("object", {"class": klass, "id": bid})
    set_prop(obj, "visible", "True" if visible else "False")
    set_prop(obj, "can-focus", "False")
    if label is not None:
        set_prop(obj, "label", label, translatable=context is not None, context=context)
    if ribbon_label is not None:
        set_prop(obj, "hst-ribbon-label", ribbon_label, translatable=True, context=context)
    if description is not None:
        set_prop(obj, "hst-ribbon-description", description, translatable=True, context=context)
    set_prop(obj, "action-name", command)
    if icon:
        set_prop(obj, "icon-name", icon)
    if klass != "GtkMenuToolButton":
        set_prop(obj, "use-underline", "True")
    hold = ET.Element("child")
    hold.append(obj)
    pack = ET.SubElement(hold, "packing")
    set_prop(pack, "expand", "False")
    set_prop(pack, "homogeneous", "True")
    return hold
