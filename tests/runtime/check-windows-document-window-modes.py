#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Window mode of each application (tabs or separate windows) on an INSTALLED HST Office (Windows, real desktop).

The Windows counterpart of check-document-window-modes.py. Usage:
  "<install>\\program\\python.exe" tests/runtime/check-windows-document-window-modes.py --install DIR --out DIR
Starts with HST Writer, Slides and PDF set to separate windows, HST Sheets and Draw to tabs. A second soffice.exe on
the same profile stands for the Start menu shortcuts and a double-click. Asserts the windows per application, the
HST Office window exception, "Apply to the open windows" with unsaved documents, the taskbar identity
(AppUserModelID) of every window, and that the modes survive a restart. Evidence: <out>/results.json and PNGs.
Exit 1 on any FAIL. Never touches an office it did not start (refuses to run while another soffice.bin runs).
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402
from pdf_fixture import tiny_pdf  # noqa: E402
from windows_window_modes_helpers import MISC, aumid, seed, set_config  # noqa: E402

APPS = (("Writer", "--writer"), ("Calc", "--calc"), ("Impress", "--impress"), ("Draw", "--draw"), ("Pdf", None))
START_TABS = {"Writer": False, "Calc": True, "Impress": False, "Draw": True, "Pdf": False}
SEED = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
        (MISC, "ShowTipOfTheDay", "false"), ("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]


class Check:
    def __init__(self, office, out):
        self.office, self.out, self.results = office, out, []

    def check(self, name, ok, detail=""):
        self.results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(("PASS  " if ok else "FAIL  ") + name + "  " + str(detail), flush=True)

    def windows(self):
        return [(h, t) for h, _c, t, _r in wg.office_windows() if " — HST " in t or t.startswith("HST Office")]

    def frames(self):
        access = self.office.desktop.getFrames()
        return [access.getByIndex(i) for i in range(access.getCount())]

    def wait(self, predicate, timeout=40):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - frames come and go
                pass
            time.sleep(0.5)
        return False

    def second(self, *args):
        subprocess.run([os.path.join(self.office.program, "soffice.exe"), "-env:UserInstallation=" + self.office.url,
                        *args], timeout=120, check=False)

    def touch(self):
        for doc in self.office.desktop.getComponents():
            try:
                doc.setModified(True)
            except Exception:  # noqa: BLE001 - HST PDF has no modified state
                pass

    def open_twice(self, flag, pdf_dir):
        for n in (1, 2):
            if flag:
                self.second(flag)
            else:
                pdf = os.path.join(pdf_dir, "tep-%d.pdf" % n)
                tiny_pdf(pdf, "HST PDF %d" % n)
                self.second(pdf)
            time.sleep(4)
            self.touch()


def run(args):
    if wg.WinOffice.bin_pids():
        print("another office runs: refusing to start (it may belong to someone else)")
        return 2
    profile = os.path.join(args.out, "profile")
    office = wg.WinOffice(args.install, profile, args.port, os.path.join(args.out, "logs"))
    office.start(fresh=True)  # the first start initialises the profile
    time.sleep(10)
    office.stop()
    seed(profile, SEED + [(MISC, "DocumentTabs" + a, "true" if t else "false") for a, t in START_TABS.items()])
    office.start()
    c = Check(office, args.out)
    try:
        c.wait(lambda: len(c.windows()) == 1, 90)
        windows = 1
        for app, flag in APPS:
            before = len(c.frames())
            c.open_twice(flag, args.out)
            windows += 1 if START_TABS[app] else 2
            c.check("%s (%s): two documents from outside" % (app, "tabs" if START_TABS[app] else "separate"),
                    c.wait(lambda: len(c.frames()) == before + 2 and len(c.windows()) == windows), c.windows())
        ids = {t: aumid(h) for h, t in c.windows()}
        c.check("taskbar: every module window has its application's id (HST PDF its own), the Start Center HST "
                "Office's", all(i.startswith("HASONTECH.HSTOffice.") for i in ids.values())
                and sum(i.endswith(".Pdf") for i in ids.values()) == 2
                and any(i.endswith(".Startcenter") for i in ids.values())
                and sum(i.endswith(".Writer") for i in ids.values()) == 2, ids)
        wg.screenshot(os.path.join(args.out, "01-windows-per-application.png"))
        start = next(f for f in c.frames() if f.Title.startswith("HST Office"))
        start.activate()
        office.service("com.sun.star.frame.DispatchHelper").executeDispatch(start, "private:factory/swriter",
                                                                             "_default", 0, ())
        time.sleep(4)
        c.touch()
        office.service("com.sun.star.frame.DispatchHelper").executeDispatch(start, "private:factory/swriter",
                                                                             "_blank", 0, ())
        c.check("HST Office window: a new text document is its tab although HST Writer is separate",
                c.wait(lambda: len(c.windows()) == windows), c.windows())
        c.touch()
        for doc in office.desktop.getComponents():
            if hasattr(doc, "getText"):
                doc.getText().setString("Nội dung chưa lưu %s" % doc.RuntimeUID)
        before = {d.RuntimeUID: (d.isModified(), d.getText().getString() if hasattr(d, "getText") else "")
                  for d in office.desktop.getComponents() if hasattr(d, "RuntimeUID")}
        for app, tabs in START_TABS.items():
            set_config(office, "DocumentTabs" + app, not tabs)
        import uno
        apply = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        apply.Name, apply.Value = "ApplyToOpenWindows", True
        office.service("com.sun.star.frame.DispatchHelper").executeDispatch(
            c.frames()[-1], ".uno:DocumentWindowMode", "", 0, (apply,))
        expected = 1 + sum(1 if not tabs else 2 for tabs in START_TABS.values())
        c.check("apply: separate windows merged, tab windows split, HST Office window kept",
                c.wait(lambda: len(c.windows()) == expected), "%d expected: %r" % (expected, c.windows()))
        after = {d.RuntimeUID: (d.isModified(), d.getText().getString() if hasattr(d, "getText") else "")
                 for d in office.desktop.getComponents() if hasattr(d, "RuntimeUID")}
        c.check("apply: every document kept, still modified, text intact", after == before, len(before))
        wg.screenshot(os.path.join(args.out, "02-after-apply.png"))
        office.dispatch_async(c.frames()[0], ".uno:DocumentWindowMode")  # View > Tabs or Separate Windows...
        page = wg.find_window(lambda t: t.startswith("Tùy chọn"), 30)
        c.check("View > Tabs or Separate Windows... opens the Options page", page is not None, page and page[2])
        wg.screenshot(os.path.join(args.out, "04-options-page.png"))
        if page:
            ctypes.windll.user32.PostMessageW(page[0], 0x0010, 0, 0)  # WM_CLOSE: Cancel
            c.wait(lambda: wg.find_window(lambda t: t.startswith("Tùy chọn"), 1) is None, 30)
    finally:
        for doc in office.desktop.getComponents():
            try:
                doc.setModified(False)
            except Exception:  # noqa: BLE001
                pass
        c.check("first session quits normally", office.stop() == 0)
    office.start()
    try:
        c.wait(lambda: len(c.windows()) == 1, 90)
        kept = {a: office.config(MISC, "DocumentTabs" + a) for a in START_TABS}
        c.check("restart: the modes chosen before are kept", all(kept[a] != t for a, t in START_TABS.items()), kept)
        c.open_twice("--calc", args.out)
        c.check("restart: HST Sheets documents open in separate windows", c.wait(lambda: len(c.windows()) == 3),
                c.windows())
        wg.screenshot(os.path.join(args.out, "03-after-restart.png"))
    finally:
        for doc in office.desktop.getComponents():
            try:
                doc.setModified(False)
            except Exception:  # noqa: BLE001
                pass
        office.stop()
    failed = sum(r["status"] == "FAIL" for r in c.results)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": c.results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2171)
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
