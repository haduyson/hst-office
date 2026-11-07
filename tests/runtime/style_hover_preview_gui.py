# SPDX-License-Identifier: AGPL-3.0-only
"""Office helpers of check-style-hover-preview.py: window placement, the document's state, the gallery item under
the pointer, hovering, and the flat ODF body and direct paragraph values compared before and after a hover."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def state(doc):
    """(paragraph style at the cursor, modified, undo titles, redo titles, tracked changes)."""
    cursor = doc.getCurrentController().getViewCursor()
    undo = doc.getUndoManager()
    return (cursor.getPropertyValue("ParaStyleName"), doc.isModified(), tuple(undo.getAllUndoActionTitles()),
            tuple(undo.getAllRedoActionTitles()), sum(1 for _ in iter_enum(doc.getRedlines().createEnumeration())))


def iter_enum(enumeration):
    while enumeration.hasMoreElements():
        yield enumeration.nextElement()


def window_of(office, title_part):
    for wid, name in hst_gui.toplevels(office.display, office.pid):
        if title_part in name:
            return wid
    return None


def gallery_item(office, wid, out, name):
    """Screen point of the gallery's second style (the first is the current style)."""
    xdo(office.display, "windowmove", wid, "0", "0")
    xdo(office.display, "windowsize", wid, "2400", "900")  # room for two style tiles beside the 1.0.0 content and Tools
    time.sleep(3)
    shot = office.screenshot(os.path.join(out, name))
    from PIL import Image
    img = Image.open(shot).convert("RGB")
    # the current style's tile has the blue selection box (a contiguous blue edge of 80+ px; a
    # checked button's border is much shorter); the next style sits right of it
    edges = []
    for y in range(45, 170):
        run = 0
        for x in range(150, 2000):
            r, g, b = img.getpixel((x, y))
            run = run + 1 if (b > 150 and r < 90 and 70 < g < 170) else 0
            if run == 80:
                edges.append((x - 79, y))
    if len(edges) < 2:
        return None
    left, top = min(edges)
    bottom = max(y for _x, y in edges)

    def blue(x, y):
        r, g, b = img.getpixel((x, y))
        return b > 150 and r < 90 and 70 < g < 170

    right = left
    while right + 1 < img.width and blue(right + 1, top):
        right += 1
    return right + (right - left) // 2 + 4, (top + bottom) // 2


def hover(office, point, rest=1.2):
    xdo(office.display, "mousemove", str(point[0]), str(point[1]))
    time.sleep(rest)


def leave(office):
    xdo(office.display, "mousemove", "700", "600")  # the document area
    time.sleep(0.8)


FLAT = "OpenDocument Text Flat XML"
DIRECT = {"ParaAdjust": 3, "ParaLeftMargin": 1000, "ParaFirstLineIndent": -500, "ParaTopMargin": 300,
          "ParaBottomMargin": 400, "ParaBackColor": 0xFFF2CC, "CharWeight": 150.0}


def flat_body(doc, path):
    """The automatic styles and the body of the document as flat ODF (what the paragraph is made of)."""
    doc.storeToURL("file://" + path, (prop("FilterName", FLAT),))
    with open(path, encoding="utf-8") as handle:
        xml = handle.read()
    start = xml.index("<office:automatic-styles")
    return xml[start:xml.index("</office:body>")]


def direct_values(paragraph):
    names = [p.Name for p in paragraph.getPropertySetInfo().getProperties()]
    values = {}
    for name in names:
        try:
            if paragraph.getPropertyState(name).value == "DIRECT_VALUE":
                value = repr(paragraph.getPropertyValue(name))
                # object references (NumberingRules, grab bags) differ by address only; the flat
                # ODF comparison covers what they hold
                if "pyuno object" not in value:
                    values[name] = value
        except Exception:  # noqa: BLE001 - properties without a state or value
            pass
    return values
