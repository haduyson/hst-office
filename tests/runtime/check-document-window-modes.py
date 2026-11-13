# SPDX-License-Identifier: AGPL-3.0-only
"""Check the window mode of each application (tabs or separate windows) on a real GUI build (Xvfb).

Usage: python3 tests/runtime/check-document-window-modes.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/document-window-modes] [--display :97]

The profile starts with HST Writer, HST Slides and HST PDF set to separate windows, HST Sheets and HST Draw to
tabs. A second soffice on the same profile stands for the launchers and the file manager. Asserts:
  1. Launchers/files from outside: two documents of an application set to separate windows get two windows,
     of an application set to tabs one window; the Start Center stays (HST Office window).
  2. Inside a separate HST Writer window, File > New opens another window; Move to New Window does nothing.
  3. HST Office window: documents created from it are its tabs, whatever the application's mode.
  4. Every mode inverted, then "Apply to the open windows" (.uno:DocumentWindowMode ApplyToOpenWindows):
     separate windows merge, tab windows split, the HST Office window keeps its tabs; every document is the
     same object, still modified, its text intact (nothing reloaded, closed or saved).
  5. After a restart the inverted modes are still set and still route documents.
Screenshots and evidence.json go to --out. Exit 1 when any check fails.
"""
import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from importlib import import_module  # noqa: E402

base = import_module("check-module-windows")  # Checker, module_of: the same harness
from document_window_modes_helpers import open_twice, snapshot, touch_all  # noqa: E402
ROOT = hst_gui.ROOT
PORT = 21994  # deterministic per check (see hst_gui)
MISC = "/org.openoffice.Office.Common/Misc"
APPS = (("Writer", "--writer"), ("Calc", "--calc"), ("Impress", "--impress"), ("Draw", "--draw"), ("Pdf", None))
START_TABS = {"Writer": False, "Calc": True, "Impress": False, "Draw": True, "Pdf": False}


def run(args):
    hst_gui.setup_uno(args.instdir)
    config = [(MISC, f"DocumentTabs{app}", "true" if tabs else "false") for app, tabs in START_TABS.items()]
    config.append(("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"))  # modal template chooser
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False, config=config)
    office.start()
    c = base.Checker(office, args.out)
    try:
        c.wait(lambda: len(c.windows()) == 1, 60)
        start = c.frames()[0]
        windows = 1
        # 1. Two documents of every application from outside.
        for app, flag in APPS:
            before = len(c.frames())
            open_twice(c, office, app, flag)
            windows += 1 if START_TABS[app] else 2
            c.check(f"{app} ({'tabs' if START_TABS[app] else 'separate'}): two documents from outside",
                    c.wait(lambda: len(c.frames()) == before + 2 and len(c.windows()) == windows),
                    repr(c.windows()))
        c.check("Start Center kept in its HST Office window", base.module_of(office, start) == "StartModule")
        c.shot("01-per-application-modes.png")

        # 2. Inside a separate HST Writer window.
        writer = [f for f in c.frames() if base.module_of(office, f) == "TextDocument"]
        c.dispatch(writer[0], "private:factory/swriter", "_blank")
        windows += 1
        c.check("separate HST Writer window: File > New opens another window",
                c.wait(lambda: len(c.windows()) == windows), repr(c.windows()))
        touch_all(office)
        office.dispatch(writer[0], ".uno:DetachDocumentTab")
        time.sleep(2)
        c.check("separate HST Writer window: Move to New Window does nothing", len(c.windows()) == windows)

        # 3. HST Office window: tabs whatever the application's mode.
        c.dispatch(start, "private:factory/swriter", "_default")
        c.wait(lambda: base.module_of(office, start) == "TextDocument")
        touch_all(office)
        c.dispatch(start, "private:factory/swriter", "_blank")
        c.check("HST Office window: a new text document is its tab although HST Writer is set to separate",
                c.wait(lambda: sum(base.module_of(office, f) == "TextDocument" for f in c.frames()) == 5)
                and len(c.windows()) == windows, repr(c.windows()))
        touch_all(office)
        for doc in office.desktop().getComponents():
            if hasattr(doc, "getText"):
                doc.getText().setString(f"Nội dung chưa lưu {doc.RuntimeUID}")
        c.shot("02-office-window-exception.png")

        # 4. Invert every mode and apply to the open windows.
        before = snapshot(office)
        frames = len(c.frames())
        for app, tabs in START_TABS.items():
            office.set_config(MISC, f"DocumentTabs{app}", not tabs)
        from com.sun.star.beans import PropertyValue
        apply = PropertyValue()
        apply.Name, apply.Value = "ApplyToOpenWindows", True
        office.dispatch(c.frames()[-1], ".uno:DocumentWindowMode", (apply,))
        # office window 1; Writer now tabs (3 windows -> 1); every other app: 2 <-> 1
        expected = 1 + sum(1 if not tabs else 2 for tabs in START_TABS.values())
        c.check("apply: separate windows merged, tab windows split, HST Office window kept",
                c.wait(lambda: len(c.windows()) == expected) and len(c.frames()) == frames,
                f"{len(c.windows())} windows, expected {expected}: {c.windows()!r}")
        c.check("apply: every document kept, still modified, text intact (no reload, no loss)",
                snapshot(office) == before, f"{len(before)} documents")
        c.shot("03-after-apply.png")
        windows = expected
        # View > Tabs or Separate Windows...: the (modal) Options page with the window modes
        threading.Thread(target=office.dispatch, args=(c.frames()[0], ".uno:DocumentWindowMode"), daemon=True).start()
        time.sleep(5)
        c.shot("04-options-page.png")
        page = [w for w, n in hst_gui.toplevels(office.display, office.pid) if n.startswith("Tùy chọn")]
        c.check("View > Tabs or Separate Windows... opens the Options page", bool(page), repr(page))
        for wid in page:  # no window manager: close it as its title-bar X would (Cancel)
            hst_gui.send_close_request(wid, office.display)
        c.wait(lambda: not any(n.startswith("Tùy chọn") for _w, n in hst_gui.toplevels(office.display, office.pid)))
    finally:
        for doc in office.desktop().getComponents():
            try:
                doc.setModified(False)
            except Exception:  # noqa: BLE001
                pass
        office.stop()

    # 5. Restart: the inverted modes stay and route.
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False)
    office.start(fresh=False)
    c2 = base.Checker(office, args.out)
    try:
        c2.wait(lambda: len(c2.windows()) == 1, 60)
        time.sleep(8)  # a crash/hang of the first session would show its error report question now
        c2.check("restart: the first session had ended normally (no other window)", len(c2.windows()) == 1,
                 repr(c2.windows()))
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", MISC
        access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,))
        kept = {app: access.getPropertyValue(f"DocumentTabs{app}") for app in START_TABS}
        c2.check("restart: the modes chosen before are kept", all(kept[a] != t for a, t in START_TABS.items()),
                 repr(kept))
        open_twice(c2, office, "Calc", "--calc")  # HST Sheets now separate
        c2.check("restart: HST Sheets documents still open in separate windows",
                 c2.wait(lambda: len(c2.windows()) == 3), repr(c2.windows()))
        c2.shot("05-after-restart.png")
    finally:
        for doc in office.desktop().getComponents():
            try:
                doc.setModified(False)
            except Exception:  # noqa: BLE001
                pass
        office.stop()
    results = c.results + c2.results
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/document-window-modes"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
