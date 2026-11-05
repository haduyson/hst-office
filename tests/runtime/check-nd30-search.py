#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Quick Search of the wizard's document-type list on the real HST build: typed keys, live filter, Enter and Esc.

Usage: python3 tests/runtime/check-nd30-search.py --display :131 [--instdir upstream/libreoffice/instdir] [--out DIR] [--port 2192]
The display must run at 1366x768. The real dialog runs over a UNO bridge; xdotool types into it. Screenshots stay in --out.
Exit 1 on any failure.
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402

ROWS = []


def check(name, ok, detail=""):
    ROWS.append(ok)
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:200]), flush=True)


wizard = None


def main():
    global wizard
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-search"))
    parser.add_argument("--port", type=int, default=2192)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    env = dict(os.environ, DISPLAY=args.display)

    def keys(*items):
        subprocess.run(["xdotool", *items], env=env, check=False, timeout=30)
        time.sleep(0.8)

    def retype(text):
        """Replace the field's text with Ctrl+A and typing, as a person does (modifier keys once crashed UNO dialogs)."""
        keys("key", "ctrl+a")
        keys("type", "--delay", "40", text)

    def shot(name):
        return hst_gui.screenshot(os.path.join(out, name), args.display)

    try:
        from hst_office import data_files, wizard_nd30
        doc = office.service("com.sun.star.frame.Desktop").loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
        result = {}
        peer = doc.getCurrentController().getFrame().getContainerWindow()
        thread = threading.Thread(target=lambda: result.update(choice=wizard.run(peer)), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(1)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        picker = wizard.picker
        field = wizard.d.model.getByName("type")
        size = wizard.d.dialog.getPeer().getPosSize()
        check("dialog fits 1366x768", size.Width <= 1366 and size.Height <= 768, (size.Width, size.Height))
        title = wizard.d.model.Title
        window = next(wid for wid, name in hst_gui.toplevels(args.display) if name == title)
        keys("windowfocus", "--sync", window)  # no window manager: give the dialog the keyboard
        info = subprocess.run(["xwininfo", "-display", args.display, "-id", window], capture_output=True, text=True).stdout
        box = [int(re.search(label + r":\s+(-?\d+)", info).group(1)) for label in ("Absolute upper-left X", "Absolute upper-left Y", "Width", "Height")]
        check("the whole dialog is on a 1366x768 screen", box[0] >= 0 and box[1] >= 0 and box[0] + box[2] <= 1366 and box[1] + box[3] <= 768, box)
        shot("search-closed.png")
        picker.field.setFocus()
        time.sleep(0.5)
        for query, wanted in (("cong van", "cong-van"), ("ke hoach", "ke-hoach"), ("gm", "giay-moi"), ("giấy mời", "giay-moi"), ("TTr", "to-trinh"),
                              ("QĐ", "quyet-dinh"), ("qd", "quyet-dinh"), ("so di", "so-van-ban-di"), ("thong tu", "thong-tu")):
            if query.isascii():
                retype(query)
            else:  # xdotool can't type Vietnamese on this display: the text arrives as an input method hands it over
                picker.field.setText(query)
                time.sleep(2.5)
            ids = [row[1] for row in picker.table if row[1]]
            check("query %r filters live" % query, picker.open and field.Text == query and bool(ids) and ids[0] == wanted, (field.Text, ids[:4]))
        shot("search-filtered.png")
        retype("quyet dinh")
        first = picker.index
        keys("key", "Down")
        check("Down moves to the next type, past any heading", picker.index > first and bool(picker.table[picker.index][1]), picker.index)
        keys("key", "Up")
        check("Up moves back", picker.index == first, picker.index)
        retype("bien ban")
        shot("search-open.png")
        keys("key", "Return")
        check("Enter chooses and leaves the dialog open", picker.current == "bien-ban" and not picker.open and thread.is_alive(), picker.current)
        check("the field shows the chosen label", field.Text == "Biên bản", field.Text)
        time.sleep(0.5)
        check("the preview follows", "THƯ KÝ" in wizard.d.get("preview"), wizard.d.get("preview")[-60:])
        picker.field.setFocus()
        retype("giay")
        keys("key", "Escape")
        check("Esc closes the list, keeps the dialog and the chosen type", not picker.open and thread.is_alive() and picker.current == "bien-ban" and field.Text == "Biên bản", field.Text)
        shot("search-after-esc.png")
        retype("sodangkyvanbandi")
        check("no result leaves an empty list", picker.table == [], picker.table[:2])
        keys("key", "Return")
        check("Enter on no result does nothing", thread.is_alive() and picker.open)
        keys("key", "Escape")
        keys("key", "Escape")
        thread.join(6)
        check("Esc with the list closed cancels the dialog", not thread.is_alive() and result.get("choice") is None)
        if not thread.is_alive():
            doc.close(True)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
