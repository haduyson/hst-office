# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog containers for check-access-keys.py: mnemonics of the .ui dialogs in the source tree.

One container per toplevel object of a .ui file; a GtkMenu nested in it (a popup) is a
container of its own. Only labels with use-underline count ("_" is otherwise literal text).
Notebookbar .ui files are skipped: the main ribbons are in the menu/ribbon model and the
grouped bars switch their visible buttons per context.

Dialogs are read from the tree only (never stored in the snapshot, which would grow by
several megabytes), so CI without a tree skips them. A dialog collision is strict when
English does not have it (the colliding items do not share one English key) and an HST
override chose one of the colliding keys; a non-ASCII key is strict when an override chose
it. Everything else comes from the upstream Vietnamese translation and is a warning.
"""
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

TRUE = ("True", "true", "1", "yes")


def dialog_containers(tree, builder):
    """Containers of type "dialogs"; `builder` is a check-access-keys ModelBuilder for `tree`."""
    containers = []

    def new(name):
        container = dict(path=name, type="dialogs", app="", strict=True, items=[])
        containers.append(container)
        return container

    for path in sorted(Path(tree).glob("*/uiconfig/**/ui/*.ui")):
        if "notebookbar" in path.name:
            continue
        rel = path.relative_to(tree).as_posix()
        po = rel.split("/")[0] + "/messages.po"

        def walk(obj, container):
            # Old glade files spell properties with "_" (use_underline).
            props = {p.get("name", "").replace("_", "-"): p for p in obj.findall("property")}
            prop, underline = props.get("label"), props.get("use-underline")
            if (prop is not None and prop.get("translatable") == "yes" and "_" in (prop.text or "")
                    and underline is not None and underline.text in TRUE):
                label = builder.label(prop.text, po, prop.get("context"), markers="_")
                container["items"].append(dict(id=obj.get("id", ""), command="", labels=[label]))
            for child in obj.findall("child/object"):
                if child.get("class") == "GtkMenu":
                    walk(child, new(rel + ":" + child.get("id", "menu")))
                else:
                    walk(child, container)

        for top in ET.parse(path).getroot().findall("object"):
            walk(top, new(rel + ":" + top.get("id", "")))
    return [c for c in containers if c["items"]]


def english_groups(container, mnemonic):
    """Item ids grouped by their English mnemonic (upper case)."""
    groups = defaultdict(set)
    for item in container["items"]:
        source = item["labels"][0]
        char = mnemonic(source["english"], source["markers"])
        if char:
            groups[char.upper()].add(item["id"])
    return groups


def is_override(item, overrides):
    source = item["labels"][0]
    return (source["file"], source["msgctxt"], source["msgid"]) in overrides
