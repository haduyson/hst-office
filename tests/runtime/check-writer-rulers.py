#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Writer shows both rulers by default: new document and opened .docx, the View commands toggle them, the choice
persists, an explicit old choice wins, and the vertical ruler leaves the ribbon and its banner slot alone.

Usage: check-writer-rulers.py [--instdir DIR] [--work DIR] [--shot FILE]   (gtk3 on a private 1366x768 Xvfb)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DISPLAY, PORT = ":76", 22976
RIBBON_HEIGHT = 190  # pixels of the window top that hold the title bar and the ribbon with its banner slot
failures = []


def check(what, actual, expected):
    good = actual == expected
    print(("ok   " if good else "FAIL ") + f"{what}: {actual!r}" + ("" if good else f" (expected {expected!r})"), flush=True)
    if not good:
        failures.append(what)


def rulers(doc):
    settings = doc.getCurrentController().getViewSettings()
    return settings.ShowRulers, settings.ShowHoriRuler, settings.ShowVertRuler


def shot(office, path):
    """Screenshot with the window at the screen's corner: without a window manager it lands anywhere."""
    for wid, _name in hst_gui.toplevels(DISPLAY, office.pid):
        subprocess.run(["xdotool", "windowmove", wid, "0", "0"], env=dict(os.environ, DISPLAY=DISPLAY), check=False)
    time.sleep(1)
    subprocess.run(["import", "-display", DISPLAY, "-window", "root", path], check=False)


def top_difference(first, second):
    crop = f"1366x{RIBBON_HEIGHT}+0+0"
    done = subprocess.run(["compare", "-metric", "AE", "(", first, "-crop", crop, ")", "(", second, "-crop", crop, ")", "null:"],
                          capture_output=True, text=True)
    return int(float((done.stderr.split() or ["-1"])[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/writer-rulers"))
    parser.add_argument("--shot", default=None)
    args = parser.parse_args()
    shutil.rmtree(args.work, ignore_errors=True)
    os.makedirs(args.work)
    hst_gui.setup_uno(args.instdir)
    no_update = [("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"), ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1366x768x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    office = hst_gui.Office(args.instdir, args.work, PORT, display=DISPLAY, config=no_update)
    try:
        office.start()
        office.set_config("/org.hasontech.hstoffice.Welcome", "Shown", True)
        doc = office.load("private:factory/swriter")
        time.sleep(6)
        check("new document shows both rulers", rulers(doc), (True, True, True))
        with_ruler = os.path.join(args.work, "with.png")
        shot(office, with_ruler)
        if args.shot:
            os.makedirs(os.path.dirname(args.shot), exist_ok=True)
            shutil.copy(with_ruler, args.shot)

        from com.sun.star.beans import PropertyValue
        name = PropertyValue()
        name.Name, name.Value = "FilterName", "MS Word 2007 XML"
        path = os.path.join(args.work, "rulers.docx")
        doc.storeToURL("file://" + path, (name,))
        opened = office.load("file://" + path)
        time.sleep(3)
        check("opened .docx shows both rulers", rulers(opened), (True, True, True))
        opened.setModified(False)
        opened.close(True)
        time.sleep(1)

        frame = doc.getCurrentController().getFrame()
        office.dispatch(frame, ".uno:VRuler")
        time.sleep(2)
        check("View: the vertical ruler toggles off", rulers(doc), (True, True, False))
        without = os.path.join(args.work, "without.png")
        shot(office, without)
        check(f"ribbon and banner slot unchanged by the vertical ruler (top {RIBBON_HEIGHT} px differing)", top_difference(with_ruler, without), 0)
        office.dispatch(frame, ".uno:Ruler")
        time.sleep(1)
        check("View: Rulers hides them all", rulers(doc)[0], False)
        office.dispatch(frame, ".uno:Ruler")
        time.sleep(1)
        check("View: Rulers shows them again, the vertical one still off", rulers(doc), (True, True, False))
        doc.setModified(False)
        doc.close(True)
        office.stop()

        office.start(fresh=False)
        doc = office.load("private:factory/swriter")
        time.sleep(5)
        check("the user's choice persists after a restart", rulers(doc), (True, True, False))
        doc.setModified(False)
        doc.close(True)
        office.stop()
        with open(os.path.join(args.work, "profile/user/registrymodifications.xcu"), encoding="utf-8") as handle:
            text = handle.read()
        check("the choice is stored in the profile", 'oor:name="VerticalRuler"' in text, True)
    finally:
        try:
            office.stop()
        except Exception:  # noqa: BLE001 - already stopped
            pass
        xvfb.terminate()
    print(f"{len(failures)} failure(s)" if failures else "all checks passed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
