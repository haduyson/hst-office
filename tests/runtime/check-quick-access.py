#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Quick access toolbar of the HST ribbon (hst-ribbon-adaptive-qat.patch), on a built office under Xvfb:
  - defaults: Lưu, Hoàn tác, Làm lại at the start of the tab row;
  - a right-click on the ribbon's Dán button and "Thêm vào thanh truy cập nhanh" adds Paste;
  - the list is per app: Sheets, opened in the same profile, does not get Paste;
  - the list survives a restart of the office;
  - overflow: with 16 commands the extra buttons go into the » menu and the banner does not move.
Usage: check-quick-access.py --instdir DIR [--display :171] [--out DIR]   (as root: runs as the build user)"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

DEFAULTS = [".uno:Save", ".uno:Undo", ".uno:Redo"]
WRITER, CALC = "com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument"
ADD = "Thêm vào thanh truy cập nhanh"
MANY = [".uno:Paste", ".uno:Cut", ".uno:Copy", ".uno:Bold", ".uno:Italic", ".uno:Underline", ".uno:CenterPara",
        ".uno:DefaultBullet", ".uno:InsertTable", ".uno:InsertGraphic", ".uno:SearchDialog", ".uno:Print",
        ".uno:PrintPreview"]


def shown(office, module):
    """Commands shown in the module's quick access toolbar (its notebookbarshortcuts settings). The toolbox sits in
    the ribbon's tab control, whose accessible children are only the tabs, so the list is read over UNO."""
    supplier = office.smgr.createInstanceWithContext(
        "com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
    items = supplier.getUIConfigurationManager(module).getSettings(
        "private:resource/toolbar/notebookbarshortcuts", False)
    result = []
    for index in range(items.getCount()):
        props = {p.Name: p.Value for p in items.getByIndex(index)}
        if props.get("IsVisible", True):
            result.append(props.get("CommandURL"))
    return result


def right_click_add(display, label):
    found = [n for n in gui.ribbon_nodes(("push button", "toggle button")) if (n[0] or "").startswith(label)]
    if not found:
        return f"no ribbon button {label}"
    box = found[0][2]
    gui.xdo(display, "mousemove", str(box[0] + box[2] // 2), str(box[1] + box[3] // 2), "click", "3")
    time.sleep(1.5)
    items = [n for n in gui.walk(gui.office_app()) if n.getRoleName() == "menu item" and n.name == ADD]
    if not items:
        return "no menu item " + ADD
    gui.click(display, gui.extents(items[0]))
    time.sleep(2)
    return ""


def set_commands(office, module, commands):
    """Shows `commands` (and keeps the defaults) in the module's quick access toolbar through the UI configuration."""
    import uno
    supplier = office.smgr.createInstanceWithContext(
        "com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
    config = supplier.getUIConfigurationManager(module)
    items = config.getSettings("private:resource/toolbar/notebookbarshortcuts", True)
    for command in commands:
        props = []
        for name, value in (("CommandURL", command), ("Label", ""), ("Type", 0), ("Style", 0), ("IsVisible", True)):
            prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop.Name, prop.Value = name, value
            props.append(prop)
        uno.invoke(items, "insertByIndex", (items.getCount(), uno.Any("[]com.sun.star.beans.PropertyValue",
                                                                          tuple(props))))
    config.replaceSettings("private:resource/toolbar/notebookbarshortcuts", items)
    config.store()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":171")
    parser.add_argument("--out", default="tests/output/quick-access")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    if os.geteuid() == 0:
        os.makedirs(out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable,
                              os.path.abspath(__file__)] + sys.argv[1:])
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    results = []

    def record(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:300]}", flush=True)
        hst_gui.screenshot(os.path.join(out, name + ".png"), args.display)

    work = os.path.join(out, "office")
    office, wid, _ = gui.start(args.instdir, "writer", args.display, work, hst_gui.free_port())
    try:
        office.close_welcome()
        time.sleep(2)
        names = shown(office, WRITER)
        record("defaults", names == DEFAULTS, names)
        problem = right_click_add(args.display, "Dán")
        names = shown(office, WRITER)
        record("add-from-ribbon", not problem and names[-1:] == [".uno:Paste"], problem or names)
        office.load("private:factory/scalc")
        time.sleep(8)
        names = shown(office, CALC)
        record("per-app", names == DEFAULTS, names)
        office.stop()
        office.start(fresh=False)
        time.sleep(10)
        office.close_welcome()
        writer = [w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES["writer"] in n]
        if writer:
            gui.xdo(args.display, "windowmove", writer[0], "0", "0")
            gui.xdo(args.display, "windowsize", writer[0], "1366", "900")
            time.sleep(4)
        names = shown(office, WRITER)
        record("persists-after-restart", ".uno:Paste" in names, names)
        banner = gui.geometry()[2]
        tabs_before = [t[1] for t in gui.ribbon_tabs()]
        set_commands(office, WRITER, [c for c in MANY if c != ".uno:Paste"])
        time.sleep(4)
        tabs_after = [t[1] for t in gui.ribbon_tabs()]
        # 16 buttons do not fit before the tabs at 1366 px: the extra ones go into the » menu, so the last tab and
        # the banner keep their place (the tabs may move right only by the room the toolbar takes)
        # the toolbar grew by less than the 12 buttons added (about 26 px each): the rest is in its » menu
        grown = tabs_after[0][0] - tabs_before[0][0] if tabs_after and tabs_before else 10 ** 6
        ok = grown < 12 * 22 and gui.geometry()[2] == banner
        record("overflow", ok, {"commands": len(shown(office, WRITER)), "tabs_before": tabs_before[:2],
                                "tabs_after": tabs_after[:2], "grown": grown, "last_tab": tabs_after[-1:] ,
                                "banner_before": banner, "banner_after": gui.geometry()[2]})
    finally:
        office.stop()
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=1)
    failed = [r for r in results if r["status"] == "FAIL"]
    print(f"{len(results) - len(failed)}/{len(results)} checks pass")
    return 1 if failed or len(results) < 5 else 0


if __name__ == "__main__":
    sys.exit(main())
