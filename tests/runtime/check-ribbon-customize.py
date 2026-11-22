# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Ribbon customization and the "Sử dụng gần đây" (recently used) tab on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-customize.py --instdir DIR --work DIR [--display :247] [--shots DIR]
                                                        [--apps writer,calc,impress,draw]
The X display must already run (this script never starts or stops it). Per app, at 1485x900, with
HST_RIBBON_DUMP_LAYOUT so the generated tabs' layouts can be checked by check-ribbon-v3-dumps.py:
  1. fresh profile: "Sử dụng gần đây" stands right after "Trang đầu" and shows its empty state;
  2. commands dispatched to the document appear on it once it is shown again;
  3. restart with a customization in <profile>/user/hst-ribbon/custom-<app>.json (a custom tab "Của tôi" after
     Trang đầu, the first group of Trang đầu hidden, a broken entry): the custom tab and its commands are there, the
     recently used tab still follows Trang đầu, the history survived the restart, the hidden group's caption is
     gone, the other tabs are unchanged;
  4. a right-click on the tab row offers "Tùy chỉnh ribbon…", which opens the dialog (closed with Escape); its
     command list and ribbon tree name every command (no raw ".uno:" id);
  5. Tùy chọn's service turns the tab off: after the reload the tab is gone.
Writes <work>/evidence.json; exit 1 on any failure.
"""
import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

RECENT = "Sử dụng gần đây"
HOME = "Trang đầu"
EMPTY = "Các lệnh bạn dùng sẽ xuất hiện ở đây"
CUSTOM_TAB = "Của tôi"
CUSTOM_GROUP = "Nhóm của tôi"
PORTS = {"writer": 7641, "calc": 7642, "impress": 7643, "draw": 7644}
HOME_PAGE = "HomeLabel"
FIRST_GROUP = "gdHomeClipboard"  # the first group of Trang đầu in every app, hidden by the customization
USED = [".uno:Bold", ".uno:Bold", ".uno:Bold", ".uno:Italic", ".uno:Underline"]
ADDED = [".uno:Bold", ".uno:Italic", ".uno:Strikeout"]
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    return ok


def customization(app):
    first_group = FIRST_GROUP
    return {"format": "hst-ribbon-customization", "version": 1, "app": app, "tabs": [
        {"id": HOME_PAGE, "groups": [{"id": first_group, "hidden": True}, {"id": "gdNoSuchGroup"}]},
        {"id": "hst-tab-1", "custom": True, "label": CUSTOM_TAB, "after": HOME_PAGE, "groups": [
            {"id": "hst-group-1", "custom": True, "label": CUSTOM_GROUP,
             "commands": [{"id": c} for c in ADDED] + [{"id": "not a command"}]}]},
        {"id": "NoSuchTab", "groups": []}]}


def texts(roles=("label",)):
    return [n[0] for n in gui.ribbon_nodes(roles)]


def ribbon_buttons():
    return [n[0] for n in gui.ribbon_nodes(("push button", "toggle button", "menu item", "push button menu"))]


def reopen(display, name):
    """Shows tab `name` after another one, so the tab's refresh on activation runs."""
    others = [t for t in gui.visible_names() if t not in (name, "Tệp tin")]
    if others:
        gui.open_tab(display, others[-1])
    return gui.open_tab(display, name)


def start(args, app, fresh, dumps):
    work = os.path.join(args.work, app)
    office = hst_gui.Office(args.instdir, work, PORTS[app], display=args.display, extra_args=[f"--{app}"],
                            nodefault=False, env={"HST_RIBBON_DUMP_LAYOUT": dumps},
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start(fresh=fresh)
    time.sleep(8)
    windows = [w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES[app] in n]
    if windows:
        gui.xdo(args.display, "windowmove", windows[0], "0", "0")
        gui.xdo(args.display, "windowsize", windows[0], "1485", "900")
        time.sleep(4)
    return office, work


def unmodified(office):
    """The commands changed the document: without this the office asks to save it and never quits."""
    try:
        office.desktop().getCurrentComponent().setModified(False)
    except Exception:  # noqa: BLE001 - no document: nothing to ask about
        pass


def menu_items():
    return [n for n in gui.walk(gui.office_app()) if n.getRoleName() == "menu item"]


def dialog_names(node, depth=0):
    """Every accessible name under the dialog, the rows of its tree views included (ribbon_tabs_gui.walk skips
    tables, and a tree view of a list store is one)."""
    try:
        yield node.name or ""
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 3000))] if depth < 16 else []
    except Exception:  # noqa: BLE001 - a row going away
        return
    for child in children:
        if child is not None:
            yield from dialog_names(child, depth + 1)


def raw_command_ids(names):
    """Names that are a bare command id: a command shown without its label."""
    return sorted({name for name in names if name.startswith(".uno:")})


def shot(args, office, name):
    if args.shots:
        office.screenshot(os.path.join(args.shots, name))


def check_app(args, app):
    dumps = os.path.join(args.work, "dumps", app)
    os.makedirs(dumps, exist_ok=True)
    office, work = start(args, app, True, dumps)
    try:
        tabs = gui.visible_names()
        default_tabs = [t for t in tabs if t != RECENT]
        gui.open_tab(args.display, HOME)
        time.sleep(1)
        home_buttons = ribbon_buttons()
        record(f"[{app}] recently used tab right after {HOME}",
               HOME in tabs and tabs.index(HOME) + 1 < len(tabs) and tabs[tabs.index(HOME) + 1] == RECENT, tabs)
        record(f"[{app}] empty state", gui.open_tab(args.display, RECENT) and EMPTY in texts(), texts())
        shot(args, office, f"{app}-recent-empty.png")
        frame = office.desktop().getCurrentFrame()
        for command in USED:
            office.dispatch(frame, command)
            time.sleep(0.2)
        office.dispatch(frame, ".uno:Undo")  # noise: never shown
        time.sleep(1)
        reopen(args.display, RECENT)
        time.sleep(2)
        buttons = ribbon_buttons()
        record(f"[{app}] used commands on the recently used tab", EMPTY not in texts() and len(buttons) >= 3, buttons)
        shot(args, office, f"{app}-recent-used.png")
        unmodified(office)
    finally:
        office.stop()  # the history is written at exit

    folder = os.path.join(work, "profile", "user", "hst-ribbon")
    record(f"[{app}] history written to the profile", os.path.isfile(os.path.join(folder, f"usage-{app}.json")),
           os.listdir(folder) if os.path.isdir(folder) else "no folder")
    with open(os.path.join(folder, f"custom-{app}.json"), "w", encoding="utf-8") as handle:
        json.dump(customization(app), handle, ensure_ascii=False)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, folder], check=False)

    office, work = start(args, app, False, dumps)
    try:
        tabs = gui.visible_names()
        record(f"[{app}] custom tab, recently used tab after {HOME}",
               tabs[tabs.index(HOME) + 1: tabs.index(HOME) + 3] == [RECENT, CUSTOM_TAB] if HOME in tabs else False, tabs)
        record(f"[{app}] built-in tabs unchanged", [t for t in tabs if t not in (RECENT, CUSTOM_TAB)] == default_tabs,
               tabs)
        gui.open_tab(args.display, HOME)
        time.sleep(1)
        buttons = ribbon_buttons()
        record(f"[{app}] hidden group gone from {HOME}",
               "Dán" in home_buttons and "Dán" not in buttons and len(buttons) < len(home_buttons),
               (len(home_buttons), len(buttons)))
        shot(args, office, f"{app}-home-customized.png")
        gui.open_tab(args.display, CUSTOM_TAB)
        time.sleep(1)
        record(f"[{app}] custom group and commands", CUSTOM_GROUP in texts() and len(ribbon_buttons()) >= len(ADDED),
               (texts(), ribbon_buttons()))
        shot(args, office, f"{app}-custom-tab.png")
        gui.open_tab(args.display, RECENT)
        time.sleep(2)
        record(f"[{app}] history kept over the restart", EMPTY not in texts() and len(ribbon_buttons()) >= 3,
               ribbon_buttons())
        # a ribbon command's menu (quick access toolbar) has the item too
        gui.open_tab(args.display, HOME)
        time.sleep(1)
        bold = [n for n in gui.ribbon_nodes(("push button", "toggle button")) if n[0] == "Đậm"]
        if bold:
            box = bold[0][2]
            gui.xdo(args.display, "mousemove", str(box[0] + box[2] // 2), str(box[1] + box[3] // 2), "click", "3")
            time.sleep(1.5)
            items = [n.name for n in menu_items()]
            record(f"[{app}] command menu: quick access and Tùy chỉnh ribbon…",
                   "Tùy chỉnh ribbon…" in items and any("truy cập nhanh" in i for i in items), items)
            gui.xdo(args.display, "key", "Escape")
            time.sleep(1)
        # right-click on the tab row
        box = dict((t[0], t[1]) for t in gui.ribbon_tabs()).get(HOME)
        if box:
            gui.xdo(args.display, "mousemove", str(box[0] + box[2] // 2), str(box[1] + box[3] // 2), "click", "3")
            time.sleep(1.5)
            items = [n.name for n in menu_items()]
            if record(f"[{app}] context menu offers Tùy chỉnh ribbon…", "Tùy chỉnh ribbon…" in items, items):
                node = next(n for n in menu_items() if n.name == "Tùy chỉnh ribbon…")
                gui.click(args.display, gui.extents(node))
                time.sleep(3)
                dialogs = [n for _w, n in hst_gui.toplevels(args.display, office.pid) if "Tùy chỉnh ribbon" in n]
                record(f"[{app}] customize dialog opens", bool(dialogs), hst_gui.toplevels(args.display, office.pid))
                office_app = gui.office_app()
                found = [n for n in (office_app.getChildAtIndex(i) for i in range(office_app.childCount))
                         if n and (n.name or "").startswith("Tùy chỉnh ribbon")]
                raw = raw_command_ids(dialog_names(found[0])) if found else ["no dialog"]
                record(f"[{app}] the dialog names every command (no raw .uno: id)", not raw, raw)
                shot(args, office, f"{app}-customize-dialog.png")
                gui.xdo(args.display, "key", "Escape")
                time.sleep(1.5)
            else:
                gui.xdo(args.display, "key", "Escape")
        # Tùy chọn › HST Office › Ribbon: off
        job = office.service("vn.hasontech.hst.RibbonCustomization")
        from com.sun.star.beans import NamedValue
        record(f"[{app}] service answers", job is not None and job.execute((NamedValue("Action", "getRecentEnabled"),)))
        job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", False)))
        time.sleep(4)
        record(f"[{app}] tab off after the switch", RECENT not in gui.visible_names(), gui.visible_names())
        job.execute((NamedValue("Action", "setRecentEnabled"), NamedValue("Enabled", True)))
        time.sleep(4)
        record(f"[{app}] tab back after the switch", RECENT in gui.visible_names(), gui.visible_names())
        unmodified(office)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--display", default=":247")
    parser.add_argument("--shots")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    args = parser.parse_args()
    if os.geteuid() == 0:  # as the build user under a session bus of its own (AT-SPI needs one)
        for path in filter(None, (args.work, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.work = os.path.abspath(args.instdir), os.path.abspath(args.work)
    address, launcher = private_atspi_bus()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", AT_SPI_BUS_ADDRESS=address)
    try:
        return run(args)
    finally:
        try:
            os.kill(launcher, signal.SIGTERM)
        except ProcessLookupError:
            pass


def private_atspi_bus():
    """This run's own AT-SPI bus, as check-banner-everywhere.py sets it up (that file's name is not importable)."""
    spec = importlib.util.spec_from_file_location("banner_everywhere", os.path.join(HERE, "check-banner-everywhere.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.private_atspi_bus()


def run(args):
    hst_gui.setup_uno(args.instdir)
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    for app in args.apps.split(","):
        try:
            check_app(args, app)
        except Exception as error:  # noqa: BLE001 - the next app still runs
            record(f"[{app}] run", False, repr(error))
    with open(os.path.join(args.work, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = [r for r in ROWS if r["status"] != "PASS"]
    print(f"{len(ROWS) - len(failed)} pass, {len(failed)} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
