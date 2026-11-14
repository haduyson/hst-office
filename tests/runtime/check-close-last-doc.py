#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Closing the last document over UNO keeps the office running (macOS: no crash restoring the default menu).

Run with the office's own Python (it needs pyuno), headless:
  Linux: <instdir>/program/python tests/runtime/check-close-last-doc.py --program <instdir>/program
  macOS: "/Applications/HST Office.app/Contents/Resources/python" tests/runtime/check-close-last-doc.py \\
             --program "/Applications/HST Office.app/Contents/MacOS"

Each case creates a document over UNO (the only document, so its menubar is the current one), closes it, and
then asks the office something: a crash while the menubar goes away (macOS: AquaSalMenu::setDefaultMenu, run on
the main thread on behalf of the UNO thread) shows up as a disposed bridge. --launcher runs the office through a
wrapper (for example a debugger script) that gets the soffice path and arguments. Exit 1 when a case fails.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

CASES = [
    ("Writer, close(True)", "private:factory/swriter", "close"),
    ("Calc, close(True)", "private:factory/scalc", "close"),
    ("Writer again, close(True)", "private:factory/swriter", "close"),
    ("Writer, dispose()", "private:factory/swriter", "dispose"),
    ("Impress, close(True)", "private:factory/simpress", "close"),
]


def connect(port, proc):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(180):
        if proc.poll() is not None:
            raise RuntimeError("office exited with %s before it was reachable" % proc.returncode)
        try:
            return resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(1)
    raise RuntimeError("office not reachable")


def run_case(desktop, url, how):
    doc = desktop.loadComponentFromURL(url, "_blank", 0, ())
    if url.endswith("swriter"):
        doc.Text.String = "NOI-DUNG"
    if how == "close":
        doc.close(True)
    else:
        doc.dispose()
    time.sleep(1)  # let the main thread run what the close posted
    return desktop.getFrames().getCount()  # any call: a crashed office raises DisposedException here


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True, help="folder with soffice (Linux program/, macOS Contents/MacOS)")
    ap.add_argument("--port", type=int, default=22236)
    ap.add_argument("--launcher", default="", help="optional wrapper command placed before soffice")
    args = ap.parse_args()
    work = tempfile.mkdtemp(prefix="hst-close-last-doc-")
    cmd = [os.path.join(args.program, "soffice"), "--headless", "--norestore", "--nologo",
           "-env:UserInstallation=file://" + os.path.join(work, "profile"),
           "--accept=socket,host=127.0.0.1,port=%d;urp;" % args.port]
    if args.launcher:
        cmd = args.launcher.split() + cmd
    proc = subprocess.Popen(cmd)
    failed = 0
    try:
        ctx = connect(args.port, proc)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        for label, url, how in CASES:
            try:
                frames = run_case(desktop, url, how)
                print("PASS %s (frames left: %d)" % (label, frames), flush=True)
            except Exception as exc:  # noqa: BLE001 - DisposedException etc.: the office died
                failed += 1
                print("FAIL %s (%s: %s)" % (label, type(exc).__name__, exc), flush=True)
                break
        if not failed:
            desktop.terminate()
    finally:
        try:
            proc.wait(60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(10)
    print("close last document: %d cases, %d failed, office exit %s" % (len(CASES), failed, proc.returncode))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
