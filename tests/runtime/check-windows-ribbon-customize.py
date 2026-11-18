#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: ribbon customization and the "Sử dụng gần đây" (recently used) tab of an INSTALLED HST Office (Linux
counterpart: check-ribbon-customize.py).

Own session (tests/runtime/windows-own-session-task.ps1; nothing is typed or clicked: the tabs are selected and read
through the accessibility tree over UNO). One fresh profile; before the documents open, a customization is written to
<profile>/user/hst-ribbon/custom-<app>.json (a custom tab "Của tôi" after Trang đầu with three commands). Per app
(HST Writer, Sheets, Slides, Draw):
  - the tabs: Trang đầu, Sử dụng gần đây, Của tôi in that order, the built-in tabs after them;
  - the recently used tab shows its empty state, and no longer after Bold/Italic were dispatched to the document;
  - the custom tab shows its group "Nhóm của tôi";
  - Tùy chọn's service (vn.hasontech.hst.RibbonCustomization) turns the tab off and on again.
Evidence: PrintWindow shots (<out>/<app>-*.bmp) and <out>/results.json.
Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-customize.py --install DIR --out DIR
"""
import argparse
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402

APPS = {"writer": ("private:factory/swriter", "HST Writer"), "calc": ("private:factory/scalc", "HST Sheets"),
        "impress": ("private:factory/simpress", "HST Slides"), "draw": ("private:factory/sdraw", "HST Draw")}
HOME, RECENT, CUSTOM_TAB, CUSTOM_GROUP = "Trang đầu", "Sử dụng gần đây", "Của tôi", "Nhóm của tôi"
EMPTY = "Các lệnh bạn dùng sẽ xuất hiện ở đây"
USED = [".uno:Bold", ".uno:Bold", ".uno:Italic"]


def customization(app):
    return {"format": "hst-ribbon-customization", "version": 1, "app": app, "tabs": [
        {"id": "hst-tab-1", "custom": True, "label": CUSTOM_TAB, "after": "HomeLabel", "groups": [
            {"id": "hst-group-1", "custom": True, "label": CUSTOM_GROUP,
             "commands": [{"id": ".uno:Bold"}, {"id": ".uno:Italic"}, {"id": ".uno:Strikeout"}]}]}]}


def role(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)


def window_of(office, title):
    for window in office.top_windows():
        try:
            context = window.getAccessibleContext()
            if title in (context.getAccessibleName() or ""):
                return window
        except Exception:  # noqa: BLE001 - a window going away
            continue
    return None


def tabs(window):
    """[(name, context)] of the ribbon's page tabs, in order."""
    found = []
    for context, _depth in wg.walk(window):
        try:
            if context.getAccessibleRole() == role("PAGE_TAB"):
                found.append((context.getAccessibleName(), context))
        except Exception:  # noqa: BLE001
            continue
    names = [n for n, _c in found]
    return found if HOME in names else []


def select_tab(window, name):
    for tab_name, context in tabs(window):
        if tab_name == name:
            parent = context.getAccessibleParent().getAccessibleContext()
            parent.selectAccessibleChild(context.getAccessibleIndexInParent())
            time.sleep(2)
            return True
    return False


def shown_texts(window):
    return wg.texts(window, limit=400)


def check_app(office, app, out, res):
    doc = office.load(APPS[app][0])
    time.sleep(6)
    wg.dismiss_startup(office, os.path.join(out, f"{app}-startup.png"), timeout=8, settle=2)
    found = wg.find_window(lambda title: APPS[app][1] in title, timeout=30)
    window = window_of(office, APPS[app][1])
    if not res(f"[{app}] window found", bool(found) and window is not None, APPS[app][1]):
        return
    shot = wg.load_check("check-windows-quick-access").window_shot
    names = [n for n, _c in tabs(window)]
    home = names.index(HOME) if HOME in names else -1
    res(f"[{app}] {RECENT} and {CUSTOM_TAB} right after {HOME}",
        home >= 0 and names[home + 1:home + 3] == [RECENT, CUSTOM_TAB], names)
    select_tab(window, RECENT)
    res(f"[{app}] empty state", EMPTY in shown_texts(window), shown_texts(window)[:40])
    shot(found[0], os.path.join(out, f"{app}-recent-empty.bmp"))
    frame = doc.getCurrentController().getFrame()
    helper = office.service("com.sun.star.frame.DispatchHelper")
    for command in USED:
        helper.executeDispatch(frame, command, "", 0, ())
        time.sleep(0.3)
    select_tab(window, HOME)
    select_tab(window, RECENT)
    time.sleep(2)
    res(f"[{app}] used commands on {RECENT}", EMPTY not in shown_texts(window) and "Đậm" in shown_texts(window),
        shown_texts(window)[:40])
    shot(found[0], os.path.join(out, f"{app}-recent-used.bmp"))
    select_tab(window, CUSTOM_TAB)
    res(f"[{app}] custom group", CUSTOM_GROUP in shown_texts(window), shown_texts(window)[:40])
    shot(found[0], os.path.join(out, f"{app}-custom-tab.bmp"))
    from com.sun.star.beans import NamedValue
    job = office.service("vn.hasontech.hst.RibbonCustomization")
    job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", False)))
    time.sleep(5)
    window = window_of(office, APPS[app][1])
    names = [n for n, _c in tabs(window)] if window is not None else []
    res(f"[{app}] tab off after the switch", HOME in names and RECENT not in names, names)
    job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", True)))
    time.sleep(5)
    window = window_of(office, APPS[app][1])
    names = [n for n, _c in tabs(window)] if window is not None else []
    res(f"[{app}] tab back after the switch", RECENT in names, names)
    doc.setModified(False)
    doc.close(True)
    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2379)
    parser.add_argument("--apps", default="writer,calc,impress,draw")
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
        folder = os.path.join(profile, "user", "hst-ribbon")
        os.makedirs(folder, exist_ok=True)
        for app in APPS:
            with open(os.path.join(folder, f"custom-{app}.json"), "w", encoding="utf-8") as handle:
                json.dump(customization(app), handle, ensure_ascii=False)
        for app in args.apps.split(","):
            try:
                check_app(office, app, args.out, res)
            except Exception as error:  # noqa: BLE001 - the next app still runs
                res(f"[{app}] run", False, repr(error))
    finally:
        office.stop()
    res(f"history written to the profile", any(n.startswith("usage-") for n in os.listdir(folder)),
        os.listdir(folder))
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
