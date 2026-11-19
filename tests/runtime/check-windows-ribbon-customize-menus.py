#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the entries of "Tùy chỉnh ribbon" and the history rule of the "Sử dụng gần đây" tab, in an INSTALLED (or
administrative image of) HST Office. Companion of check-windows-ribbon-customize.py.

No mouse: the ribbon is reached through the accessibility tree over UNO (tab selection, focus on a command), the
menus are opened with Shift+F10 and walked with the keyboard (SendInput, guarded: only our own windows get keys).
Per app (HST Writer, HST Sheets by default):
  - Shift+F10 on the tab row opens a menu whose item opens the "Tùy chỉnh ribbon" dialog; it lists the ribbon's
    tabs and closes with Escape;
  - Shift+F10 on a command (Đậm) opens the menu with the quick access entry and "Tùy chỉnh ribbon…", which opens
    the dialog too;
  - switching the recently used tab off and on keeps the history: the used commands are back on the tab, also after
    a restart of the office with the tab off (the history in the profile is kept).
Evidence: <out>/results.json and PrintWindow shots.
Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-customize-menus.py --install DIR --out DIR
"""
import argparse
import importlib.util
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402

_spec = importlib.util.spec_from_file_location("ribbon_win", os.path.join(HERE, "check-windows-ribbon-customize.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
DIALOG = "Tùy chỉnh ribbon"
SHIFT, F10 = 0x10, 0x79
APPS = {"writer": base.APPS["writer"], "calc": base.APPS["calc"]}


def dialog_window(office):
    for window in office.top_windows():
        try:
            context = base.accessible(window).getAccessibleContext()
            if window.isVisible() and context.getAccessibleName().startswith(DIALOG):
                return window
        except Exception:  # noqa: BLE001 - a window going away
            continue
    return None


def menu_items(office):
    """Names of the menu items shown in the office's popup menus (read through accessibility)."""
    names = []
    for window in office.top_windows():
        try:
            for context, _depth in wg.walk(base.accessible(window)):
                if context.getAccessibleRole() == base.role("MENU_ITEM"):
                    names.append(context.getAccessibleName())
        except Exception:  # noqa: BLE001 - a window going away
            continue
    return names


def focus_tab_row(window):
    """Keyboard focus on the ribbon's tab row (the page tab list), through its accessible component."""
    for context, _depth in wg.walk(window):
        try:
            if context.getAccessibleRole() == base.role("PAGE_TAB_LIST"):
                context.grabFocus()
                time.sleep(0.5)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def open_menu_and_pick(office, hwnd, downs, shots, name):
    """Shift+F10 on the focused ribbon part, `downs` x Down, Enter: True when the customize dialog opened (then closed
    with Escape and checked to list the ribbon's tabs)."""
    wg.chord(SHIFT, F10, target=hwnd)
    time.sleep(1.5)
    items = menu_items(office)
    print(f"{name}: menu items {items}", flush=True)
    wg.load_check("check-windows-quick-access").window_shot(hwnd, os.path.join(shots, name + "-menu.bmp"))
    for _ in range(downs):
        wg.keys("down", target=hwnd, front=False)
    wg.keys("enter", target=hwnd, front=False)
    deadline, window = time.time() + 15, None
    while time.time() < deadline and window is None:
        window = dialog_window(office)
        time.sleep(0.5)
    if window is None:
        wg.keys("escape", target=hwnd, front=False)
        return False, items
    time.sleep(1.5)
    listed = wg.texts(base.accessible(window), limit=300)
    dialog = wg.dialog_hwnd(window)
    if dialog:
        wg.load_check("check-windows-quick-access").window_shot(dialog, os.path.join(shots, name + "-dialog.bmp"))
    wg.keys("escape", target=dialog or hwnd)
    time.sleep(2)
    return dialog_window(office) is None, listed


def focus_command(window, label):
    """Give keyboard focus to the ribbon command `label` through its accessible component."""
    for context, _depth in wg.walk(window):
        try:
            if context.getAccessibleName() == label and context.getAccessibleRole() in (
                    base.role("PUSH_BUTTON"), base.role("TOGGLE_BUTTON")):
                context.grabFocus()
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def recent_shows(window, label):
    base.select_tab(window, base.HOME)
    base.select_tab(window, base.RECENT)
    time.sleep(2)
    return label in base.shown_texts(window)


def check_app(office, app, out, res):
    from com.sun.star.beans import NamedValue
    doc = office.load(APPS[app][0])
    time.sleep(6)
    wg.dismiss_startup(office, os.path.join(out, f"{app}-startup.png"), timeout=8, settle=2)
    found = wg.find_window(lambda title: APPS[app][1] in title, timeout=30)
    window = base.window_of(doc)
    if not res(f"[{app}] window found", bool(found) and window is not None, found):
        return
    hwnd = found[0]
    base.select_tab(window, base.HOME)
    focused = focus_tab_row(base.window_of(doc))
    ok, listed = open_menu_and_pick(office, hwnd, 0, out, f"{app}-tabrow")
    res(f"[{app}] tab row focused", focused)
    res(f"[{app}] tab row: Shift+F10 menu opens {DIALOG}, Escape closes it", ok, listed[:30])
    res(f"[{app}] the dialog lists the ribbon's tabs", base.HOME in listed, listed[:30])
    focused = focus_command(base.window_of(doc), "Đậm")
    ok, _listed = open_menu_and_pick(office, hwnd, 1, out, f"{app}-command")
    res(f"[{app}] command Đậm: Shift+F10 menu, second entry opens {DIALOG}", focused and ok, focused)
    helper = office.service("com.sun.star.frame.DispatchHelper")
    frame = doc.getCurrentController().getFrame()
    for command in base.USED:
        helper.executeDispatch(frame, command, "", 0, ())
    job = office.service("vn.hasontech.hst.RibbonCustomization")
    job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", False)))
    time.sleep(5)
    res(f"[{app}] tab off", base.RECENT not in [n for n, _c in base.tabs(base.window_of(doc))])
    job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", True)))
    time.sleep(5)
    res(f"[{app}] off then on: the used commands are still on the tab", recent_shows(base.window_of(doc), "Đậm"))
    job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", False)))
    doc.setModified(False)
    doc.close(True)
    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2381)
    parser.add_argument("--apps", default="writer,calc")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(15)
        office.ctx = office._connect()  # the first start of a new image restarts itself after the extension sync
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        for app in args.apps.split(","):
            try:
                check_app(office, app, args.out, res)
            except Exception as error:  # noqa: BLE001 - the next app still runs
                res(f"[{app}] run", False, repr(error))
        office.stop()  # the tab is off now: the history must survive the restart
        office.start(fresh=False)
        time.sleep(10)
        office.ctx = office._connect()
        from com.sun.star.beans import NamedValue
        job = office.service("vn.hasontech.hst.RibbonCustomization")
        res("after a restart the tab is still off", job.execute((NamedValue("Action", "getRecentEnabled"),)) is False)
        job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", True)))
        doc = office.load(APPS["writer"][0])
        time.sleep(8)
        wg.dismiss_startup(office, os.path.join(args.out, "restart-startup.png"), timeout=8, settle=2)
        res("after a restart with the tab off, switched on: the history is back", recent_shows(base.window_of(doc), "Đậm"))
    finally:
        office.stop()
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
