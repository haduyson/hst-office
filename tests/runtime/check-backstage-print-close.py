#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the ways a document ends while its File panel shows the Print page with a print job
(hst-backstage-print-job-ends-before-close.patch, hst-backstage-panel-keeps-focus.patch). One visible office per case
and application (Writer, Sheets), driven through UITest, run with the office's Python in the test user's session:
  sessionend  a changed document; what Windows does at log off: WM_QUERYENDSESSION (5 s) then WM_ENDSESSION(TRUE)
              to this office's windows, AutoRecovery on. The office must end with exit code 0, no crash dump.
  macroclose  XCloseable.close(True) on the document from a Python macro of the profile (main thread): no crash,
              the office stays (Start Center).
  macroterm   Desktop.terminate() from the same macro (the updater's "Cập nhật ngay" quits this way): exit code 0.
  quit        File > Thoát (.uno:Quit): exit code 0.
  closex      the window's X (SC_CLOSE): the document closes, the office stays.
  ctrlw / esc the window activated again (as after Alt+Tab), then Ctrl+W: the document closes; Esc: the panel
              closes and the document stays.
A crash counts by a new soffice.bin dump in %LOCALAPPDATA%\\CrashDumps (Windows Error Reporting LocalDumps).
Calls over the UNO bridge thread (Desktop.terminate() from this script) are not a case: they run off the main
thread (common rules, UNO load from test harnesses).
Usage: <office python> check-backstage-print-close.py --soffice PATH --out DIR [--cases a,b] [--apps swriter,scalc]
Exit 1 on a failure.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("cancel_back", os.path.join(HERE, "check-backstage-print-cancel-back.py"))
CB = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CB)
user32 = ctypes.windll.user32
DUMPS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps")
WM_SYSCOMMAND, SC_CLOSE, WM_QUERYENDSESSION, WM_ENDSESSION, ENDSESSION_LOGOFF = 0x112, 0xF060, 0x11, 0x16, 0x80000000
VK_CONTROL, VK_W, VK_ESCAPE = 0x11, 0x57, 0x1B
CASES = ("sessionend", "macroclose", "macroterm", "quit", "closex", "ctrlw", "esc")
MACRO = """
def close_doc(*args):
    XSCRIPTCONTEXT.getDocument().close(True)
def terminate(*args):
    XSCRIPTCONTEXT.getDesktop().terminate()
"""
ENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def office_pids(work):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | ? { $_.CommandLine -like '*"
                          + os.path.basename(work) + "/profile*' } | % { $_.ProcessId }"],
                         capture_output=True, text=True, timeout=60).stdout.split()
    return [int(p) for p in out]


def windows_of(pids, title=None):
    """The visible top-level VCL windows of these processes (with `title` in their title, when given)."""
    found = []

    def visit(hwnd, _):
        cls, text, owner = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(512), ctypes.c_ulong(0)
        user32.GetClassNameW(hwnd, cls, 256)
        user32.GetWindowTextW(hwnd, text, 512)
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
        if (user32.IsWindowVisible(hwnd) and cls.value.startswith("SAL") and owner.value in pids
                and (title is None or title in text.value)):
            found.append(hwnd)
        return True
    user32.EnumWindows(ENUM(visit), 0)
    return found


def keys(*strokes):
    for vk, up in strokes:
        user32.keybd_event(vk, 0, 2 if up else 0, 0)
        time.sleep(0.05)


def end_session(pids):
    send = user32.SendMessageTimeoutW
    send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t, ctypes.c_uint, ctypes.c_uint,
                     ctypes.POINTER(ctypes.c_size_t)]
    hwnds = windows_of(pids)
    for msg, wparam in ((WM_QUERYENDSESSION, 0), (WM_ENDSESSION, 1)):
        for hwnd in hwnds:
            result = ctypes.c_size_t(0)
            send(hwnd, msg, wparam, ENDSESSION_LOGOFF, 0, 5000, ctypes.byref(result))


def new_dumps(pids):
    return [f for p in pids for f in [f"soffice.bin.{p}.dmp"] if os.path.exists(os.path.join(DUMPS, f))]


def start(case, work, soffice):
    real_popen = subprocess.Popen
    if case == "sessionend":  # AutoRecovery on: the session end stores the documents (the product's way)
        subprocess.Popen = lambda argv, **kw: real_popen([a for a in argv if a != "--norestore"], **kw)
    try:
        office = CB.BASE.VisibleOffice(soffice, work, None)
    finally:
        subprocess.Popen = real_popen
    scripts = os.path.join(work, "profile", "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    with open(os.path.join(scripts, "hstprintclose.py"), "w", encoding="utf-8") as handle:
        handle.write(MACRO)
    return office


def run(case, app, out, soffice):
    work = os.path.join(out, f"{case}-{app}")
    office = start(case, work, soffice)
    tag, doc = f"{case} {app}", None
    try:
        office.close_welcome()
        doc = CB.load(office, app)
        frame = doc.getCurrentController().getFrame()
        CB.FRAME[:] = [frame]
        title = frame.Title
        pids = office_pids(work)
        time.sleep(3)
        if case == "sessionend":
            if app == "swriter":
                doc.getText().setString("đã sửa")
            else:
                doc.Sheets.getByIndex(0).getCellByPosition(0, 0).setString("đã sửa")
        office.ui.executeCommandForProvider(".uno:Print", frame)
        if CB.panel_button(office, "back") is None:
            CB.check(False, f"{tag}: the Print page opens")
            return
        time.sleep(3)  # the preview is painted on idle
        hwnd = (windows_of(pids, title) or [None])[0]
        if case == "sessionend":
            end_session(pids)
        elif case in ("macroclose", "macroterm"):
            url = ("vnd.sun.star.script:hstprintclose.py$" + ("close_doc" if case == "macroclose" else "terminate")
                   + "?language=Python&location=user")
            threading.Thread(target=lambda: office.ui.executeCommandForProvider(url, frame), daemon=True).start()
        elif case == "quit":
            threading.Thread(target=lambda: office.ui.executeCommandForProvider(".uno:Quit", frame), daemon=True).start()
        elif case == "closex":
            user32.PostMessageW(ctypes.c_void_p(hwnd), WM_SYSCOMMAND, SC_CLOSE, 0)
        else:  # the window activated again, then the key
            user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            time.sleep(1)
            keys(*([(VK_CONTROL, 0), (VK_W, 0), (VK_W, 1), (VK_CONTROL, 1)] if case == "ctrlw"
                   else [(VK_ESCAPE, 0), (VK_ESCAPE, 1)]))
        time.sleep(12)
        code = office.proc.poll()
        if case in ("sessionend", "macroterm", "quit"):
            CB.check(code == 0, f"{tag}: the office ended with exit code 0 (got {code})")
        else:
            CB.check(code is None and bool(office_pids(work)), f"{tag}: the office keeps running (exit {code})")
        if case in ("macroclose", "closex", "ctrlw"):
            CB.check(not windows_of(pids, title), f"{tag}: the document window closed")
        if case == "esc":
            CB.check(CB.is_closed(office, 3), f"{tag}: Esc closed the File panel")
            CB.check(bool(windows_of(pids, title)), f"{tag}: the document stays")
        dumps = new_dumps(pids)
        CB.check(not dumps, f"{tag}: no crash dump {dumps}")
    finally:
        try:
            if doc is not None:
                doc.setModified(False)
        except Exception:  # noqa: BLE001 - the document may be gone
            pass
        office.stop()
        if office.proc.poll() is None:
            office.proc.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-close-"))
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--apps", default="swriter,scalc")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    for case in args.cases.split(","):
        for app in args.apps.split(","):
            try:
                run(case, app, out, args.soffice)
            except Exception as error:  # noqa: BLE001 - one case's failure is its result
                CB.check(False, f"{case} {app}: run ({type(error).__name__}: {error})")
    print(f"{len(CB.failures)} failure(s)", flush=True)
    sys.exit(1 if CB.failures else 0)


if __name__ == "__main__":
    main()
