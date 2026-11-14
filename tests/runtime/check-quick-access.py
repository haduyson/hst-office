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

DEFAULTS = ["Lưu", "Hoàn tác", "Làm lại"]
ADD = "Thêm vào thanh truy cập nhanh"
MANY = [".uno:Paste", ".uno:Cut", ".uno:Copy", ".uno:Bold", ".uno:Italic", ".uno:Underline", ".uno:CenterPara",
        ".uno:DefaultBullet", ".uno:InsertTable", ".uno:InsertGraphic", ".uno:SearchDialog", ".uno:Print",
        ".uno:PrintPreview"]


def qat(display_top):
    """(names, box, node) of the quick access toolbar: the tool bar left of the first ribbon tab."""
    tabs = gui.ribbon_tabs()
    first = tabs[0][1] if tabs else (10 ** 6, 0, 0, 0)
    for node in gui.walk(gui.office_app()):
        try:
            if node.getRoleName() != "tool bar" or not gui.showing(node):
                continue
            box = gui.extents(node)
            if box[0] + box[2] <= first[0] + 2 and abs(box[1] - first[1]) < 40 and box[1] < display_top + 120:
                names = [node.getChildAtIndex(i).name for i in range(node.childCount)]
                shown = [n for i, n in enumerate(names) if n and gui.showing(node.getChildAtIndex(i))]
                return shown, box, node
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
    return [], None, None


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
        names = qat(0)[0]
        record("defaults", names[:3] == DEFAULTS and len(names) == 3, names)
        problem = right_click_add(args.display, "Dán")
        names = qat(0)[0]
        record("add-from-ribbon", not problem and names[-1:] == ["Dán"], problem or names)
        office.load("private:factory/scalc")
        time.sleep(8)
        calc = [w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES["calc"] in n]
        if calc:
            gui.xdo(args.display, "windowactivate", calc[0])
            time.sleep(3)
        names = qat(0)[0]
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
        names = qat(0)[0]
        record("persists-after-restart", "Dán" in names, names)
        banner = gui.geometry()[2]
        set_commands(office, "com.sun.star.text.TextDocument", MANY)
        time.sleep(4)
        names, box, _ = qat(0)
        tabs = gui.ribbon_tabs()
        ok = box is not None and tabs and box[0] + box[2] <= tabs[0][1][0] + 2 and gui.geometry()[2] == banner
        ok = ok and len(names) < 3 + 1 + len(MANY)  # some buttons went into the » menu
        record("overflow", ok, {"shown": names, "qat": box, "first_tab": tabs[0][1] if tabs else None,
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
