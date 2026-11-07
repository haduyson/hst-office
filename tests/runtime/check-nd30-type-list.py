#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The open "Loại văn bản" list of the ND30 wizard stays on top of the fields it covers: hover, repaint, wheel and click.

Usage: python3 tests/runtime/check-nd30-type-list.py --display :131 [--instdir upstream/libreoffice/instdir] [--out DIR]
                                                     [--port 2194]
The display must already run (1366x768); it is never started or stopped here. HST_VCLPLUGIN=gen checks the gen backend.

Regression: the list used to be inserted after the fields, so in VCL it lay under them. Over the "Cơ quan ban hành"
row the pointer reached the agency field: a hover repainted the field over the list (a white bar on macOS and gtk3),
the wheel did not scroll the list, and a click focused the field instead of choosing the row. Moved above them in the
model it still was a sibling, and VCL does not clip siblings: on Windows the themed edits repainted through it on hover
and on any change. The list is now a popup (an overlap window in the dialog's frame, wizard_type_popup); a covered field
that repaints must stay under it. Exit 1 on any failure.
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
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:200]), flush=True)


def _crop(path, box):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert("RGB").crop(box).tobytes()


def _intersects(a, b, slack=2):
    """Overlap of more than `slack` pixels (AppFont units round to whole pixels, so neighbours may touch by 1 px)."""
    return (a.X + slack < b.X + b.Width and b.X + slack < a.X + a.Width
            and a.Y + slack < b.Y + b.Height and b.Y + slack < a.Y + a.Height)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-type-list"))
    parser.add_argument("--port", type=int, default=2194)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    env = dict(os.environ, DISPLAY=args.display)

    def xdo(*items, pause=0.6):
        subprocess.run(["xdotool", *map(str, items)], env=env, check=False, timeout=30)
        time.sleep(pause)

    def shot(name):
        path = os.path.join(out, name)
        hst_gui.screenshot(path, args.display)
        return path

    try:
        from hst_office import data_files, wizard_nd30
        doc = office.service("com.sun.star.frame.Desktop").loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
        names = list(wizard.d.model.ElementNames)
        check("the list is not a control of the dialog (VCL does not clip overlapping siblings)", "typeList" not in names)
        peer = doc.getCurrentController().getFrame().getContainerWindow()
        thread = threading.Thread(target=lambda: wizard.run(peer), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(1)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        dialog, picker = wizard.d.dialog, wizard.picker
        geo = {n: dialog.getControl(n).getPeer().getPosSize() for n in names}
        listbox = type("Box", (), dict(zip(("X", "Y", "Width", "Height"), picker.popup.box())))
        covered = [n for n in names if _intersects(listbox, geo[n])]
        check("the popup lies under the type field, over the fields below it", "agency" in covered
              and listbox.Y >= geo["type"].Y + geo["type"].Height, covered)
        window = None
        for _ in range(20):  # the gen backend maps the dialog window a little later
            window = next((wid for wid, name in hst_gui.toplevels(args.display) if name == wizard.d.model.Title), None)
            if window is None:  # gen: the title may not read back as UTF-8 through xwininfo
                found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", re.escape(wizard.d.model.Title)],
                                       env=env, capture_output=True, text=True).stdout.split()
                window = hex(int(found[-1])) if found else None
            if window:
                break
            time.sleep(0.5)
        check("the dialog window is on screen", window is not None)
        if window is None:
            raise RuntimeError("dialog window not found")
        info = subprocess.run(["xwininfo", "-display", args.display, "-id", window], capture_output=True, text=True).stdout
        ox, oy = (int(re.search(label + r":\s+(-?\d+)", info).group(1)) for label in ("Absolute upper-left X", "Absolute upper-left Y"))
        xdo("windowfocus", "--sync", window)
        row = (ox + geo["agency"].X + geo["agency"].Width * 2 // 5, oy + geo["agency"].Y + geo["agency"].Height // 2)
        box = (ox + listbox.X, oy + listbox.Y, ox + listbox.X + listbox.Width, oy + listbox.Y + listbox.Height)
        start = picker.current
        arrow = geo["typeOpen"]
        xdo("mousemove", ox + arrow.X + arrow.Width // 2, oy + arrow.Y + arrow.Height // 2)
        xdo("click", 1, pause=1.5)
        check("the arrow opens the list", picker.open)
        xdo("mousemove", box[2] + 40, oy + 5, pause=1.0)
        away = shot("1-open-pointer-away.png")
        xdo("mousemove", *row, pause=1.2)
        hover = shot("2-hover-agency-row.png")
        band = (box[0] + 4, oy + geo["agency"].Y + 2, box[2] - 4, oy + geo["agency"].Y + geo["agency"].Height - 2)
        flat_away, flat_hover = _flat_share(away, band), _flat_share(hover, band)
        check("hover over the 'Cơ quan ban hành' row shows the list there, not the field",
              flat_hover <= max(0.6, flat_away + 0.2), "flat rows %.2f -> %.2f" % (flat_away, flat_hover))
        # a covered field repaints on its own while the list is open (here: its text changes)
        place = geo["place"]
        band = (ox + place.X + 4, oy + place.Y + 2, ox + place.X + place.Width - 4, oy + place.Y + place.Height - 2)
        flat_before = _flat_share(hover, band)
        wizard.d.model.getByName("place").Text = "Tam Kỳ, Quảng Nam"
        time.sleep(1.2)
        repainted = shot("2b-covered-field-repaints.png")
        flat_after = _flat_share(repainted, band)
        check("a covered field that repaints stays under the list", flat_after <= max(0.6, flat_before + 0.2),
              "flat rows %.2f -> %.2f" % (flat_before, flat_after))
        top_rows = (box[0], box[1], box[2], oy + geo["agency"].Y - 2)  # list rows above the field band: only a scroll moves them
        before = _crop(hover, top_rows)
        for _ in range(5):
            xdo("click", 5, pause=0.2)
        time.sleep(1)
        wheel = shot("3-wheel-over-agency-row.png")
        check("wheel over that row scrolls the list", _crop(wheel, top_rows) != before)
        xdo("click", 1, pause=1.5)
        shot("4-click-agency-row.png")
        agency_focus = dialog.getControl("agency").getPeer().hasFocus()
        check("click on that row chooses it and closes the list", picker.current != start and not picker.open, (start, picker.current))
        check("the click does not focus the agency field", not agency_focus)
        dialog.endExecute()
        thread.join(10)
        doc.close(True)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


def _flat_share(path, box):
    """Share of the pixel rows inside `box` that have one colour only. The list shows its rows' text there; a field
    painted over the list is an empty white box, so almost every pixel row in it is flat."""
    from PIL import Image
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(box)
    width, height = crop.size
    pixels = crop.load()
    flat = sum(1 for y in range(height) if len({pixels[x, y] for x in range(width)}) == 1)
    return flat / float(height or 1)


if __name__ == "__main__":
    sys.exit(main())
