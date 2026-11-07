# SPDX-License-Identifier: AGPL-3.0-only
"""The Slides animation gallery and .uno:HstApplyAnimation (gtk3, vi_VN).

Usage: python3 tests/runtime/check-slides-animation-gallery.py [--instdir DIR] [--display :71] [--out DIR]

Creates one slide with two rectangles and a two-paragraph text box. Checks dispatcher application,
state, undo/redo, replacement, multi-selection WITH_PREVIOUS, None, disabled empty selection,
mixed state, unknown ids, and the text-group rule. Reads the actual UNO main animation sequence.
If the notebookbar contains the command, also checks click/Enter, paging, accessible class labels,
and the deck button, and saves gallery.png. Writes evidence.json; exit 1 on a failed check.
Run on S6's private build, after its component registry has been refreshed.
"""
import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

PORT = 7463
COMMAND = ".uno:HstApplyAnimation"
GALLERY_NAMES = ("Hiệu ứng hoạt hình", "Animations")
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:240]}", flush=True)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def dispatch(office, doc, effect):
    helper = office.service("com.sun.star.frame.DispatchHelper")
    return helper.executeDispatch(doc.getCurrentController().getFrame(), COMMAND, "", 0,
                                  (prop("Effect", effect),))


def state_of(office, doc):
    """Keep enabled separate from state: disabled, mixed (empty), and None are distinct."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL

    class Listener(unohelper.Base, XStatusListener):
        value = None

        def statusChanged(self, event):
            self.value = (event.IsEnabled, event.State)

        def disposing(self, source):
            pass

    url = URL()
    url.Complete = COMMAND
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    provider = doc.getCurrentController().getFrame().queryDispatch(url, "", 0)
    if provider is None:
        return None
    listener = Listener()
    provider.addStatusListener(listener, url)
    try:
        deadline = time.monotonic() + 3
        while listener.value is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return listener.value
    finally:
        provider.removeStatusListener(listener, url)


def select(office, doc, *shapes):
    collection = office.service("com.sun.star.drawing.ShapeCollection")
    for shape in shapes:
        collection.add(shape)
    if not doc.getCurrentController().select(collection):
        raise RuntimeError("The controller refused the shape selection")
    time.sleep(0.3)


def descendants(node):
    yield node
    if hasattr(node, "createEnumeration"):
        children = node.createEnumeration()
        while children.hasMoreElements():
            yield from descendants(children.nextElement())


def effects(page):
    """One record per preset container, only below MAIN_SEQUENCE (never trigger sequences)."""
    from com.sun.star.presentation.EffectNodeType import MAIN_SEQUENCE
    root = page.getAnimationNode()
    sequence = next((node for node in descendants(root)
                     if dict((p.Name, p.Value) for p in node.getUserData()).get("node-type") == MAIN_SEQUENCE), None)
    result = []
    if sequence is None:
        return result
    for node in descendants(sequence):
        data = {p.Name: p.Value for p in node.getUserData()}
        if "preset-id" not in data:
            continue
        targets, paragraphs = set(), set()
        for child in descendants(node):
            if not hasattr(child, "getTarget"):
                continue
            target = child.getTarget()
            if target is None:
                continue
            if hasattr(target, "Shape"):
                paragraphs.add(target.Paragraph)
                target = target.Shape
            targets.add(target.getName())
        result.append({"id": data["preset-id"], "node_type": data.get("node-type"),
                       "targets": sorted(targets), "paragraphs": sorted(paragraphs)})
    return result


def settled_effects(page):
    # MainSequence uses a delayed rebuild; wait before inspecting the UNO animation tree.
    time.sleep(1.2)
    return effects(page)


def make_slide(doc):
    from com.sun.star.awt import Point, Size
    import uno
    page = doc.getDrawPages().getByIndex(0)
    while page.getCount():
        page.remove(page.getByIndex(0))
    shapes = []
    for kind, name, x, y in (("RectangleShape", "Rectangle one", 1800, 1800),
                             ("RectangleShape", "Rectangle two", 10500, 1800),
                             ("TextShape", "Paragraph text", 1800, 7000)):
        shape = doc.createInstance("com.sun.star.drawing." + kind)
        page.add(shape)
        shape.setName(name)
        shape.setPosition(Point(x, y))
        shape.setSize(Size(6500, 2600))
        if kind == "TextShape":
            shape.setPropertyValue("FillStyle", uno.Enum("com.sun.star.drawing.FillStyle", "NONE"))
            shape.setPropertyValue("LineStyle", uno.Enum("com.sun.star.drawing.LineStyle", "NONE"))
            shape.setString("First paragraph\nSecond paragraph")
        shapes.append(shape)
    doc.getCurrentController().setCurrentPage(page)
    return page, shapes


def check_dispatcher(office, doc, page, shapes):
    from com.sun.star.presentation.EffectNodeType import ON_CLICK, WITH_PREVIOUS
    first, second, text = shapes
    undo = doc.getUndoManager()
    select(office, doc, first)
    undo.clear()
    doc.setModified(False)
    dispatch(office, doc, "ooo-entrance-fly-in")
    current = settled_effects(page)
    record("1. fly-in applies to one selected rectangle", len(current) == 1
           and current[0]["id"] == "ooo-entrance-fly-in" and current[0]["targets"] == [first.getName()], current)
    record("7. command state reports the preset id", state_of(office, doc) == (True, "ooo-entrance-fly-in"),
           state_of(office, doc))
    record("application modifies the document", doc.isModified())
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    removed = settled_effects(page)
    record("2. one undo action restores the empty sequence", len(titles) == 1 and not removed, (titles, removed))
    undo.redo()
    record("redo restores the effect", settled_effects(page) == current)
    undo.clear()
    dispatch(office, doc, "ooo-exit-fade-out")
    replaced = settled_effects(page)
    record("3. fade-out replaces fly-in", len(replaced) == 1 and replaced[0]["id"] == "ooo-exit-fade-out"
           and replaced[0]["targets"] == [first.getName()], replaced)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("replacement is one undo action restoring fly-in", len(titles) == 1 and settled_effects(page) == current)
    undo.redo()
    settled_effects(page)
    select(office, doc, first, second)
    record("different selected shapes report mixed state", state_of(office, doc) == (True, ""), state_of(office, doc))
    undo.clear()
    dispatch(office, doc, "ooo-entrance-fly-in")
    paired = settled_effects(page)
    record("4. two shapes get ordered effects, second WITH_PREVIOUS", len(paired) == 2
           and [e["id"] for e in paired] == ["ooo-entrance-fly-in"] * 2
           and [e["targets"] for e in paired] == [[first.getName()], [second.getName()]]
           and [e["node_type"] for e in paired] == [ON_CLICK, WITH_PREVIOUS], paired)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("multi-shape replacement is one undo action", len(titles) == 1 and settled_effects(page) == replaced)
    undo.redo()
    settled_effects(page)
    undo.clear()
    dispatch(office, doc, "None")
    removed = settled_effects(page)
    record("5. None removes both shapes' effects", not removed and state_of(office, doc) == (True, "None"), removed)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("None is one undo action restoring both effects", len(titles) == 1 and settled_effects(page) == paired)
    undo.redo()
    settled_effects(page)
    undo.clear()
    dispatch(office, doc, "no-such-animation")
    record("unknown preset leaves effects and undo unchanged", not settled_effects(page)
           and not undo.getAllUndoActionTitles())
    select(office, doc)
    state = state_of(office, doc)
    dispatch(office, doc, "ooo-entrance-fly-in")
    record("6. empty selection disables the command and changes nothing", state is not None and not state[0]
           and not settled_effects(page) and not undo.getAllUndoActionTitles(), state)
    select(office, doc, text)
    undo.clear()
    dispatch(office, doc, "ooo-entrance-appear")
    grouped = settled_effects(page)
    record("a lone unfilled text box animates by paragraph", len(grouped) == 2
           and all(e["id"] == "ooo-entrance-appear" and e["targets"] == [text.getName()] for e in grouped)
           and sorted(p for e in grouped for p in e["paragraphs"]) == [0, 1], grouped)
    dispatch(office, doc, "ooo-exit-fade-out")
    grouped = settled_effects(page)
    record("text replacement removes all previous paragraph effects", len(grouped) == 2
           and all(e["id"] == "ooo-exit-fade-out" for e in grouped), grouped)
    dispatch(office, doc, "None")
    record("None removes paragraph targets too", not settled_effects(page))
    select(office, doc, first)
    undo.clear()
    # No sleeps between these mutations: UndoAnimation must never clone a stale timer-backed tree.
    dispatch(office, doc, "ooo-entrance-appear")
    dispatch(office, doc, "ooo-exit-fade-out")
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    immediate = effects(page)
    record("consecutive dispatches keep separate undo snapshots", len(titles) == 2 and len(immediate) == 1
           and immediate[0]["id"] == "ooo-entrance-appear", immediate)
    undo.redo()
    immediate = effects(page)
    record("immediate redo restores the replacement", len(immediate) == 1
           and immediate[0]["id"] == "ooo-exit-fade-out", immediate)
    undo.undo()
    undo.undo()
    record("immediate undo restores the original empty sequence", not effects(page))
    undo.clear()


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
    gallery = next((n for n in (tabs.walk(tab_list) if tab_list else ())
                    if (n.name or "") in GALLERY_NAMES and n.childCount > 0), None)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/slides-animation-gallery"))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=True)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    try:
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                raise RuntimeError(f"UNO port {PORT} is already in use; stop its owned instance before retrying")
        office.start()
        doc = office.load("private:factory/simpress")
        time.sleep(6)
        page, shapes = make_slide(doc)
        check_dispatcher(office, doc, page, shapes)
        check_gallery_on_screen(office, doc, page, args)
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        if office.proc is not None:
            office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
