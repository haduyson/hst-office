#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""A crash while the last document window closes must not leave a hung office (owner report, Windows 1.0.1: the
emergency save dialog with an empty list stayed on screen and only the Task Manager ended the office).

Run with the office's own python.exe, in the test user's own session (tests/runtime/windows-own-session-task.ps1):
  python.exe check-close-crash-handler-windows.py --install <dir with program\\> --out <dir> [--runs 6]

Every run: the owner's save settings (autosave every minute + "always autosave the document instead", backup copy in
the document's folder, .docx default), a saved .docx changed and autosaved in place, then the UNO bridge is dropped
and the Writer window is closed (WM_CLOSE to its own HWND) with an access violation injected into the main thread
the moment that window is destroyed (inject-main-thread-fault.ps1): the office's crash handler runs while the office
ends. PASS when the process ends by itself within 40 s, answering a recovery dialog with Enter if one shows; FAIL
when it is still there (hung handler: the configuration flush waited for a lock held by the faulted thread).
Last check ("open"): the same fault while the document is open: the emergency save dialog lists it, Enter ends the
process (restart), and the restarted office offers the document for recovery.
Exit 1 when a check fails.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import close_crash_windows as cw  # noqa: E402

RESULTS = []


def record(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, " (%s)" % detail if detail else ""), flush=True)


def saved_and_autosaved(off):
    from com.sun.star.beans import PropertyValue
    import uno
    desktop = off.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", off.ctx)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_default", 0, ())
    doc.Text.insertString(doc.Text.End, "synthetic text", False)
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", "MS Word 2007 XML"
    doc.storeAsURL(uno.systemPathToFileUrl(os.path.join(off.docs, "t.docx")), (arg,))
    doc.Text.insertString(doc.Text.End, " changed", False)
    end = time.time() + 120
    while doc.isModified() and time.time() < end:  # the user autosave stores the .docx in place
        time.sleep(2)
    return not doc.isModified()


def settle(off, timeout=40):
    """Wait until this run's office is gone; Enter on a recovery dialog of ours. 'gone', 'restarted' or a hang."""
    first = cw.pids(off.work, "soffice.bin")
    end, answered = time.time() + timeout, set()
    while time.time() < end:
        own = cw.pids(off.work)
        if not own:
            return "gone"
        binaries = cw.pids(off.work, "soffice.bin")
        if binaries and not binaries & first:
            return "restarted"
        for hwnd, title in cw.windows(own):
            if cw.RECOVERY.search(title) and hwnd not in answered and cw.responsive(hwnd):
                time.sleep(2)
                if cw.press_enter(hwnd):
                    answered.add(hwnd)
        time.sleep(2)
    own = cw.pids(off.work)
    shown = cw.windows(own)
    return "hung: alive, windows %s, responsive %s" % ([t for _h, t in shown], [cw.responsive(h) for h, _t in shown])


def close_run(program, out, index):
    off = cw.Office(program, os.path.join(out, "close-%d" % index))
    off.prepare()
    off.start()
    if not saved_and_autosaved(off):
        record("close %d: autosave stored the .docx" % index, False)
        off.kill()
        return
    off.end_startup_dialogs(settle=5)
    shown = cw.windows(cw.pids(off.work))
    writer = [h for h, t in shown if "Writer" in t]
    if len(shown) != 1:
        print("     windows before the close: %s" % [t for _h, t in shown], flush=True)
    off.drop_bridge()
    injector = off.arm_fault(writer[0])
    if not cw.guard.close_window(writer[0]):
        record("close %d: WM_CLOSE posted to the Writer window" % index, False, cw.guard.refusal(writer[0], cw.guard.win32()))
    state = settle(off)
    try:
        injected = injector.communicate(timeout=30)[0].strip().splitlines()[-1:]
    except subprocess.TimeoutExpired:
        injector.kill()
        injected = ["not fired"]
    note = off.fault_note().splitlines()
    record("close %d: the office ends after a crash while closing" % index, state in ("gone", "restarted"),
           "%s; injector: %s; note: %s" % (state, injected, note[:1] + note[-1:]))
    off.kill()


def open_run(program, out):
    off = cw.Office(program, os.path.join(out, "open"))
    off.prepare()
    off.start()
    saved_and_autosaved(off)
    off.drop_bridge()
    off.arm_fault().communicate(timeout=60)
    state = settle(off, 60)
    record("open: emergency save dialog answered, office restarted", state == "restarted", state)
    found = None
    end = time.time() + 120
    while not found and time.time() < end:
        found = [t for _h, t in cw.windows(cw.pids(off.work)) if cw.RECOVERY.search(t)]
        time.sleep(2)
    record("open: the restarted office offers the document for recovery", bool(found))
    off.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs", type=int, default=6)
    args = parser.parse_args()
    program = os.path.join(args.install, "program")
    for index in range(args.runs):
        close_run(program, args.out, index)
    open_run(program, args.out)
    failed = RESULTS.count(False)
    print("check-close-crash-handler-windows: %d checks, %d failed" % (len(RESULTS), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
