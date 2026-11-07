# SPDX-License-Identifier: AGPL-3.0-only
"""UNO helpers of check-slides-animation-gallery.py: the evidence rows, the command and its state,
shape selection, and the main animation sequence read from the slide's animation tree."""
import time

COMMAND = ".uno:HstApplyAnimation"
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


def user_data(node):
    """The node's user data; the root reached through XAnimationNodeSupplier may be a bare proxy."""
    try:
        return {p.Name: p.Value for p in node.UserData}
    except AttributeError:
        return {}


def effects(page):
    """One record per preset container, only below MAIN_SEQUENCE (never trigger sequences)."""
    from com.sun.star.presentation.EffectNodeType import MAIN_SEQUENCE
    root = page.getAnimationNode()
    sequence = next((node for node in descendants(root)
                     if user_data(node).get("node-type") == MAIN_SEQUENCE), None)
    result = []
    if sequence is None:
        return result
    for node in descendants(sequence):
        data = user_data(node)
        if "preset-id" not in data:
            continue
        targets, paragraphs = set(), set()
        for child in descendants(node):
            try:
                target = child.Target  # XAnimate; containers have no target
            except AttributeError:
                continue
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
