#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Windows: screenshots and accessible boxes of the ribbon's banner, tab titles and tab row, for check-banner-fit.

Per theme (light, then dark: the office's own appearance setting, set in the profile and the office started again),
Writer, Sheets and Slides run maximised on an INSTALLED HST Office. On every shown ribbon tab but "Tệp tin" (each
opened by a click on its title) the screen is saved as <out>\\shots\\<app>-<label>-<theme>-<index>.png and the
accessible boxes (screen pixels) of the window's client area, the tab titles, the visible banners ("<name> — <tagline>")
and the other widgets of the tab row are written to <out>\\collected-<label>.json. --label names the run: the real
display scaling (100 or 125), set before with tests/runtime/r1auto/scaling.py; the run fails when the scaling it
finds is not the label. Judge the result on Linux with check-windows-banner-fit.py. Usage (console session, under
C:\\hst-test\\console-lock.txt, with an environment free of another image's URE_BOOTSTRAP/UNO_PATH/PYTHON*):
  "<install>\\program\\python.exe" tests/runtime/collect-windows-banner-fit.py --install DIR --out DIR --label 125
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402

APPS = {"writer": ("private:factory/swriter", "HST Writer"), "calc": ("private:factory/scalc", "HST Sheets"),
        "impress": ("private:factory/simpress", "HST Slides")}
SKIP_TABS = ("Tệp tin",)  # opens the File panel
ROW_ROLES = ("PUSH_BUTTON", "TOGGLE_BUTTON", "BUTTON_DROPDOWN", "BUTTON_MENU", "TEXT", "COMBO_BOX", "TOOL_BAR")
BAND = 400  # screen px from the window's top that hold the title, the tab row and the ribbon at 125 %


def display_scale():
    """The primary monitor's real scaling in percent (what Windows applies, not a font setting)."""
    shcore, user32 = ctypes.windll.shcore, ctypes.windll.user32
    user32.MonitorFromPoint.argtypes, user32.MonitorFromPoint.restype = [wintypes.POINT, wintypes.DWORD], wintypes.HANDLE
    value = ctypes.c_int()
    if shcore.GetScaleFactorForMonitor(user32.MonitorFromPoint(wintypes.POINT(0, 0), 1), ctypes.byref(value)):
        raise RuntimeError("GetScaleFactorForMonitor failed")
    return value.value


def client_box(hwnd):
    """(x, y, w, h) of the window's client area in screen pixels."""
    rect = wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    left, top = wg.client_origin(hwnd)
    return [left, top, rect.right - rect.left, rect.bottom - rect.top]


def _role(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)


def _near_top(context, depth=0):
    """Yield the showing contexts whose box starts above BAND; a subtree below it (the document) is not walked."""
    try:
        if not wg.showing(context) or context.getLocationOnScreen().Y > BAND:
            return
        count = min(context.getAccessibleChildCount(), 400)
    except Exception:  # noqa: BLE001 - widgets come and go
        return
    yield context
    if depth >= 20:
        return
    for index in range(count):
        try:
            child = context.getAccessibleChild(index)
            child = child.getAccessibleContext() if child is not None else None
        except Exception:  # noqa: BLE001
            continue
        if child is not None:
            yield from _near_top(child, depth + 1)


def boxes(office):
    """{"tabs": [[name, box]], "banners": [box], "widgets": [box]} of the showing nodes near the window's top."""
    page_tab, row_roles = _role("PAGE_TAB"), {_role(r) for r in ROW_ROLES}
    found = {"tabs": [], "banners": [], "widgets": []}
    window = office.desktop.getCurrentFrame().getContainerWindow()
    try:
        root = window.getAccessibleContext()
    except AttributeError:  # toolkit windows hand their XAccessible out as a property (VCLXWindow)
        root = window.getProperty("XAccessible").getAccessibleContext()
    for context in _near_top(root):
        try:
            role, name = context.getAccessibleRole(), context.getAccessibleName() or ""
            where, size = context.getLocationOnScreen(), context.getSize()
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
        box = [where.X, where.Y, size.Width, size.Height]
        if size.Width <= 0 or size.Height <= 0:
            continue
        if role == page_tab:
            found["tabs"].append([name, box])
        elif " — " in name and 40 <= size.Height <= 200:  # the window's own node is "<document> — <app>"
            found["banners"].append(box)
        elif role in row_roles:
            found["widgets"].append(box)
    found["tabs"].sort(key=lambda tab: tab[1][0])
    return found


def set_theme(office, theme):
    from com.sun.star.beans import PropertyValue
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    arg = PropertyValue(Name="nodepath", Value="/org.openoffice.Office.Common/Appearance")
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
    access.setPropertyValue("ApplicationAppearance", {"light": 1, "dark": 2}[theme])
    access.commitChanges()


def collect_app(office, app, theme, args, res):
    factory, title = APPS[app]
    case, shots = f"{app}-{args.label}-{theme}", []
    office.load(factory)
    time.sleep(6)
    wg.dismiss_startup(office, os.path.join(args.out, f"{case}-startup.png"), timeout=8, settle=2)
    office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
    time.sleep(4)
    window = wg.find_window(lambda text: title in text, timeout=30)
    if not res(f"[{case}] window", bool(window)):
        return None
    wg.foreground(window[0])
    time.sleep(1)
    tabs = [(name, box) for name, box in boxes(office)["tabs"] if name not in SKIP_TABS]
    res(f"[{case}] ribbon tabs found", len(tabs) >= 4, [name for name, _box in tabs])
    for index, (name, box) in enumerate(tabs):  # the titles stay where they are when another tab opens
        wg.click(box[0] + box[2] // 2, box[1] + box[3] // 2)
        time.sleep(2.5)
        shot = os.path.join(args.out, "shots", f"{case}-{index:02d}.png")
        wg.screenshot(shot, cursor=False)
        shots.append(dict(tab=name, shot=os.path.basename(shot), **boxes(office)))
    client = client_box(window[0])  # before the document (and its window) closes
    try:
        office.desktop.getCurrentComponent().setModified(False)
        office.desktop.getCurrentComponent().close(True)
    except Exception:  # noqa: BLE001 - the document is gone already
        pass
    time.sleep(2)
    return {"client": client, "tabs": shots}


def collect_theme(theme, args, res, collected):
    profile = os.path.join(args.out, f"profile-{args.label}-{theme}")
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(10)
        wg.dismiss_startup(office, os.path.join(args.out, f"{theme}-startup.png"))
        set_theme(office, theme)
        office.stop()
        office.start()  # the appearance applies from the next start
        time.sleep(8)
        for app in args.apps.split(","):
            try:
                collected[f"{app}-{args.label}-{theme}"] = collect_app(office, app, theme, args, res)
            except Exception as error:  # noqa: BLE001 - one app's failure must not lose the others
                res(f"[{app}-{args.label}-{theme}] crashed", False, repr(error))
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", required=True, choices=("100", "125", "150"))
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--port", type=int, default=2391)
    args = parser.parse_args()
    os.makedirs(os.path.join(args.out, "shots"), exist_ok=True)
    res = wg.Results(args.out, os.path.join(args.out, "profile"))
    scale = display_scale()
    if not res("display scaling is the label", scale == int(args.label), f"{scale} %"):
        return res.exit_code()
    collected = {"scale": scale}
    for theme in args.themes.split(","):
        collect_theme(theme, args, res, collected)
    with open(os.path.join(args.out, f"collected-{args.label}.json"), "w", encoding="utf-8") as handle:
        json.dump(collected, handle, ensure_ascii=False, indent=1)
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
