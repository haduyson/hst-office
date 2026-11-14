#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: hovering a ribbon button shows the rich tooltip, on an INSTALLED HST Office (console session).

The tip (hst-ribbon-rich-tooltips.patch) has the name and shortcut in bold and, for a command with a sentence, the
sentence below (HelpTextWindow, RichTitle). Per button the pointer is moved onto it with the gated input
(windows_gui_input.mouse_move: only over our own window) and left there 2.5 s; the check then needs a new visible
window of soffice.bin under the pointer's row: the tip, two text lines high at least for a described command, and
not wider than MAX_WIDTH_EM times the font height (about two lines of the longest sentence). A screenshot is kept.
--dark switches ApplicationAppearance to dark first (configuration, then a restart). Usage (console session, under
C:\\hst-test\\console-lock.txt):
  "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-tooltips.py --install DIR --out DIR [--dark]
Evidence: <out>/results.json and <out>/<app>-<n>.png.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402
from windows_gui_a11y import _role, walk  # noqa: E402

# app: (factory, window title, [(button name, has a sentence)])
APPS = {"writer": ("private:factory/swriter", "HST Writer",
                   [("Dán", True), ("Căn đều", True), ("Gạch đè", True), ("Sao chép định dạng", True)]),
        "impress": ("private:factory/simpress", "HST Slides",
                    [("Dán đặc biệt", True), ("Thụt đầu dòng treo", True), ("Chỉ số trên", True),
                     ("Xoay vòng kiểu chữ", True)])}
MAX_WIDTH_PX = 900  # at 100 %; scaled by the DPI
user32 = ctypes.windll.user32


def visible_windows(pid):
    """{hwnd: (left, top, right, bottom)} of the visible top-level windows of process pid."""
    found = {}
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def each(hwnd, _param):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            rect = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found[hwnd] = (rect.left, rect.top, rect.right, rect.bottom)
        return True

    user32.EnumWindows(proc(each), 0)
    return found


def buttons(office, names):
    """{name: (x, y, w, h)} of the visible ribbon buttons with these accessible names."""
    roles, boxes = {_role("PUSH_BUTTON"), _role("TOGGLE_BUTTON")}, {}
    for window in office.top_windows():
        for context, _depth in walk(window, limit=14):
            try:
                role, name = context.getAccessibleRole(), context.getAccessibleName()
                where, size = context.getLocationOnScreen(), context.getSize()
            except Exception:  # noqa: BLE001 - widgets come and go
                continue
            if role in roles and name in names and name not in boxes and size.Width > 0 and where.Y < 300:
                boxes[name] = (where.X, where.Y, size.Width, size.Height)
    return boxes


def set_dark(office):
    import uno
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    arg = PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Common/Misc")
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
                                                  uno.Any("[]com.sun.star.beans.PropertyValue", (arg,)))
    access.setPropertyValue("ApplicationAppearance", 2)
    access.commitChanges()


def check_app(office, res, args, app):
    factory, title, wanted = APPS[app]
    office.load(factory)
    time.sleep(6)
    wg.dismiss_startup(office, os.path.join(args.out, f"{app}-startup.png"), timeout=8, settle=2)
    office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
    time.sleep(3)
    window = wg.find_window(lambda name: title in name, timeout=30)
    boxes = buttons(office, {name for name, _ in wanted})
    if not res(f"[{app}] ribbon buttons found", bool(window) and len(boxes) == len(wanted), sorted(boxes)):
        return
    wg.foreground(window[0])
    pid = office.bin_pids_of_profile()[0]
    scale = user32.GetDpiForWindow(window[0]) / 96.0 if hasattr(user32, "GetDpiForWindow") else 1.0
    for n, (name, described) in enumerate(wanted):
        x, y, w, h = boxes[name]
        wg.mouse_move(x + w // 2, y + h + 40)  # off the button first, so each hover starts a new tip
        time.sleep(1.0)
        before = visible_windows(pid)
        wg.mouse_move(x + w // 2, y + h // 2)
        time.sleep(2.5)
        tips = {k: r for k, r in visible_windows(pid).items() if k not in before and r[3] - r[1] < 200}
        wg.screenshot(os.path.join(args.out, f"{app}-{n}.png"))
        rect = next(iter(tips.values()), None)
        width = rect[2] - rect[0] if rect else 0
        height = rect[3] - rect[1] if rect else 0
        res(f"[{app}] '{name}': tip shown, {'two lines or more' if described else 'one line'}, width sensible",
            rect is not None and height >= (30 * scale if described else 10) and width <= MAX_WIDTH_PX * scale,
            {"rect": rect, "scale": scale})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2381)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--apps", default="writer,impress")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        if args.dark:
            set_dark(office)
            office.stop()
            office.start(fresh=False)
            time.sleep(15)
            office.ctx = office._connect()
            wg.dismiss_startup(office, os.path.join(args.out, "startup-dark.png"))
        for app in args.apps.split(","):
            try:
                check_app(office, res, args, app)
            except Exception as error:  # noqa: BLE001 - one app's failure must not hide the others
                res(f"[{app}] ran", False, repr(error))
    finally:
        office.stop()
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
