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
import threading
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
# the contextual tabs each object opens (named as in Office; check-ribbon-contextual.py checks the same on Linux)
EXPECTED = {"picture": ("Định dạng ảnh",), "table": ("Thiết kế bảng", "Bố trí bảng"),
            "shape": ("Định dạng hình dạng",), "chart": ("Thiết kế biểu đồ", "Định dạng biểu đồ"),
            "pivot": ("Phân tích bảng tổng hợp",)}
MSAA = os.path.join(HERE, "windows-msaa-ribbon.ps1")
SETTLE = 3
# --main-thread: the dispatches run on the office's main thread (DispatchHelper's OnMainThread), as a user's click
# does; without it they run on the UNO bridge thread (a harness-only path that can deadlock with accessibility)
DISPATCH_ARGS = {}
STEP_TIMEOUT = 240  # seconds for one object: four MSAA reads, three settles and the command


def msaa(office, *args):
    pid = office.bin_pids_of_profile()[0]
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", MSAA, *args,
                          "-OfficePid", str(pid)], capture_output=True, timeout=180, check=False)
    return out.stdout.decode("utf-8", "replace")


def ribbon_tabs(office):
    """[(name, selected)] of the SHOWN ribbon tabs, left to right. MSAA lists the hidden contextual tabs as well,
    without the invisible state: only their empty rectangle tells them apart (rects); 0x2 of dump is the selected."""
    shown = parse_rects(msaa(office, "-Action", "rects"))
    selected = dict(parse_tabs(msaa(office, "-Action", "dump")))
    return [(name, selected.get(name, False)) for name in shown]


def parse_rects(text):
    """Names of the ribbon tabs with an area, left to right, from "RECT x y w h name" lines (the tab row is at the
    window's top: Sheets' sheet tabs and Draw's layer tabs are page tabs too)."""
    tabs = []
    for line in text.splitlines():
        parts = line.strip().split(" ", 5)
        if len(parts) == 6 and parts[0] == "RECT":
            x, y, w, h = (int(v) for v in parts[1:5])
            if w > 0 and h > 0 and y < 300:
                tabs.append((x, parts[5]))
    return [name for _, name in sorted(tabs)]


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
    return msaa(office, "-Action", "select-tab", "-Name", name).startswith("OK")


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


def stop_office(office, shot, res, app, timeout=120):
    """office.stop() in a thread: Desktop.terminate does not return while a prompt holds the quit. Past the timeout
    the screen is kept (what held it) and our own processes end, so the next app still runs."""
    worker = threading.Thread(target=office.stop, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        # what holds the quit: the screen, and every window of the office with its accessible names (a save prompt
        # of the document checked here is the harness; any other prompt is a product bug)
        windows = what_holds(office, shot)
        import windows_gui_processes as processes
        office.proc.kill()
        processes.terminate(office.url)
        res(f"[{app}] office closed", False, f"Desktop.terminate held over {timeout} s: {shot}; {windows}")


class _Dispatcher:
    """What park() needs of the office: a dispatch that returns once the command ran."""

    def __init__(self, office):
        self.office = office

    def dispatch(self, frame, command):
        self.office.dispatch_async(frame, command, **DISPATCH_ARGS).join(30)


def check_kind(app, kind, doc, objects, frame, office, res, args):
    park(app, doc, _Dispatcher(office))
    time.sleep(SETTLE)
    plain = {name for name, _ in ribbon_tabs(office)}
    if not res(f"[{app}] {kind}: ribbon tabs read", bool(plain), sorted(plain)):
        return
    doc.CurrentController.select(objects[kind])
    time.sleep(SETTLE)
    now = [name for name, _ in ribbon_tabs(office)]
    contextual = [name for name in now if name not in plain]
    wanted = [name for name in contextual if name in EXPECTED[kind]]
    if not res(f"[{app}] {kind}: contextual tab shown", bool(wanted), contextual or now):
        return
    tab = wanted[0]
    select_tab(office, tab)
    time.sleep(SETTLE)
    before = [name for name, selected in ribbon_tabs(office) if selected]
    if not res(f"[{app}] {kind}: {tab} selected", before == [tab], before):
        return
    if args.shots:  # the contextual tab as the user sees it, before the command
        wg.screenshot(os.path.join(args.out, "shots", f"{app}-{kind}.png"), cursor=False)
    command = command_for(app, kind)
    dispatch = office.dispatch_async(frame, command, **DISPATCH_ARGS)
    dispatch.join(30)
    if dispatch.is_alive():  # the command opened something modal: what it is decides harness or product
        shot = os.path.join(args.out, f"{app}-{kind}-command-held.png")
        res(f"[{app}] {kind}: {command} returned", False, f"held over 30 s: {shot}; " + what_holds(office, shot))
    time.sleep(SETTLE)
    after = [name for name, selected in ribbon_tabs(office) if selected]
    res(f"[{app}] {kind}: {tab} still selected after {command}", after == [tab], after)


def leave_unmodified(app, doc, office):
    """The checked document goes without a save prompt: unmodified, its controller suspended, then closed."""
    try:
        doc.setModified(False)
    except Exception as error:  # noqa: BLE001 - the office is gone
        print("setModified:", repr(error), flush=True)
    try:
        doc.CurrentController.suspend(True)
        doc.close(True)
    except Exception as error:  # noqa: BLE001 - the quit then shows what still holds it
        print("close:", repr(error), flush=True)


def what_holds(office, shot):
    """The screen and every window of the office with its accessible names, kept next to SHOT; returns the names."""
    wg.screenshot(shot, cursor=False)
    try:
        windows = msaa(office, "-Action", "tabs")
    except Exception as error:  # noqa: BLE001 - the screenshot stays the evidence
        windows = repr(error)
    # a prompt answers and shows above; a hung UI thread answers nothing: then a dump of the office for its stack
    try:
        import windows_hang_probe as hang
        states = hang.ui_state()
        windows += "\nUI " + "; ".join(f"{title}: {state}" for _hwnd, title, state in states)
        if any(state == "hung" for _hwnd, _title, state in states):
            dump = os.path.splitext(shot)[0] + ".dmp"
            pid = office.bin_pids_of_profile()[0]
            windows += f"\nDUMP {dump}: {hang.write_minidump(pid, dump)}"
            program = getattr(office, "program", "")
            stacks = hang.thread_stacks(pid, os.environ.get("HST_PDB_PATH", program))
            if stacks is not None:
                with open(os.path.splitext(shot)[0] + "-stacks.txt", "w", encoding="utf-8") as handle:
                    handle.write(stacks)
                windows += f"\nSTACKS {os.path.splitext(shot)[0]}-stacks.txt"
            else:
                windows += "\nSTACKS no cdb.exe on this machine"
    except Exception as error:  # noqa: BLE001 - the screenshot and the names stay the evidence
        windows += f"\nUI state unknown: {error!r}"
    with open(os.path.splitext(shot)[0] + ".txt", "w", encoding="utf-8") as handle:
        handle.write(windows)
    return windows


def check_app(app, args, res):
    factory, title = APPS[app]
    office = wg.WinOffice(args.install, os.path.join(args.out, f"profile-{app}"), args.port, args.out, nodefault=True)
    office.start(fresh=True)
    doc = None
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
            # each object in a thread: a UNO call held by a prompt must not hang the run without evidence
            step = threading.Thread(target=check_kind, args=(app, kind, doc, objects, frame, office, res, args),
                                    daemon=True)
            step.start()
            step.join(STEP_TIMEOUT)
            if step.is_alive():
                shot = os.path.join(args.out, f"{app}-{kind}-held.png")
                res(f"[{app}] {kind}: step finished", False, f"held over {STEP_TIMEOUT} s: {shot}; "
                    + what_holds(office, shot))
                break
    finally:
        # the document itself: with a chart selected the current component is the chart's model, and a modified
        # sheet would hold the close on its save prompt
        # each on its own: a refused park (Slides' select of nothing) must not leave the save prompt in the way
        if doc is not None:  # bounded as well: a held prompt holds these calls too; the close then shows it
            tidy = threading.Thread(target=leave_unmodified, args=(app, doc, office), daemon=True)
            tidy.start()
            tidy.join(60)
        stop_office(office, os.path.join(args.out, f"{app}-close-blocked.png"), res, app)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--port", type=int, default=2384)
    parser.add_argument("--main-thread", action="store_true", help="dispatch on the office's main thread")
    parser.add_argument("--shots", action="store_true", help="screenshot each contextual tab once selected")
    args = parser.parse_args()
    if args.main_thread:
        DISPATCH_ARGS["OnMainThread"] = True
    os.makedirs(args.out, exist_ok=True)
    res = wg.Results(args.out, os.path.join(args.out, "profile"))
    for app in args.apps.split(","):
        try:
            check_app(app, args, res)
        except Exception as error:  # noqa: BLE001 - one app's failure must not lose the others
            import traceback
            res(f"[{app}] crashed", False, traceback.format_exc())
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
