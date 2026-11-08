# SPDX-License-Identifier: AGPL-3.0-only
"""On-screen part of check-slides-animation-gallery.py: the gallery on the ribbon's Animation tab."""
import importlib.util
import os
import time

import hst_gui
from slides_animation_gallery_uno import COMMAND, ROWS, record, settled_effects

GALLERY_NAMES = ("Hiệu ứng hoạt hình", "Animations")


def ribbon_tab_list(tabs):
    """Find the ribbon shallowly; never recurse through slide panes or document shapes."""
    app = tabs.office_app()
    queue = [(app, 0)] if app else []
    while queue:
        node, depth = queue.pop(0)
        role = node.getRoleName()
        if role == "page tab list":
            x, y, width, height = tabs.extents(node)
            if width > 0 and 0 <= y < 200:
                return node
        if depth >= 7 or role in ("document frame", "document presentation", "drawing area",
                                 "tree", "tree table", "list", "table", "scroll pane"):
            continue
        queue.extend((node.getChildAtIndex(i), depth + 1) for i in range(min(node.childCount, 60))
                     if node.getChildAtIndex(i) is not None)
    return None


def check_gallery_on_screen(office, doc, page, args):
    ui = os.path.join(args.instdir, "share/config/soffice.cfg/modules/simpress/ui/notebookbar.ui")
    with open(ui, encoding="utf-8") as handle:
        if COMMAND not in handle.read():
            ROWS.append({"check": "gallery on screen", "status": "SKIP", "detail": "S5 notebookbar item is absent"})
            print("SKIP  gallery on screen: the notebookbar has no animation gallery item yet", flush=True)
            return
    spec = importlib.util.spec_from_file_location("ribbon_tabs", os.path.join(os.path.dirname(__file__), "check-ribbon-tabs.py"))
    tabs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tabs)
    for wid, _name in hst_gui.toplevels(args.display, office.pid):
        tabs.xdo(args.display, "windowmove", wid, "0", "0")
        tabs.xdo(args.display, "windowsize", wid, "1485", "900")
    time.sleep(3)
    tab_list = ribbon_tab_list(tabs)
    nodes = list(tabs.walk(tab_list)) if tab_list else []
    tab = next((n for n in nodes if n.getRoleName() == "page tab"
                and n.name in ("Hoạt hình", "Hiệu ứng", "Animations", "Animation")), None)
    if tab:
        tabs.click(args.display, tabs.extents(tab))
        time.sleep(2)
    # The tool item carries the command label, which in Vietnamese equals the icon view's name; the gallery
    # is the named node whose children are the effect items.
    gallery = next((n for n in (tabs.walk(tab_list) if tab_list else ())
                    if (n.name or "") in GALLERY_NAMES and n.childCount > 1
                    and n.getChildAtIndex(0) is not None
                    and n.getChildAtIndex(0).getRoleName() in ("list item", "icon", "table cell")), None)
    items = [gallery.getChildAtIndex(i) for i in range(gallery.childCount)] if gallery else []
    item_names = [i.name for i in items]
    office.screenshot(os.path.join(args.out, "gallery.png"))
    record("gallery is on the Animation tab with named effect items", tab is not None and len(items) >= 2
           and all(item_names), item_names)
    if len(items) < 2:
        return
    record("effect accessible name includes its class", items[1].name.endswith(("(Vào)", "(Entrance)")), items[1].name)
    tabs.click(args.display, tabs.extents(items[1]))
    current = settled_effects(page)
    record("click applies the visible Appear effect", len(current) == 1 and current[0]["id"] == "ooo-entrance-appear", current)
    # State describes only the first effect; activating the same preset must still replace effects.
    gallery.queryComponent().grabFocus()
    time.sleep(0.3)
    doc.getUndoManager().clear()
    tabs.xdo(args.display, "key", "Return")
    current = settled_effects(page)
    record("Enter reapplies the selected preset as one action", len(current) == 1
           and current[0]["id"] == "ooo-entrance-appear"
           and len(doc.getUndoManager().getAllUndoActionTitles()) == 1, current)
    before_names = item_names
    next_button = next((n for n in tabs.walk(tab_list) if n.name in ("Các hiệu ứng tiếp theo", "Next animations")), None)
    if next_button:
        tabs.click(args.display, tabs.extents(next_button))
    after_names = [gallery.getChildAtIndex(i).name for i in range(gallery.childCount)]
    record("next pages through the gallery", next_button is not None and after_names != before_names, after_names)
    more = next((n for n in tabs.walk(tab_list) if n.name in ("Tất cả hiệu ứng", "All animations")), None)
    record("the deck button has an accessible name", more is not None)
    if more:
        tabs.click(args.display, tabs.extents(more))
        office.screenshot(os.path.join(args.out, "animation-deck.png"))
