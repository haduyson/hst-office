#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Run an hst_gui based runtime check (written for Linux/Xvfb) on Windows, through hst_gui_windows.Office.

Usage (with the office's own python.exe; --ui needs an interactive session, see windows-own-session-task.ps1):
    <instdir>\\program\\python.exe tests\\runtime\\run-check-windows.py CHECK.py --instdir <instdir> --out <dir>
        [--port 2318] [--ui] [-- extra arguments of the check]
CHECK.py is a file of tests/runtime that accepts --display/--instdir/--out/--port (e.g. check-nd30-insertion-point.py).
--display is passed as "windows" and ignored. Without --ui the office runs --headless (no dialogs, no comment editing).
With --ui a stall is reported: every 90 s the Python stacks and the titles of this office's visible windows
(a modal dialog left open is the usual cause) go to stderr. The exit status is the check's.
"""
import argparse
import faulthandler
import importlib.util
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions", "hst-vietnamese-tools", "python")]


def office_windows(port):
    """Titles and classes of the visible top-level windows of the soffice.bin listening on `port`."""
    import ctypes
    listing = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | Where-Object "
                              "{ $_.CommandLine -match 'port=%d;' } | ForEach-Object { $_.ProcessId }" % port],
                             capture_output=True, text=True, check=False).stdout.split()
    pids, found, user32 = {int(p) for p in listing}, [], ctypes.windll.user32
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def each(hwnd, _):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            title, cls = ctypes.create_unicode_buffer(200), ctypes.create_unicode_buffer(100)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 200)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 100)
            found.append((title.value, cls.value))
        return True
    user32.EnumWindows(proto(each), 0)
    return found


def watch(port, every=90):
    faulthandler.dump_traceback_later(every, repeat=True, file=sys.stderr)

    def report():
        while True:
            time.sleep(every)
            print("WINDOWS %r" % (office_windows(port),), file=sys.stderr, flush=True)
    threading.Thread(target=report, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("check")
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2318)
    parser.add_argument("--ui", action="store_true", help="real UI in this (interactive) session")
    args, extra = parser.parse_known_args()
    os.environ["HST_WINDOWS_UI"] = "1" if args.ui else "0"
    import hst_gui_windows
    hst_gui_windows.install()
    if args.ui:
        watch(args.port)
    path = args.check if os.path.isabs(args.check) else os.path.join(HERE, args.check)
    spec = importlib.util.spec_from_file_location("check_under_windows", path)
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    sys.argv = [path, "--display", "windows", "--instdir", args.instdir, "--out", args.out, "--port", str(args.port)]
    sys.argv += [a for a in extra if a != "--"]
    return check.main()


if __name__ == "__main__":
    sys.exit(main())
