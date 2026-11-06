# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-vietnamese-utilities.py: dispatch a command that opens a modal dialog, find the dialog window,
send keys to it, take screenshots, open the classic HST menu through AT-SPI."""
import os
import re
import subprocess
import threading
import time

import hst_gui

ROWS = []


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=20)


def wait_window(office, pattern, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for wid, name in hst_gui.toplevels(office.display, office.pid):
            if re.search(pattern, name):
                return wid
        time.sleep(0.5)
    return None


def window_gone(office, wid, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if wid not in [w for w, _ in hst_gui.toplevels(office.display, office.pid)]:
            return True
        time.sleep(0.5)
    return False


def focus(display, wid, x=4, y=4):
    """Give the window the keyboard focus: no window manager runs on the test display, so click inside it."""
    xdo(display, "windowraise", wid)
    xdo(display, "mousemove", "--window", wid, str(x), str(y), "click", "1")
    xdo(display, "windowfocus", "--sync", wid)
    time.sleep(0.4)


def keys(display, wid, *names):
    """Focus the window, then press the keys one by one."""
    focus(display, wid)
    for name in names:
        xdo(display, "key", name)
        time.sleep(0.25)


def type_text(display, wid, text):
    xdo(display, "type", "--delay", "60", text)


def background_dispatch(office, frame, url, args=()):
    """Run the dispatch in a thread (a modal dialog blocks the call); returns the thread."""
    def run():
        try:
            office.dispatch(frame, url, args)
        except Exception as error:  # noqa: BLE001 - reported by the caller's checks
            print("dispatch %s: %r" % (url, error))
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def crop(full, wid, display, target):
    """Save the part of the screenshot `full` covered by window `wid`."""
    from PIL import Image
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    x, y = (int(re.search(name + r":\s+(-?\d+)", info).group(1)) for name in ("Absolute upper-left X", "Absolute upper-left Y"))
    w, h = (int(re.search(name + r":\s+(\d+)", info).group(1)) for name in ("Width", "Height"))
    Image.open(full).crop((max(x, 0), max(y, 0), x + w, y + h)).save(target)


def dialog_shot(office, wid, directory, name):
    os.makedirs(directory, exist_ok=True)
    full = os.path.join(directory, name + "-full.png")
    time.sleep(1.0)
    office.raise_windows()
    xdo(office.display, "windowraise", wid)
    time.sleep(0.5)
    hst_gui.screenshot(full, office.display)
    target = os.path.join(directory, name + ".png")
    try:
        crop(full, wid, office.display, target)
        os.remove(full)
    except Exception as error:  # noqa: BLE001 - keep the full screenshot then
        print("crop skipped:", error)
        target = full
    return target


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            return app
    return None


def find(node, role, name, depth=0, limit=14):
    """First accessible with the role and name below `node` (document content is skipped)."""
    try:
        if node.getRoleName() == role and node.name == name:
            return node
        if depth >= limit or node.getRoleName().startswith("document") or node.childCount > 500:
            return None
        for index in range(node.childCount):
            found = find(node.getChildAtIndex(index), role, name, depth + 1, limit)
            if found is not None:
                return found
    except Exception:  # noqa: BLE001 - widgets come and go
        pass
    return None


def children_names(menu):
    return [menu.getChildAtIndex(i).name for i in range(menu.childCount)]


def click(display, node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    xdo(display, "mousemove", str(box.x + box.width // 2), str(box.y + box.height // 2), "click", "1")
    time.sleep(1.2)


def hover(display, node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    xdo(display, "mousemove", str(box.x + 20), str(box.y + box.height // 2))
    time.sleep(1.5)


def host_for(office, doc, said):
    from hst_office import actions
    from hst_office.data_files import load_locale

    class Host(actions.Host):
        def say(self, text, error=False):
            said.append(text)
    return Host(office.ctx, doc.getCurrentController().getFrame(), load_locale("vi"))
