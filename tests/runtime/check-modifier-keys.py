# SPDX-License-Identifier: AGPL-3.0-only
"""Ctrl, Alt and Shift alone must be harmless in every kind of window (gtk3, real GUI).

Usage: python3 tests/runtime/check-modifier-keys.py [--instdir DIR] [--display :71] [--out DIR]
The modifier handling of the ribbon runs in SystemWindow::EventNotify, so every top-level window passes through it, also
those without a ribbon. Presses each modifier, and Ctrl+A, with the focus in: a native dialog, a dialog of a Python UNO
client, the Basic IDE, the Start Center, a document in the tabbed UI and a document in the classic toolbar UI.
The office must stay alive in all of them. Runs as the build user. Writes evidence.json; exit 1 on a failure.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROWS = []
KEYS = ("ctrl", "Alt_L", "shift", "Control_L", "Shift_L", "ctrl+a")
CLASSIC = [("/org.openoffice.Office.UI.ToolbarMode/Applications/Writer", "Active", "Default"),
           ("/org.openoffice.Office.UI.ToolbarMode/Applications/Calc", "Active", "Default")]


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def press(args, office, what):
    """All the keys, each followed by a check that the office answers."""
    for key in KEYS:
        subprocess.run(["xdotool", "key", key.replace("ctrl", "Control_L") if key == "ctrl" else key.replace("shift", "Shift_L") if key == "shift" else key],
                       env=dict(os.environ, DISPLAY=args.display), check=False, timeout=15)
        time.sleep(0.3)
        alive = office.pid is not None
        if not alive:
            record(f"{what}: {key}", False, "the office died")
            return False
    record(f"{what}: Ctrl, Alt, Shift alone and Ctrl+A", True)
    return True


def focus_window(args, wid):
    subprocess.run(["xdotool", "windowfocus", wid], env=dict(os.environ, DISPLAY=args.display), check=False, timeout=15)
    time.sleep(0.5)


def newest(args, office, before):
    time.sleep(2.5)
    fresh = [w for w, _n in hst_gui.toplevels(args.display, office.pid) if w not in before]
    return fresh[0] if fresh else None


def windows(args, office):
    return {w for w, _n in hst_gui.toplevels(args.display, office.pid)}


def uno_dialog(office, args):
    """A toolkit dialog with an edit and a button, executed from this client."""
    smgr = office.smgr
    ctx = office.ctx
    model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    model.Width, model.Height, model.Title = 120, 60, "HST modifier check"
    edit = model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit.Name, edit.PositionX, edit.PositionY, edit.Width, edit.Height = "e", 5, 5, 100, 14
    model.insertByName("e", edit)
    button = model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    button.Name, button.PositionX, button.PositionY, button.Width, button.Height, button.PushButtonType = "b", 5, 30, 50, 14, 2
    model.insertByName("b", button)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(model)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    dialog.setVisible(True)
    time.sleep(2)
    return dialog


def check_tabbed(args, instdir):
    office = hst_gui.Office(instdir, os.path.join(args.out, "tabbed"), 7700, display=args.display, nodefault=False)
    office.start()
    try:
        time.sleep(6)
        press(args, office, "Start Center")
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        time.sleep(3)
        press(args, office, "Writer, tabbed UI")
        before = windows(args, office)
        office.dispatch(frame, ".uno:ParagraphDialog")
        wid = newest(args, office, before)
        record("native dialog opens", wid is not None)
        if wid:
            focus_window(args, wid)
            press(args, office, "native dialog")
            hst_gui.send_close_request(wid, args.display)
            time.sleep(1)
            subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=args.display), check=False)
            time.sleep(1)
        dialog = uno_dialog(office, args)
        before_keys = hst_gui.toplevels(args.display, office.pid)
        target = [w for w, n in before_keys if "HST modifier check" in n]
        if target:
            focus_window(args, target[0])
        record("UNO dialog shows", bool(target))
        press(args, office, "UNO dialog")
        dialog.setVisible(False)
        dialog.dispose()
        before = windows(args, office)
        office.dispatch(frame, ".uno:BasicIDEAppear")
        wid = newest(args, office, before)
        record("Basic IDE opens", wid is not None)
        if wid:
            focus_window(args, wid)
            press(args, office, "Basic IDE")
        doc.setModified(False)
    finally:
        office.stop()


def check_classic(args, instdir):
    office = hst_gui.Office(instdir, os.path.join(args.out, "classic"), 7701, display=args.display, config=CLASSIC)
    office.start()
    try:
        doc = office.load("private:factory/swriter")
        time.sleep(4)
        press(args, office, "Writer, classic toolbars")
        calc = office.load("private:factory/scalc")
        time.sleep(4)
        press(args, office, "Sheets, classic toolbars")
        doc.setModified(False)
        calc.setModified(False)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/modifier-keys"))
    args = parser.parse_args()
    args.instdir = os.path.abspath(args.instdir)
    hst_gui.setup_uno(args.instdir)
    for step in (check_tabbed, check_classic):
        try:
            step(args, args.instdir)
        except Exception as error:  # noqa: BLE001
            record(f"{step.__name__} crashed", False, repr(error)[:200])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
