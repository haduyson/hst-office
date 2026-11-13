# SPDX-License-Identifier: AGPL-3.0-only
"""Regression check: the first Sheets document of a session, opened while a start-up dialog keeps the focus.

Usage (run with the office's own Python, any platform):
    <program>/python check-first-calc-under-dialog.py --program <instdir>/program --profile <empty dir> [--wait 25]

A fresh profile shows the welcome dialog over the Start Center. Sheets is then loaded over UNO as the session's
first document, so the Calc window does not take the focus from the dialog. ScInputHandler's 500 ms delay timer then
runs before Calc ever created the input line's edit engine; before hst-calc-input-delay-timer-no-engine.patch it
cleared the text of a missing engine and the office crashed (document recovery dialog, Windows 1.0.1).
PASS when, 10 s after the load, the office still answers a UNO call and wrote no fault note (builds with
hst-windows-silent-crash-note). Exit 1 on FAIL.
The profile directory is created by the office; the office is terminated at the end.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

import uno


def connect(pipe, seconds):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
        except Exception:  # noqa: BLE001 - the office is still starting
            time.sleep(0.5)
    return None


def answers(ctx, seconds):
    """True when the office's main loop still answers a UNO call (the toolkit needs it) within `seconds`."""
    result = []

    def ask():
        toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        result.append(toolkit.getTopWindowCount())

    worker = threading.Thread(target=ask, daemon=True)
    worker.start()
    worker.join(seconds)
    return bool(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--wait", type=int, default=25, help="seconds for the first start and its welcome dialog")
    args = parser.parse_args()
    pipe = "hst_first_calc_%d" % os.getpid()
    soffice = os.path.join(args.program, "soffice.exe" if sys.platform == "win32" else "soffice")
    url = uno.systemPathToFileUrl(os.path.abspath(args.profile))
    office = subprocess.Popen([soffice, "-env:UserInstallation=" + url, "--accept=pipe,name=%s;urp;" % pipe])
    ok, detail = False, ""
    try:
        time.sleep(args.wait)  # the first start restarts once; the welcome dialog opens over the Start Center
        ctx = connect(pipe, 60)
        if ctx is None:
            detail = "no UNO connection"
        else:
            desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            time.sleep(10)  # the delay timer fires after 500 ms
            note = os.path.join(args.profile, "user", "hst-office", "last-fault.txt")
            faulted = os.path.exists(note) and os.path.getsize(note) > 0  # builds with the fault note
            alive = office.poll() is None and answers(ctx, 20)  # a crash sits in its recovery dialog
            ok = doc is not None and alive and not faulted
            detail = "loaded=%s answering=%s fault note=%s" % (doc is not None, alive, faulted)
            try:
                desktop.terminate()
            except Exception:  # noqa: BLE001
                pass
    finally:
        try:
            office.wait(20)
        except subprocess.TimeoutExpired:  # a crashed office ignores terminate(): end its process tree
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(office.pid)], capture_output=True)
            office.kill()
    print("%s first Sheets document under the start-up dialog (%s)" % ("PASS" if ok else "FAIL", detail))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
