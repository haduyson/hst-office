#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Writer: Backspace with a whole table selected deletes the table, as in Word (real key events in a visible office).

hst-writer-backspace-deletes-selected-table.patch. Each case opens its own copy of a small document (a paragraph, a
2x2 table, a paragraph; or a table nested in a table's first cell), puts the cursor in a cell through the API, then
sends the keys as the user types them: xdotool on an X display (Linux), keybd_event to the foreground office window
(Windows, the window activated first and checked with GetForegroundWindow).
  backspace  Ctrl+A twice in B2, Backspace: no table left, the cursor in "after"; Ctrl+Z: the table is back.
  delete     Ctrl+A twice, Delete: the table stays with empty cells.
  partial    Shift+Right three times from A1 (A1 and B1), Backspace: the table stays, row 2 untouched.
  nested     Ctrl+A twice in the inner table, Backspace: only the inner table goes.
The office quits with .uno:Quit on its main thread (XUITest.executeCommandForProvider).
Usage (the office's own python):
  Linux:   python3 check-writer-table-backspace.py --instdir DIR --out DIR [--display :147]
  Windows: python.exe check-writer-table-backspace.py --soffice <instdir>\\program\\soffice.exe --out DIR
Exit 1 on a failure.
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS = sys.platform == "win32"
RESULTS = []

HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<office:document '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" office:version="1.3" '
        'office:mimetype="application/vnd.oasis.opendocument.text"><office:body><office:text>')
TAIL = '</office:text></office:body></office:document>\n'


def table_xml(name, prefix="", first_cell_extra=""):
    cell = '<table:table-cell office:value-type="string">%s<text:p>%s</text:p></table:table-cell>'
    return (f'<table:table table:name="{name}"><table:table-column table:number-columns-repeated="2"/>'
            '<table:table-row>' + cell % (first_cell_extra, prefix + "A1") + cell % ("", prefix + "B1")
            + '</table:table-row><table:table-row>' + cell % ("", prefix + "A2") + cell % ("", prefix + "B2")
            + '</table:table-row></table:table>')


def document(nested):
    inner = table_xml("Inner", "i") if nested else ""
    return (HEAD + '<text:p>before</text:p>' + table_xml("Outer" if nested else "Table1", "", inner)
            + '<text:p>after</text:p>' + TAIL)


def check(ok, what):
    RESULTS.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + what, flush=True)
    return ok


# --- key input -------------------------------------------------------------------------------------------------------
if WINDOWS:
    import ctypes
    user32 = ctypes.windll.user32
    VK = {"ctrl": 0x11, "shift": 0x10, "a": 0x41, "z": 0x5A, "BackSpace": 0x08, "Delete": 0x2E, "Right": 0x27}
    EXTENDED = {"Delete", "Right"}
    ENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def office_pids(profile):
        script = ("Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | Where-Object { $_.CommandLine "
                  "-like '*%s*' } | ForEach-Object { $_.ProcessId }" % profile.replace("\\", "/"))
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                             timeout=60).stdout
        return [int(p) for p in out.split()]

    def window_of(pids, title):
        found = []

        def visit(hwnd, _):
            text, owner = ctypes.create_unicode_buffer(512), ctypes.c_ulong(0)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), text, 512)
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
            if user32.IsWindowVisible(ctypes.c_void_p(hwnd)) and owner.value in pids and title in text.value:
                found.append(hwnd)
            return True
        user32.EnumWindows(ENUM(visit), 0)
        return found[0] if found else None

    def key_event(name, up):
        flags = (2 if up else 0) | (1 if name in EXTENDED else 0)
        user32.keybd_event(VK[name], 0, flags, 0)
        time.sleep(0.05)

    def activate(hwnd):
        """Foreground as after Alt+Tab: a lone Shift first (Alt would show the ribbon's key tips), the input of the
        foreground thread shared while asking; True when GetForegroundWindow() is the window."""
        kernel32 = ctypes.windll.kernel32
        for _ in range(5):
            key_event("shift", False)
            key_event("shift", True)
            front = user32.GetForegroundWindow()
            theirs = user32.GetWindowThreadProcessId(ctypes.c_void_p(front), None) if front else 0
            mine = kernel32.GetCurrentThreadId()
            attached = bool(theirs) and theirs != mine and user32.AttachThreadInput(mine, theirs, True)
            try:
                user32.BringWindowToTop(ctypes.c_void_p(hwnd))
                user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            finally:
                if attached:
                    user32.AttachThreadInput(mine, theirs, False)
            time.sleep(1)
            if (user32.GetForegroundWindow() or 0) & 0xFFFFFFFF == int(hwnd) & 0xFFFFFFFF:
                return True
        return False


class Keys:
    """Sends key chords ("ctrl+a", "BackSpace") to the document window as real input events."""

    def __init__(self, office, frame):
        self.office, self.frame = office, frame
        self.target = None

    def focus(self):
        title = self.frame.Title
        if WINDOWS:
            hwnd = window_of(set(office_pids(self.office.profile)), title.split(".")[0])
            return bool(hwnd) and activate(hwnd)
        env = dict(os.environ, DISPLAY=self.office.display)
        found = []
        for wid in subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(self.office.pid), "--name", "."],
                                  env=env, capture_output=True, text=True, timeout=30).stdout.split():
            name = subprocess.run(["xdotool", "getwindowname", wid], env=env, capture_output=True, text=True,
                                  timeout=15).stdout.strip()
            if title.split(".")[0] in name:
                found.append(wid)
        if not found:
            print(f"note: no visible window titled {title!r}", flush=True)
            return False
        self.target = found[0]
        subprocess.run(["xdotool", "windowfocus", "--sync", self.target], env=env, capture_output=True, timeout=15)
        time.sleep(0.5)
        return True

    def press(self, chord, times=1):
        for _ in range(times):
            if WINDOWS:
                parts = chord.split("+")
                for part in parts:
                    key_event(part, False)
                for part in reversed(parts):
                    key_event(part, True)
            else:
                subprocess.run(["xdotool", "key", "--clearmodifiers", chord],
                               env=dict(os.environ, DISPLAY=self.office.display), check=False, timeout=15)
            time.sleep(0.6)
        time.sleep(0.8)


# --- office ----------------------------------------------------------------------------------------------------------
class WinOffice:
    """A visible office of this check only (own settled profile, scrubbed environment)."""

    def __init__(self, soffice, work):
        self.soffice, self.work = os.path.abspath(soffice), work
        self.profile = os.path.join(work, "profile")
        self.proc = self.ctx = None

    def start(self):
        import uno
        url = uno.systemPathToFileUrl(self.profile)
        shutil.rmtree(self.profile, ignore_errors=True)
        program = os.path.dirname(self.soffice).lower()
        env = {k: v for k, v in os.environ.items()
               if k not in ("URE_BOOTSTRAP", "UNO_PATH", "PYTHONHOME", "PYTHONPATH")}
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if p and os.path.normcase(p.rstrip("\\")).lower() != program)
        subprocess.run([self.soffice, "-env:UserInstallation=" + url, "--headless", "--norestore",
                        "--terminate_after_init"], env=env, timeout=300)
        xcu = os.path.join(self.profile, "user", "registrymodifications.xcu")
        items = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % i
                        for i in (("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                                  ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
                                  ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")))
        with open(xcu, encoding="utf-8") as handle:
            text = handle.read()
        with open(xcu, "w", encoding="utf-8") as handle:
            handle.write(text.replace("</oor:items>", items + "</oor:items>"))
        port = 2000 + os.getpid() % 20000
        self.proc = subprocess.Popen([self.soffice, "-env:UserInstallation=" + url, "--norestore", "--nologo",
                                      f"--accept=socket,host=127.0.0.1,port={port};urp;"], env=env)
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(120):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                return self
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(1)
        raise RuntimeError("the office did not start")

    def desktop(self):
        return self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def kill_leftovers(self):
        for pid in office_pids(self.profile):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def load(office, path):
    import uno
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = "OnMainThread", True
    return office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (prop,))


def goto_cell(doc, table, cell):
    xcell = doc.getTextTables().getByName(table).getCellByName(cell)
    doc.getCurrentController().getViewCursor().gotoRange(xcell.getStart(), False)
    time.sleep(0.5)


def selection_kind(doc):
    """What the selection is, as the API reports it (a table cell range for a whole-table selection)."""
    selection = doc.getCurrentController().getSelection()
    try:
        return selection.getImplementationName() + (f" {selection.getRangeName()}"
                                                    if hasattr(selection, "getRangeName") else "")
    except Exception as error:  # noqa: BLE001 - diagnostic only
        return type(error).__name__


def cell_text(doc, table, cell):
    return doc.getTextTables().getByName(table).getCellByName(cell).getString()


def cursor_paragraph(doc):
    cursor = doc.getCurrentController().getViewCursor()
    if cursor.TextTable is not None:
        return None
    para = cursor.getText().createTextCursorByRange(cursor.getStart())
    para.gotoStartOfParagraph(False)
    para.gotoEndOfParagraph(True)
    return para.getString()


def write_document(out, name, nested):
    """The case's document in a folder the office's user can write (Linux: the office runs as the build user; a
    file it cannot write opens read-only and the keys change nothing)."""
    folder = os.path.join(out, "docs")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".fodt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document(nested))
    if not WINDOWS:
        os.chmod(folder, 0o777)
        os.chmod(path, 0o666)
    return path


def run_case(office, case, out):
    doc = load(office, write_document(out, case, case == "nested"))
    time.sleep(3)
    if not check(not doc.isReadonly(), f"{case}: the document opened for editing"):
        doc.close(True)
        return
    frame = doc.getCurrentController().getFrame()
    keys = Keys(office, frame)
    try:
        if case == "nested":
            goto_cell(doc, "Inner", "B2")
        elif case == "partial":
            goto_cell(doc, "Table1", "A1")
        else:
            goto_cell(doc, "Table1", "B2")
        if not check(keys.focus(), f"{case}: the document window has the keyboard focus"):
            return
        tables = doc.getTextTables().getCount()
        if case == "partial":
            keys.press("shift+Right", 3)
        else:
            keys.press("ctrl+a", 2)
        print(f"note: {case}: selection before the key: {selection_kind(doc)}", flush=True)
        keys.press("Delete" if case == "delete" else "BackSpace")
        count = doc.getTextTables().getCount()
        if case == "backspace":
            check(tables == 1 and count == 0, f"{case}: Backspace deleted the table (tables {tables} -> {count})")
            check(cursor_paragraph(doc) == "after", f"{case}: the cursor is in the paragraph after the table "
                  f"({cursor_paragraph(doc)!r})")
            keys.press("ctrl+z")
            check(doc.getTextTables().getCount() == 1 and cell_text(doc, "Table1", "B2") == "B2",
                  f"{case}: one Ctrl+Z restores the table and its text")
        elif case == "delete":
            texts = [cell_text(doc, "Table1", c) for c in ("A1", "B1", "A2", "B2")]
            check(count == 1 and texts == ["", "", "", ""], f"{case}: Delete kept the table, cells {texts}")
        elif case == "partial":
            texts = [cell_text(doc, "Table1", c) for c in ("A1", "B1", "A2", "B2")]
            check(count == 1 and texts == ["", "", "A2", "B2"],
                  f"{case}: Backspace on A1:B1 kept the table, cells {texts}")
        else:
            check(tables == 2 and count == 1 and cell_text(doc, "Outer", "B2") == "B2",
                  f"{case}: only the inner table was deleted (tables {tables} -> {count})")
    finally:
        doc.setModified(False)


def quit_office(office, frame_doc):
    """.uno:Quit on the office's main thread, as File > Exit does."""
    ui = office.service("com.sun.star.ui.test.UITest")
    frame = frame_doc.getCurrentController().getFrame()
    threading.Thread(target=lambda: ui.executeCommandForProvider(".uno:Quit", frame), daemon=True).start()
    try:
        office.proc.wait(90)
    except subprocess.TimeoutExpired:
        pass
    check(office.proc.poll() == 0, f"the office quit with exit code 0 (got {office.proc.poll()})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", help="Linux: the office's instdir")
    parser.add_argument("--soffice", help="Windows: <instdir>\\program\\soffice.exe")
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY", ":147"))
    parser.add_argument("--cases", default="backspace,delete,partial,nested")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    if WINDOWS:
        sys.path.insert(0, os.path.dirname(os.path.abspath(args.soffice)))
        office = WinOffice(args.soffice, os.path.join(out, "work")).start()
    else:
        sys.path.insert(0, HERE)
        import hst_gui
        hst_gui.setup_uno(args.instdir)
        office = hst_gui.Office(args.instdir, os.path.join(out, "work"), hst_gui.free_port(), display=args.display,
                                lang="en_US.UTF-8")
        office.start()
        office.profile = os.path.join(office.workdir, "profile")
    last = None
    try:
        for case in args.cases.split(","):
            run_case(office, case, out)
        last = load(office, write_document(out, "quit", False))
        time.sleep(2)
        quit_office(office, last)
    finally:
        if WINDOWS:
            office.kill_leftovers()
        else:
            office.ctx = None  # quit already asked on the main thread: no terminate() over the bridge
            office.stop()
    return 0 if RESULTS and all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
