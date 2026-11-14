# SPDX-License-Identifier: AGPL-3.0-only
"""Measure and judge the toolbars beside the window banner (Linux AT-SPI, Windows UNO accessibility).

hst-toolbar-two-rows.patch: in the toolbar user interfaces with one docked toolbar (Single toolbar, Sidebar, and
Draw's Standard one) that toolbar takes two rows of about equal width beside the banner, the block centred
vertically on the banner; other toolbar layouts keep one row per toolbar. A snapshot is
{"bars": [{"box": [x, y, w, h], "items": [[x, y, w, h], ...]}], "banners": [[x, y, w, h], ...]} in screen px,
as a screen reader finds the tool bars, their showing items (separators aside) and the banner link.
"""

# the toolbar user interfaces of each app (officecfg ToolbarMode.xcu); Draw and Slides have no Sidebar one
MODES = {"writer": ("Default", "Single", "Sidebar"), "calc": ("Default", "Single", "Sidebar"),
         "impress": ("Default", "Single"), "draw": ("Default",)}
# the user interfaces whose top docking area holds one toolbar (the others have two rows of toolbars already)
LONE = {("writer", "Single"), ("writer", "Sidebar"), ("calc", "Single"), ("calc", "Sidebar"), ("impress", "Single"),
        ("draw", "Default")}
CENTRE_TOLERANCE = 2  # px between the centres of the toolbar block and the banner
EDGE_TOLERANCE = 1  # px between the left edges of the two rows
SKIP = ("document text", "document spreadsheet", "document presentation", "document frame", "menu bar",
        "status bar", "ruler", "tree", "table", "list")


def snapshot_atspi():
    """Linux: the snapshot of every office application on the AT-SPI bus."""
    import pyatspi

    def box(node):
        ext = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        return [ext.x, ext.y, ext.width, ext.height]

    def showing(node):
        return node.getState().contains(pyatspi.STATE_SHOWING)

    out = {"bars": [], "banners": []}

    def walk(node, depth):
        try:
            role = node.getRoleName()
            if role == "link" and " — " in (node.name or "") and showing(node):
                out["banners"].append(box(node))
            if role == "tool bar" and showing(node):
                kids = [node.getChildAtIndex(i) for i in range(node.childCount)]
                out["bars"].append({"box": box(node), "items": [box(k) for k in kids if showing(k)
                                                                and k.getRoleName() != "separator"]})
                return
            if depth < 16 and role not in SKIP:
                for index in range(node.childCount):
                    walk(node.getChildAtIndex(index), depth + 1)
        except Exception:  # noqa: BLE001 - widgets come and go
            pass

    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            walk(app, 0)
    return out


def snapshot_uno(top_windows):
    """Windows: the snapshot of the toolkit top windows over UNO accessibility (windows_gui.walk)."""
    import uno
    import windows_gui as wg

    def role(name):
        return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)

    def box(context):
        loc, size = context.getLocationOnScreen(), context.getSize()
        return [loc.X, loc.Y, size.Width, size.Height]

    def accessible(window):  # a toolkit top window does not list XAccessible to pyuno (r1auto/access.py)
        return window if hasattr(window, "getAccessibleContext") else window.queryInterface(
            uno.getTypeByName("com.sun.star.accessibility.XAccessible"))

    out = {"bars": [], "banners": []}
    for window in top_windows:
        root = accessible(window)
        out["roots"] = out.get("roots", 0) + (root is not None)  # evidence when nothing is found
        if root is None:
            continue
        for context, _depth in wg.walk(root, limit=16):
            out["nodes"] = out.get("nodes", 0) + 1
            try:
                if not wg.showing(context):
                    continue
                if context.getAccessibleRole() == role("TOOL_BAR"):
                    kids = [context.getAccessibleChild(i).getAccessibleContext()
                            for i in range(context.getAccessibleChildCount())]
                    out["bars"].append({"box": box(context), "items": [
                        box(k) for k in kids if wg.showing(k) and k.getAccessibleRole() != role("SEPARATOR")]})
                elif " — " in (context.getAccessibleName() or ""):
                    out["banners"].append(box(context))
            except Exception:  # noqa: BLE001 - a disposed node
                continue
    return out


def strip(snapshot):
    """(banner box, the tool bars beside it in the banner strip) of a snapshot, or (None, [])."""
    banners = [b for b in snapshot["banners"] if b[2] > 0 and b[3] > 0]
    if len(banners) != 1:
        return None, []
    bx, by, bw, bh = banners[0]
    bars = [bar for bar in snapshot["bars"] if len(bar["items"]) >= 2 and bar["box"][0] < bx
            and by <= bar["box"][1] + bar["box"][3] / 2 <= by + bh]
    return banners[0], bars


def typical(values):
    """The most common value (the size of a plain button), 0 without values."""
    return max(sorted(set(values)), key=values.count) if values else 0


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


def judge(app, mode, snapshot):
    """(ok, detail) for one snapshot of `app` in the toolbar user interface `mode`."""
    banner, bars = strip(snapshot)
    if banner is None:
        return False, f"{len(snapshot['banners'])} banners showing, one expected"
    if not bars:
        return False, "no toolbar beside the banner"
    if (app, mode) not in LONE:
        multi = [bar["box"] for bar in bars if len(rows(bar["items"])) != 1]
        return (not multi), (f"toolbars with more than one row: {multi}" if multi else
                             f"{len(bars)} toolbars beside the banner, one row each")
    if len(bars) != 1:
        return False, f"{len(bars)} toolbars beside the banner, one expected"
    bar = bars[0]
    found = rows(bar["items"])
    if len(found) != 2:
        return False, f"{len(found)} rows of buttons, two expected"
    (l1, r1, t1, b1, _w1), (l2, r2, t2, b2, _w2) = found
    common = typical([i[2] for i in bar["items"]])
    button = max(i[2] for i in bar["items"] if i[2] <= common * 3 // 2)  # one button: the widest plain one
    line = typical([i[3] for i in bar["items"]])  # item windows taller than a button stick out, as in one row
    plain = [i for i in bar["items"] if i[3] <= line]
    t1, b2 = min(i[1] for i in plain), max(i[1] + i[3] for i in plain)
    if abs(l1 - l2) > EDGE_TOLERANCE:
        return False, f"rows start {abs(l1 - l2)} px apart"
    if abs((r1 - l1) - (r2 - l2)) > button + 1:
        return False, f"rows {r1 - l1} and {r2 - l2} px wide, more than one button ({button} px) apart"
    if t2 < b1 - 1:
        return False, "the rows overlap"
    x, y, w, h = bar["box"]
    if l1 < x - 1 or max(r1, r2) > x + w + 1 or t1 < y - 1 or b2 > y + h + 1:
        return False, f"buttons outside the toolbar {bar['box']}"
    if abs((t1 + b2) / 2 - (banner[1] + banner[3] / 2)) > CENTRE_TOLERANCE:
        return False, f"buttons {t1}..{b2} not centred on the banner {banner}"
    if banner[0] < x + w:
        return False, f"banner {banner} overlaps the toolbar {bar['box']}"
    return True, f"rows {r1 - l1}/{r2 - l2} px (button {button}), buttons {t1}..{b2}, banner {banner}"
