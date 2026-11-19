#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: a contextual ribbon tab stays the current tab after a command on its object (bug #9: the ribbon went
back to "Trang đầu"), for a picture, a table and a shape in Writer, Sheets, Slides and Draw and a chart in Sheets
(Sheets' table: a database range with a table style, as Chèn › Bảng makes; its pivot table is checked too).

Per app on an INSTALLED HST Office (console session, under C:\\hst-test\\console-lock.txt): a new document with the
objects of ribbon_contextual_objects.py; for each object it is selected, its first contextual tab (a tab the plain
document did not show) is selected through MSAA (windows-msaa-ribbon.ps1), a command runs on the object through UNO
(COMMANDS) and, after SETTLE seconds, MSAA must report the same tab selected (state 0x2). No mouse clicks.
  "<install>\\program\\python.exe" tests/runtime/check-windows-contextual-keep-tab.py --install DIR --out DIR
Evidence: <out>\\results.json (one PASS/FAIL per app and object).
"""
import argparse
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
from ribbon_contextual_objects import make_objects, park  # noqa: E402

APPS = {"writer": ("private:factory/swriter", "HST Writer"), "calc": ("private:factory/scalc", "HST Sheets"),
        "impress": ("private:factory/simpress", "HST Slides"), "draw": ("private:factory/sdraw", "HST Draw")}
# the objects each app is checked with; Sheets' cell objects (pivot, table) first: after a drawing selection, a cell
# selected through the API does not switch Sheets to their shells
KINDS = {"writer": ("picture", "table", "shape"), "calc": ("pivot", "table", "picture", "shape", "chart"),
         "impress": ("picture", "table", "shape"), "draw": ("picture", "table", "shape")}
# a command on the selected object that leaves it selected
COMMANDS = {"picture": ".uno:GraphicFilterInvert", "table": ".uno:InsertRowsAfter", "shape": ".uno:FillShadow",
            "chart": ".uno:BringToFront", "pivot": ".uno:RecalcPivotTable"}
CALC_TABLE_COMMAND = ".uno:Bold"  # on a cell of the Sheets table: the cursor stays in it
CALC_TABLE_STYLE = "TableStyleMedium2"  # a built-in table style of core (defaulttablestyles.inc)
MSAA = os.path.join(HERE, "windows-msaa-ribbon.ps1")
SETTLE = 3


def ribbon_tabs(office):
    """[(name, selected)] of the shown ribbon tabs (MSAA page tabs; 0x2 selected)."""
    pid = office.bin_pids_of_profile()[0]
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", MSAA, "-Action", "dump",
                          "-OfficePid", str(pid)], capture_output=True, timeout=180, check=False)
    return parse_tabs(out.stdout.decode("utf-8", "replace"))


def parse_tabs(text):
    """[(name, selected)] from the "TABS name[0xSTATE] | ..." line of windows-msaa-ribbon.ps1 -Action dump."""
    for line in text.splitlines():
        if line.startswith("TABS "):
            tabs = []
            for item in line[5:].split(" | "):
                name, _, state = item.rpartition("[0x")
                if name:
                    tabs.append((name, bool(int(state.rstrip("]"), 16) & 0x2)))
            return tabs
    return []


def select_tab(office, name):
    pid = office.bin_pids_of_profile()[0]
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", MSAA, "-Action",
                          "select-tab", "-Name", name, "-OfficePid", str(pid)], capture_output=True, timeout=180,
                         check=False)
    return out.stdout.decode("utf-8", "replace").startswith("OK")


def make_calc_table(doc):
    """A Sheets table: a database range over K1:L4 with a table style (what makes the table shell, and its contextual
    tab, apply to a cell in it); returns a cell inside it."""
    from com.sun.star.table import CellRangeAddress
    sheet = doc.Sheets.getByIndex(0)
    for row, (name, value) in enumerate((("Tên", None), ("a", 1), ("b", 2), ("c", 3))):
        sheet.getCellByPosition(10, row).String = name
        if value is None:
            sheet.getCellByPosition(11, row).String = "Số"
        else:
            sheet.getCellByPosition(11, row).Value = value
    area = CellRangeAddress()
    area.Sheet, area.StartColumn, area.EndColumn, area.EndRow = 0, 10, 11, 3
    doc.DatabaseRanges.addNewByName("Bang1", area)
    doc.DatabaseRanges.getByName("Bang1").setPropertyValue("TableStyleName", CALC_TABLE_STYLE)
    return sheet.getCellByPosition(10, 2)


def command_for(app, kind):
    return CALC_TABLE_COMMAND if (app, kind) == ("calc", "table") else COMMANDS[kind]


class _Dispatcher:
    """What park() needs of the office: a dispatch that returns once the command ran."""

    def __init__(self, office):
        self.office = office

    def dispatch(self, frame, command):
        self.office.dispatch_async(frame, command).join(30)


def check_app(app, args, res):
    factory, title = APPS[app]
    office = wg.WinOffice(args.install, os.path.join(args.out, f"profile-{app}"), args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, f"{app}-startup.png"))
        office.load(factory)
        time.sleep(6)
        wg.dismiss_startup(office, os.path.join(args.out, f"{app}-doc-startup.png"), timeout=8, settle=2)
        office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
        time.sleep(4)
        window = wg.find_window(lambda text: title in text, timeout=30)
        if not res(f"[{app}] window", bool(window)):
            return
        wg.foreground(window[0])
        doc = office.desktop.getCurrentComponent()
        image = "file:///" + os.path.join(args.install, "share", "extensions", "hst-vietnamese-tools", "banners",
                                          "aios@1x.png").replace("\\", "/")
        objects = make_objects(app, doc, image)
        if app == "calc":
            objects["table"] = make_calc_table(doc)
        frame = doc.CurrentController.Frame
        for kind in KINDS[app]:
            park(app, doc, _Dispatcher(office))
            time.sleep(SETTLE)
            plain = {name for name, _ in ribbon_tabs(office)}
            doc.CurrentController.select(objects[kind])
            time.sleep(SETTLE)
            contextual = [name for name, _ in ribbon_tabs(office) if name not in plain]
            if not res(f"[{app}] {kind}: contextual tab shown", bool(contextual), contextual):
                continue
            tab = contextual[0]
            select_tab(office, tab)
            time.sleep(SETTLE)
            before = [name for name, selected in ribbon_tabs(office) if selected]
            if not res(f"[{app}] {kind}: {tab} selected", before == [tab], before):
                continue
            command = command_for(app, kind)
            office.dispatch_async(frame, command).join(30)
            time.sleep(SETTLE)
            after = [name for name, selected in ribbon_tabs(office) if selected]
            res(f"[{app}] {kind}: {tab} still selected after {command}", after == [tab], after)
    finally:
        try:
            office.desktop.getCurrentComponent().setModified(False)
        except Exception:  # noqa: BLE001 - no document, or the office is gone
            pass
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--port", type=int, default=2384)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    res = wg.Results(args.out, os.path.join(args.out, "profile"))
    for app in args.apps.split(","):
        try:
            check_app(app, args, res)
        except Exception as error:  # noqa: BLE001 - one app's failure must not lose the others
            res(f"[{app}] crashed", False, repr(error))
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
