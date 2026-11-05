# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the ribbon checks: the office on an X display, the ribbon tabs through AT-SPI, chart commands."""
import os
import subprocess
import time

import hst_gui

NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides"}


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def click(display, box):
    xdo(display, "mousemove", str(box[0] + box[2] // 2), str(box[1] + box[3] // 2), "click", "1")
    time.sleep(0.8)


def office_app(timeout=10.0):
    """The office's AT-SPI application. It can drop out of the registry for a moment (seen right after a chart dialog
    closes), so wait for it instead of returning None at once; None only when it stays away for `timeout` seconds."""
    import pyatspi
    deadline = time.time() + timeout
    while True:
        desktop = pyatspi.Registry.getDesktop(0)
        apps = (desktop.getChildAtIndex(index) for index in range(desktop.childCount))
        found = next((app for app in apps if app and "office" in (app.name or "").lower()), None)
        if found is not None or time.time() >= deadline:
            return found
        time.sleep(0.5)


SKIP = ("document text", "document spreadsheet", "document presentation", "menu bar", "status bar", "ruler", "table")


def walk(node, depth=0):
    if node is None:  # no office application on the accessibility bus: nothing to walk
        return
    yield node
    try:  # widgets come and go; the document itself is large and holds no part of the ribbon
        wanted = depth < 14 and node.getRoleName() not in SKIP
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))] if wanted else []
    except Exception:  # noqa: BLE001
        children = []
    for child in children:
        if child is not None:
            yield from walk(child, depth + 1)


def extents(node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    return box.x, box.y, box.width, box.height


def ribbon_tabs():
    """[(name, box, selected, node)] of the visible tabs in the ribbon (top row), left to right."""
    import pyatspi
    nodes = [n for n in walk(office_app()) if n.getRoleName() == "page tab" and 0 < extents(n)[2] and extents(n)[1] < 100]
    found = [(n.name, extents(n), n.getState().contains(pyatspi.STATE_SELECTED), n) for n in nodes]
    return sorted(found, key=lambda t: t[1][0])


def selected():
    return [t[0] for t in ribbon_tabs() if t[2]]


def visible_names():
    return [t[0] for t in ribbon_tabs()]


def showing(node):
    import pyatspi
    try:
        box = extents(node)
        return node.getState().contains(pyatspi.STATE_SHOWING) and box[2] > 0 and box[3] > 0
    except Exception:  # noqa: BLE001 - widgets come and go
        return False


def ribbon_nodes(roles, band=260):
    """(name, role, box, node) of the showing nodes with one of `roles` in the ribbon band of the window."""
    found = []
    for node in walk(office_app()):
        try:
            role, name = node.getRoleName(), node.name or ""
        except Exception:  # noqa: BLE001
            continue
        if role in roles and showing(node) and extents(node)[1] < band:
            found.append((name, role, extents(node), node))
    return found


def open_tab(display, name):
    tabs = {t[0]: t for t in ribbon_tabs()}
    if name not in tabs:
        return False
    click(display, tabs[name][1])
    return selected() == [name]


def geometry():
    top, doc_tabs, banner = None, None, None
    for node in walk(office_app()):
        role = node.getRoleName()
        if role == "frame" and top is None:
            top = extents(node)[1]
        elif role == "panel" and node.name == "Thẻ tài liệu":
            doc_tabs = extents(node)[1]
        elif role == "link" and banner is None and extents(node)[2] > 100:
            banner = extents(node)
    return top, doc_tabs, banner


def start(instdir, app, display, work, port):
    subprocess.run(["xprop", "-display", display, "-root", "-remove", "AT_SPI_BUS"], check=False, stderr=subprocess.DEVNULL)
    office = hst_gui.Office(instdir, work, port, display=display, extra_args=[f"--{app}"], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    time.sleep(8)
    windows = [w for w, n in hst_gui.toplevels(display, office.pid) if NAMES[app] in n]
    xdo(display, "windowmove", windows[0], "0", "0")
    xdo(display, "windowsize", windows[0], "1485", "900")
    time.sleep(4)
    return office, windows[0], windows


def check_chart_command(office, args, app, record):
    """The chart type command of the ribbon, dispatched on the document frame, opens the chart's dialog."""
    frame = office.desktop().getCurrentFrame()
    before = {w for w, _n in hst_gui.toplevels(args.display, office.pid)}
    from com.sun.star.util import URL
    url = URL()
    url.Complete = ".uno:DiagramType"
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if not record_ok(record, f"[{app}] chart command resolves on the document frame", dispatch is not None):
        return
    dispatch.dispatch(url, ())
    time.sleep(3)
    dialogs = [(w, n) for w, n in hst_gui.toplevels(args.display, office.pid) if w not in before]
    record(f"[{app}] chart command opens the chart dialog", bool(dialogs), dialogs)
    if args.shots and dialogs:
        office.screenshot(os.path.join(args.shots, f"{app}-chart-dialog.png"))
    for wid, _name in dialogs:
        hst_gui.send_close_request(wid, args.display)
    time.sleep(1.5)
    for wid, _name in hst_gui.toplevels(args.display, office.pid):
        if wid not in before:  # no window manager: a close request may not reach it
            xdo(args.display, "key", "--window", wid, "Escape")
    time.sleep(1.5)
    xdo(args.display, "key", "Escape")  # out of the chart
    time.sleep(1)


def record_ok(record, name, ok):
    record(name, ok)
    return ok
