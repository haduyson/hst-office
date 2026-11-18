#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""AT-SPI side of check-backstage-print-margins.py (system python3 with pyatspi; the office's own python has UNO).

The File panel is a popup of its own that UITest does not reach, so its Print page is read through AT-SPI (gtk3 with
the atk bridge, as check-backstage.py does). Usage:
    backstage_print_atspi.py state            -> JSON {"margins": shown entry, "showing": bool, "pages": "/ N"}
                                                 (null fields when the page is not up)
    backstage_print_atspi.py focus            -> gives the margins box the keyboard focus (the caller then steps its
                                                 entries with Down: vcl's gtk3 box takes no AT-SPI selection)
    backstage_print_atspi.py dialog [cancel]  -> JSON {"dialog": name of a showing dialog or null}; "cancel" presses
                                                 its "Hủy" button
    backstage_print_atspi.py panels           -> JSON {"panels": showing print panels, "pages": their "/ N" labels,
                                                 "english": showing panel labels left in English}
                                                 (each panel has one page count label next to its preview)
"""
import json
import sys

import pyatspi

ENGLISH = {"Printer", "Range and Copies", "Number of copies", "Page Setup", "More Options", "Whole Page", "Print"}

def walk(node, out, depth=0):
    try:
        role = node.getRoleName()
        out.append((role, node.name or "", node))
        if role.startswith("document") or node.childCount > 500 or depth > 60:
            return out
        for index in range(node.childCount):
            walk(node.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def office():
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if app is not None and (app.name or "").lower() in ("soffice", "soffice.bin", "hst office", "libreoffice"):
            return app
    names = [desktop.getChildAtIndex(i).name for i in range(desktop.childCount) if desktop.getChildAtIndex(i)]
    raise SystemExit("no office on the accessibility bus: %s" % names)


def margins_box(found):
    """The shown combo box the "Lề trang:" label is for (vcl wraps a hidden GtkComboBox and its own box in a filler)."""
    for role, name, node in found:
        if role == "label" and name.rstrip(":").strip() == "Lề trang":
            for relation in node.getRelationSet():
                if relation.getRelationType() == pyatspi.RELATION_LABEL_FOR and relation.getNTargets():
                    target = relation.getTarget(0)
                    boxes = [target.getChildAtIndex(i) for i in range(target.childCount)]
                    boxes = [b for b in boxes if b.getRoleName() == "combo box"
                             and b.getState().contains(pyatspi.STATE_VISIBLE)]
                    return boxes[0] if boxes else target
    return None


def dialog(found, cancel):
    for role, name, node in found:
        if role == "dialog" and node.getState().contains(pyatspi.STATE_SHOWING):
            # a dialog with a showing "Hủy" (the File panel keeps the print dialog's Cancel hidden)
            buttons = [n for r, label, n in walk(node, []) if r == "push button" and label in ("Hủy", "Huỷ")
                       and n.getState().contains(pyatspi.STATE_SHOWING)]
            if not buttons:
                continue
            if cancel:
                buttons[0].queryAction().doAction(0)
            print(json.dumps({"dialog": name}, ensure_ascii=False))
            return 0
    print(json.dumps({"dialog": None}))
    return 0


def main():
    found = walk(office(), [])
    if sys.argv[1] == "dialog":
        return dialog(found, sys.argv[2:] == ["cancel"])
    if sys.argv[1] == "panels":
        pages = [name for role, name, node in found
                 if role == "label" and name.startswith("/ ") and node.getState().contains(pyatspi.STATE_SHOWING)]
        # labels of the panel that a Vietnamese UI must not show in English
        english = sorted({name for role, name, node in found
                          if role in ("label", "push button") and name.rstrip(".:…") in ENGLISH
                          and node.getState().contains(pyatspi.STATE_SHOWING)})
        print(json.dumps({"panels": len(pages), "pages": pages, "english": english}, ensure_ascii=False))
        return 0
    combo = margins_box(found)
    if sys.argv[1] == "focus":
        ok = combo is not None and combo.queryComponent().grabFocus()
        print(json.dumps({"focused": bool(ok)}))
        return 0 if ok else 1
    pages = [name for role, name, node in found
             if role == "label" and name.startswith("/ ") and node.getState().contains(pyatspi.STATE_SHOWING)]
    # the name follows the user's picks; the entry the office set when the page opened is not announced
    print(json.dumps({"margins": combo.name if combo else None,
                      # the row's label: vcl hides and shows it with the box (its gtk3 box keeps inner parts visible)
                      "showing": any(role == "label" and name.rstrip(":").strip() == "Lề trang"
                                     and node.getState().contains(pyatspi.STATE_VISIBLE) for role, name, node in found),
                      "pages": pages[0] if pages else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
