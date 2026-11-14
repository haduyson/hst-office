#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: clicking each ribbon group launcher (↘) of an INSTALLED HST Office opens its group's dialog on the group's
tab (data/ribbon/launcher-targets.json; the Linux counterpart is check-ribbon-launchers.py).

The office runs with its own profile in the tester's own session (tests/runtime/windows-own-session-task.ps1 over SSH).
Nothing is typed: the ribbon tab, the launcher and the dialog tabs are pressed through MSAA (windows-msaa-ribbon.ps1,
the tree VCL's IAccessible2 bridge serves), dialogs are closed with WM_CLOSE to their own HWND (windows_gui_dialogs). Each dialog is first left on
another tab, so a launcher that names no tab fails. Usage:
  "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-launchers.py --install DIR --out DIR [app ...]
"""
import argparse
import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
from ribbon_launcher_contexts import MODULES, prepare  # noqa: E402

TABLE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "data", "ribbon", "launcher-targets.json")


MSAA = os.path.join(HERE, "windows-msaa-ribbon.ps1")


def msaa(action, wait=True, **args):
    """Run one windows-msaa-ribbon.ps1 action; with wait=False the call may stay inside a modal dialog's loop."""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", MSAA, "-Action", action]
    for key, value in args.items():
        cmd += ["-" + key, str(value)]
    if not wait:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    return result.stdout.decode("utf-8", "replace").strip()


def close_dialogs(office):
    for window, _title in wg.dialogs(office):
        wg.close_dialog(window)


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
    msaa("other-tab", Hwnd=wg.dialog_hwnd(window), Name=row["tab"])
    time.sleep(0.5)
    wg.close_dialog(window)
    time.sleep(1.0)


def check_row(office, report, row, out):
    what = f"{row['app']} {row['ribbon_tab']} > {row['group']}"
    doc = office.load("private:factory/" + MODULES[row["app"]])
    pressing = None
    try:
        prepare(doc, row["app"], row.get("context"), out)
        time.sleep(2.0)
        close_dialogs(office)  # the tip of the day comes with the first document
        pid = office.bin_pids_of_profile()[0]
        shown = msaa("select-tab", OfficePid=pid, Name=row["ribbon_tab"])
        if not shown.startswith("OK"):
            raise AssertionError(f"ribbon tab {row['ribbon_tab']!r}: {shown}; {msaa('dump', OfficePid=pid)[:600]}")
        time.sleep(1.5)
        if os.environ.get("HST_LAUNCHER_DUMP"):
            report.note(what + " before", msaa("dump", OfficePid=pid).split("SMALL")[-1])
        if row.get("tab"):
            leave_on_other_tab(office, doc.getCurrentController().getFrame(), row)
        pressing = msaa("press", wait=False, OfficePid=pid, Name=row.get("label") or row["group"])
        window, title = wait_dialog(office)
        tab = msaa("selected", Hwnd=wg.dialog_hwnd(window)).removeprefix("TAB ")
        if os.environ.get("HST_LAUNCHER_DUMP"):
            report.note(what + " dialog", msaa("tabs", Hwnd=wg.dialog_hwnd(window)))
        wg.close_dialog(window)
        report(what, not row.get("tab") or tab == row["tab"], f"{title} › {tab} (expected {row.get('tab')})")
    except Exception as error:  # noqa: BLE001 - one broken launcher must not hide the others
        if pressing is not None and pressing.poll() is not None:
            error = f"{error!r}; press: {pressing.stdout.read().decode('utf-8', 'replace').strip()}"
        report(what, False, str(error))
        if os.environ.get("HST_LAUNCHER_DUMP"):
            report.note(what + " ribbon", msaa("dump", OfficePid=office.bin_pids_of_profile()[0]).split("SMALL")[-1])
        close_dialogs(office)
    finally:
        if pressing is not None:
            try:
                pressing.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pressing.kill()  # our own helper process, stuck in a dialog that is gone
        doc.setModified(False)
        doc.close(True)


def check_toggles(office, report, apps):
    """The launchers' state fix touches only Page variants of a command: plain toggles keep their checked state
    (the ribbons have no toggle with other arguments; StyleApply?Style:… of Sheets are menu items)."""
    for app in (a for a in ("writer", "calc", "impress") if a in apps):
        doc = office.load("private:factory/" + MODULES[app])
        try:
            if app == "writer":
                cursor = doc.getText().createTextCursor()
                cursor.setString("Đậm")
                cursor.gotoStart(False)
                cursor.gotoEnd(True)
                doc.getCurrentController().select(cursor)
            elif app == "calc":
                cell = doc.Sheets.getByIndex(0).getCellRangeByName("A1")
                cell.setString("Đậm")
                doc.getCurrentController().select(cell)
            else:
                from ribbon_launcher_contexts import add_shape
                add_shape(doc, "Đậm")
            time.sleep(1.0)
            office.dispatch_async(doc.getCurrentController().getFrame(), ".uno:Bold").join(30)
            time.sleep(2.0)
            close_dialogs(office)
            pid = office.bin_pids_of_profile()[0]
            msaa("select-tab", OfficePid=pid, Name="Trang đầu")
            time.sleep(1.5)
            states = {name: msaa("state", OfficePid=pid, Name=name).split()[1:] for name in ("Đậm", "Nghiêng")}
            pressed = {name: [bool(int(s, 16) & 0x18) for s in found] for name, found in states.items()}
            if app == "writer":
                report(f"{app}: Đậm stays pressed, Nghiêng not",
                       pressed["Đậm"][:1] == [True] and pressed["Nghiêng"][:1] == [False], str(states))
            else:  # Sheets and Slides do not show the pressed state over MSAA in a disconnected session
                report.note(f"{app}: Đậm/Nghiêng states (not readable here, also before the change)", str(states))
        except Exception as error:  # noqa: BLE001
            report(f"{app}: toggles", False, repr(error))
        finally:
            doc.setModified(False)
            doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2183)
    parser.add_argument("--toggles-only", action="store_true", help="only the toggle state check")
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
        for row in [] if args.toggles_only else rows:
            check_row(office, report, row, args.out)
        check_toggles(office, report, args.apps)
    finally:
        office.stop()
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
