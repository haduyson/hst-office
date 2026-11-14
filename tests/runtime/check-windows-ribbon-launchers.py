#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: clicking each ribbon group launcher (↘) of an INSTALLED HST Office opens its group's dialog on the group's
tab (data/ribbon/launcher-targets.json; the Linux counterpart is check-ribbon-launchers.py).

The office runs with its own profile in the tester's own session (tests/runtime/windows-own-session-task.ps1 over SSH).
Nothing is typed: the ribbon tab, the launcher and the dialog tabs are driven through the office's accessibility tree
over UNO, dialogs are closed with WM_CLOSE to their own HWND (windows_gui_dialogs). Each dialog is first left on
another tab, so a launcher that names no tab fails. Usage:
  "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-launchers.py --install DIR --out DIR [app ...]
"""
import argparse
import json
import os
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
from ribbon_launcher_contexts import MODULES, prepare  # noqa: E402

TABLE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "data", "ribbon", "launcher-targets.json")


def role(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)


def showing_named(accessible, name, wanted):
    return [c for c, _d in wg.walk(accessible, limit=24)
            if c.getAccessibleRole() == role(wanted) and c.getAccessibleName() == name and wg.showing(c)]


def selected_tab(window):
    import uno
    selected = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SELECTED")
    for context, _depth in wg.walk(window):
        if context.getAccessibleRole() == role("PAGE_TAB") and context.getAccessibleStateSet() & selected:
            return context.getAccessibleName()
    return None


def in_thread(action):
    """A modal dialog blocks the UNO call that opened it until it closes: run the call from a thread."""
    thread = threading.Thread(target=action, daemon=True)
    thread.start()
    return thread


def wait_dialog(office, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = wg.dialogs(office)
        if found:
            time.sleep(1.0)  # let the pages build before reading the tab
            return found[0]
        time.sleep(0.3)
    raise AssertionError("no dialog opened")


def leave_on_other_tab(office, frame, row):
    """Open the dialog the plain way and leave it on another tab (the tab a dialog reopens on unless told)."""
    office.dispatch_async(frame, row["command"].split("?", 1)[0])
    window, _title = wait_dialog(office)
    for context, _depth in wg.walk(window):
        if context.getAccessibleRole() == role("PAGE_TAB") and context.getAccessibleName() != row["tab"]:
            wg.press(context)
            time.sleep(0.5)
            break
    wg.close_dialog(window)
    time.sleep(1.0)


def check_row(office, report, row, out):
    what = f"{row['app']} {row['ribbon_tab']} > {row['group']}"
    doc = office.load("private:factory/" + MODULES[row["app"]])
    try:
        prepare(doc, row["app"], row.get("context"), out)
        time.sleep(2.0)
        frame = doc.getCurrentController().getFrame()
        top = frame.getContainerWindow()
        tabs = showing_named(top, row["ribbon_tab"], "PAGE_TAB")
        if not tabs:
            raise AssertionError(f"ribbon tab {row['ribbon_tab']!r} not shown")
        wg.press(tabs[0])
        time.sleep(1.5)
        if row.get("tab"):
            leave_on_other_tab(office, frame, row)
        label = row.get("label") or row["group"]
        launchers = showing_named(top, label, "PUSH_BUTTON")
        if len(launchers) != 1:
            names = sorted({c.getAccessibleName() for c, _d in wg.walk(top, limit=24)
                            if c.getAccessibleRole() == role("PUSH_BUTTON") and wg.showing(c)})
            raise AssertionError(f"{len(launchers)} shown buttons named {label!r}; shown: {names}")
        in_thread(lambda: wg.press(launchers[0]))
        window, title = wait_dialog(office)
        tab = selected_tab(window)
        wg.screenshot(os.path.join(out, row["app"] + "-" + row["id"] + ".png"))
        wg.close_dialog(window)
        report(what, not row.get("tab") or tab == row["tab"], f"{title} › {tab} (expected {row.get('tab')})")
    except Exception as error:  # noqa: BLE001 - one broken launcher must not hide the others
        report(what, False, repr(error))
        for window, _title in wg.dialogs(office):
            wg.close_dialog(window)
    finally:
        doc.setModified(False)
        doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2183)
    parser.add_argument("apps", nargs="*", default=list(MODULES))
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(TABLE, encoding="utf-8") as handle:
        rows = [r for r in json.load(handle)["launchers"] if r["app"] in args.apps and r.get("dialog")]
    report = wg.Results(args.out, os.path.join(args.out, "profile"))
    office = wg.WinOffice(args.install, os.path.join(args.out, "profile"), args.port, os.path.join(args.out, "logs"))
    try:
        office.start(fresh=True)
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        for row in rows:
            check_row(office, report, row, args.out)
    finally:
        office.stop()
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
