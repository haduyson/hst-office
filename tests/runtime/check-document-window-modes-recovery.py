# SPDX-License-Identifier: AGPL-3.0-only
"""Crash recovery with per-application window modes on a real GUI build (Xvfb, xdotool).

Usage: python3 tests/runtime/check-document-window-modes-recovery.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/document-window-modes-recovery] [--display :97]

HST Writer is set to separate windows, HST Sheets to tabs. Two text documents (two windows) and two
spreadsheets (one window, two tabs) are edited; then HST Sheets is switched to separate windows without
applying it to the open windows. After autosave and a hard kill (SIGKILL), the restarted office recovers:
  1. every document comes back, with its unsaved text;
  2. one window per document: the HST Writer windows as they were, the saved HST Sheets tab window split
     because HST Sheets is now set to separate windows.
Screenshots and evidence.json go to --out. Exit 1 when any check fails.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from importlib import import_module  # noqa: E402

base = import_module("check-module-windows")
from document_window_modes_helpers import open_twice  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 21995  # deterministic per check (see hst_gui)
MISC = "/org.openoffice.Office.Common/Misc"


def documents(office):
    """Title -> text (Writer) or A1 (Sheets) of every recovered document."""
    result = {}
    for doc in office.desktop().getComponents():
        if hasattr(doc, "getText"):
            result[doc.getCurrentController().getFrame().Title] = doc.getText().getString()
        elif hasattr(doc, "getSheets"):
            result[doc.getCurrentController().getFrame().Title] = \
                doc.getSheets().getByIndex(0).getCellByPosition(0, 0).getString()
    return result


def press_first_button(office):
    """Recovery dialog: its first button ("Khôi phục mục đã chọn", then "Hoàn tất")."""
    dialogs = [(w, n) for w, n in hst_gui.toplevels(office.display, office.pid) if " — HST " not in n and n]
    if not dialogs:
        return False
    info = subprocess.run(["xwininfo", "-display", office.display, "-id", dialogs[0][0]],
                          capture_output=True, text=True).stdout
    x, y, width, height = (int(re.search(pattern, info).group(1)) for pattern in (
        r"Absolute upper-left X:\s+(-?\d+)", r"Absolute upper-left Y:\s+(-?\d+)", r"Width:\s+(\d+)",
        r"Height:\s+(\d+)"))
    env = dict(os.environ, DISPLAY=office.display)
    subprocess.run(["xdotool", "mousemove", str(x + width - 286), str(y + height - 26), "click", "1"],
                   env=env, check=False, timeout=20)
    return True


def run(args):
    hst_gui.setup_uno(args.instdir)
    config = [(MISC, "DocumentTabsWriter", "false"), (MISC, "DocumentTabsCalc", "true")]
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False, config=config,
                            restore=True)
    office.start()
    c = base.Checker(office, args.out)
    try:
        c.wait(lambda: len(c.windows()) == 1, 60)
        open_twice(c, office, "Writer", "--writer")
        open_twice(c, office, "Calc", "--calc")
        c.wait(lambda: len(c.frames()) == 5)
        for number, doc in enumerate(office.desktop().getComponents()):
            if hasattr(doc, "getText"):
                doc.getText().setString(f"Văn bản chưa lưu {number}")
            elif hasattr(doc, "getSheets"):
                doc.getSheets().getByIndex(0).getCellByPosition(0, 0).setString(f"Bảng chưa lưu {number}")
        before = documents(office)
        c.check("before the crash: two HST Writer windows and one HST Sheets window with two tabs",
                len(c.windows()) == 4 and len(before) == 4, repr(c.windows()))
        office.set_config(MISC, "DocumentTabsCalc", False)  # not applied to the open windows
        office.set_config("/org.openoffice.Office.Recovery/AutoSave", "TimeIntervall", 1)
        time.sleep(75)  # adaptive autorecovery skips documents changed less than one interval ago
        from com.sun.star.util import URL
        recovery = office.ctx.getValueByName("/singletons/com.sun.star.frame.theAutoRecovery")
        url = URL()
        url.Complete = "vnd.sun.star.autorecovery:/doAutoSave"
        recovery.dispatch(office.service("com.sun.star.util.URLTransformer").parseStrict(url)[1], ())
        time.sleep(10)
        c.shot("10-before-crash.png")
        os.kill(office.pid, signal.SIGKILL)
        time.sleep(3)
        office.ctx = None
        office.start(fresh=False)
        for _ in range(2):  # start the recovery, then finish it
            c.wait(lambda: any(" — HST " not in n and n for _w, n in hst_gui.toplevels(office.display, office.pid)),
                   40)
            if not press_first_button(office):
                break
            time.sleep(15)
        time.sleep(15)
        after = documents(office)
        c.check("recovery: every document back with its unsaved content",
                sorted(after.values()) == sorted(before.values()), repr(after))
        c.check("recovery: one window per document (HST Sheets now separate, its tab window split)",
                c.wait(lambda: len([n for _w, n in c.windows() if " — HST " in n]) == 4), repr(c.windows()))
        c.shot("11-after-recovery.png")
    finally:
        try:
            for doc in office.desktop().getComponents():
                doc.setModified(False)
        except Exception:  # noqa: BLE001 - the bridge may be gone after a failed recovery
            pass
        office.stop()
    failed = sum(r["status"] == "FAIL" for r in c.results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": c.results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/document-window-modes-recovery"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
