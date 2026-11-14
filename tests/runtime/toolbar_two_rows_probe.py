# SPDX-License-Identifier: AGPL-3.0-only
"""Measure and judge the toolbars beside the window banner over UNO (Linux and Windows alike).

hst-toolbar-two-rows.patch: in the toolbar user interfaces with one docked toolbar (Single toolbar, Sidebar, and
Draw's Standard one) that toolbar takes two rows of about equal width beside the banner; the toolbar block is
centred vertically in the top docking area, left of the banner. Other toolbar layouts keep one row per toolbar.
Everything is read through the accessibility API of the toolbar windows (no AT-SPI needed), in px relative to the
window's container.
"""

# the toolbar user interfaces of each app (officecfg ToolbarMode.xcu); Draw and Slides have no Sidebar one
MODES = {"writer": ("Default", "Single", "Sidebar"), "calc": ("Default", "Single", "Sidebar"),
         "impress": ("Default", "Single"), "draw": ("Default",)}
# the user interfaces whose top docking area holds one toolbar (the others have two rows of toolbars already)
LONE = {("writer", "Single"), ("writer", "Sidebar"), ("calc", "Single"), ("calc", "Sidebar"), ("impress", "Single"),
        ("draw", "Default")}
CENTRE_TOLERANCE = 2  # px between the space above and below the toolbar block
EDGE_TOLERANCE = 1  # px between the left edges of the two rows


def _const(group, name):
    import uno
    return uno.getConstantByName(f"com.sun.star.accessibility.{group}.{name}")


def _showing(context):
    try:
        return bool(context.getAccessibleStateSet() & _const("AccessibleStateType", "SHOWING"))
    except Exception:  # noqa: BLE001 - a disposed node
        return False


def _box(context, origin):
    loc, size = context.getLocationOnScreen(), context.getSize()
    return [loc.X - origin.X, loc.Y - origin.Y, size.Width, size.Height]


def measure(frame):
    """{"bars": [{"url", "box", "items": [[x, y, w, h] relative to the toolbar]}], "area": box of the top docking
    area, "banner": box or None} for the docked toolbars of the top docking area of `frame`."""
    container = frame.getContainerWindow().getAccessibleContext()
    origin = container.getLocationOnScreen()
    layout = frame.LayoutManager
    separator = _const("AccessibleRole", "SEPARATOR")
    docked = []  # (docking area context, its box, bar)
    for element in layout.getElements():
        url = element.ResourceURL
        if not url.startswith("private:resource/toolbar/") or not layout.isElementVisible(url) \
                or layout.isElementFloating(url):
            continue
        context = element.getRealInterface().getAccessibleContext()
        if not _showing(context):
            continue
        items = []
        for index in range(context.getAccessibleChildCount()):
            child = context.getAccessibleChild(index).getAccessibleContext()
            if _showing(child) and child.getAccessibleRole() != separator:
                b = child.getBounds()
                if b.Width > 0 and b.Height > 0:
                    items.append([b.X, b.Y, b.Width, b.Height])
        parent = context.getAccessibleParent().getAccessibleContext()
        docked.append((parent, _box(parent, origin), {"url": url, "box": _box(context, origin), "items": items}))
    result = {"bars": [], "area": None, "banner": None}
    if not docked:
        return result
    # the top docking area is the highest one that is wider than high
    top = min((d for d in docked if d[1][2] > d[1][3]), key=lambda d: d[1][1], default=None)
    if top is None:
        return result
    result["area"] = top[1]
    result["bars"] = [bar for _parent, box, bar in docked if box == top[1]]
    for index in range(top[0].getAccessibleChildCount()):
        child = top[0].getAccessibleChild(index).getAccessibleContext()
        if " — " in (child.getAccessibleName() or "") and _showing(child):
            result["banner"] = _box(child, origin)
    return result


def rows(items):
    """The items grouped into rows (top to bottom), each [left, right, top, bottom, widest item]."""
    out = []
    for x, y, w, h in sorted(items, key=lambda i: (i[1], i[0])):
        if out and abs(y + h / 2 - (out[-1][2] + out[-1][3]) / 2) < h / 2:
            row = out[-1]
            row[0], row[1], row[3], row[4] = min(row[0], x), max(row[1], x + w), max(row[3], y + h), max(row[4], w)
        else:
            out.append([x, x + w, y, y + h, w])
    return out


def judge(app, mode, data):
    """(ok, detail) for one measurement of `app` in the toolbar user interface `mode`."""
    bars = data["bars"]
    if not bars:
        return False, "no docked toolbar in the top docking area"
    if (app, mode) not in LONE:
        multi = [b["url"].rsplit("/", 1)[-1] for b in bars if len(rows(b["items"])) != 1]
        return (not multi), (f"toolbars with more than one row: {multi}" if multi else
                             f"{len(bars)} toolbars, one row each")
    if len(bars) != 1:
        return False, f"{len(bars)} toolbars in the top docking area, one expected"
    bar = bars[0]
    found = rows(bar["items"])
    if len(found) != 2:
        return False, f"{bar['url']}: {len(found)} rows of buttons, two expected"
    (l1, r1, t1, b1, w1), (l2, r2, t2, b2, w2) = found
    button = max(w1, w2)
    if abs(l1 - l2) > EDGE_TOLERANCE:
        return False, f"rows start {abs(l1 - l2)} px apart"
    if abs((r1 - l1) - (r2 - l2)) > button + 1:
        return False, f"rows {r1 - l1} and {r2 - l2} px wide, more than one button ({button} px) apart"
    if t2 < b1 - 1:
        return False, "the rows overlap"
    x, y, w, h = bar["box"]
    if max(r1, r2) > w + 1 or max(b1, b2) > h + 1:
        return False, f"buttons outside the toolbar {bar['box']}"
    ax, ay, aw, ah = data["area"]
    above, below = y - ay, ay + ah - (y + h)
    if abs(above - below) > CENTRE_TOLERANCE:
        return False, f"toolbar block {above} px below the strip top, {below} px above its bottom"
    banner = data["banner"]
    if banner is None:
        return False, "no banner in the top docking area"
    if banner[0] < x + w:
        return False, f"banner {banner} overlaps the toolbar {bar['box']}"
    return True, f"rows {r1 - l1}/{r2 - l2} px (button {button}), block {h} px in a {ah} px strip, banner {banner}"
