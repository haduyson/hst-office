#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 wizard: moving between fields and typing stay fast, and every one-line field is as high as the platform draws it.

Usage: python3 tests/runtime/check-nd30-field-switch.py --display :131 [--instdir upstream/libreoffice/instdir]
                                                        [--out DIR] [--port 2195] [--max-median-ms 100] [--max-ms 500]
The display must already run (1366x768); it is never started or stopped here. HST_VCLPLUGIN=gen checks the gen backend.

Timing: the wizard runs inside the office (HST menu command), for "Công văn", "Quyết định" and the Party "Thông tri".
Keys are posted inside VCL (XToolkitRobot), so the X server or a VM cannot drop them. Each Tab or digit is timed from the
post until the office is idle again (processEventsToIdle): VCL focus handling, the edit's change, the wizard's refresh()
of the preview and the repaints. Tabs through the empty and the
filled form (with a 40-paragraph body), digits typed in every field.

Type then Tab: a query typed in "Loại văn bản" and Tab take the highlighted type, close the list and move to the next
field (the open list used to cover the next seven fields, typing went nowhere and the type was silently lost).

Height: the wizard is built over the bridge; each one-line edit must be at least as high as its preferred height
(Edit::CalcMinimumSize: text height plus borders, or the native frame when higher; 29 px on macOS), or fill all the
room down to the control below it. A 12-unit edit was
lower than that on macOS (text pinned to the top border, descenders of g/y cut) and on gen (hook of Ủ cut).
Exit 1 on any failure.
"""
import argparse
import os
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402
from nd30_field_switch_gui import (PARA, Robot, close, focus_window, open_wizard, set_clipboard,  # noqa: E402
                                   wizard_window)

ROWS = []


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def timing(office, args):
    robot = Robot(office)
    set_clipboard(office, "\n".join([PARA] * 40))
    for query in ("cong van", "quyet dinh", "thong tri"):
        doc, dialog, thread = open_wizard(office, robot)
        check("%s: the wizard opens" % query, dialog is not None)
        if dialog is None:
            continue
        # choose the type with real keys: a Return posted inside VCL bypasses the list's key handler and presses "Chèn"
        env = dict(os.environ, DISPLAY=args.display)
        subprocess.run(["xdotool", "type", "--delay", "40", query], env=env, check=False, timeout=30)
        time.sleep(0.8)
        subprocess.run(["xdotool", "key", "Return"], env=env, check=False, timeout=30)
        time.sleep(1)
        if wizard_window(robot.toolkit) is None:
            check("%s: the type was chosen in the open wizard" % query, False, "the wizard closed")
            close(doc)
            continue
        tabs = [robot.timed(dialog, "TAB") for _ in range(20)]
        for _ in range(20):
            robot.press(dialog, "TAB", modifiers=1)  # Shift+Tab back to the type field
        time.sleep(0.5)
        keys = []
        for field in range(15):  # Tab to the next stop, type two digits (the 7th stop is the date: keep it valid)
            tabs.append(robot.timed(dialog, "TAB"))
            if field == 9:  # "Nội dung": paste the 40-paragraph body
                keys.append(robot.timed(dialog, "V", "v", modifiers=2))
            elif field != 6:
                keys += [robot.timed(dialog, "NUM" + digit, digit) for digit in "12"]
        keys += [robot.timed(dialog, "NUM1", "1") for _ in range(10)]  # long preview
        for name, values in (("Tab", tabs), ("key", keys)):
            median, worst = statistics.median(values), max(values)
            check("%s: %s median under %d ms" % (query, name, args.max_median_ms), median < args.max_median_ms,
                  "median %.1f ms, max %.1f ms, n=%d" % (median, worst, len(values)))
            check("%s: every %s under %d ms" % (query, name, args.max_ms), worst < args.max_ms, "max %.1f ms" % worst)
        hst_gui.screenshot(os.path.join(args.out, "filled-%s.png" % query.replace(" ", "-")), args.display)
        focus_window(args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=30)
        thread.join(10)
        if thread.is_alive():  # the list may have taken the first Esc
            subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=30)
            thread.join(10)
        check("%s: Esc closes the wizard" % query, not thread.is_alive())
        if thread.is_alive():
            dialog.endExecute()
            thread.join(10)
        close(doc)


def heights(office, args):
    from hst_office import data_files, dialog_edit_heights, wizard_nd30
    from com.sun.star.awt import Size
    from com.sun.star.util.MeasureUnit import APPFONT
    doc = office.desktop().loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
    thread = threading.Thread(target=lambda: wizard.run(doc.getCurrentController().getFrame().getContainerWindow()), daemon=True)
    thread.start()
    for _ in range(60):
        time.sleep(0.5)
        if wizard.picker.handler and wizard.d.dialog.getPeer():
            break
    time.sleep(1.5)
    d = wizard.d
    peer = d.dialog.getPeer()
    low = []
    for name in d._single_lines:
        control = d.dialog.getControl(name)
        want, have = control.getPreferredSize().Height, control.getPeer().getPosSize().Height
        if have < want and d.model.getByName(name).Height < dialog_edit_heights.room_below(d, name):
            low.append("%s %d<%d px" % (name, have, want))
    check("every one-line field has its preferred height or all the room below it", not low, low or len(d._single_lines))
    model = d.model
    field, rows = d.dialog.getControl("type").getPeer().getPosSize(), wizard.picker.popup.box()
    check("the type list hangs under the type field", rows[1] >= field.Y + field.Height, (field.Y, field.Height, rows))
    overlaps = []
    names = [n for n in model.ElementNames if model.getByName(n).EnableVisible]
    for name in d._single_lines:
        a = model.getByName(name)
        for other in names:
            b = model.getByName(other)
            if other != name and (a.PositionX < b.PositionX + b.Width and b.PositionX < a.PositionX + a.Width
                                  and a.PositionY < b.PositionY + b.Height and b.PositionY < a.PositionY + a.Height):
                overlaps.append("%s/%s" % (name, other))
    check("grown fields overlap no other control", not overlaps, overlaps)
    # Type a query in "Loại văn bản" and leave with Tab: the highlighted type is taken, the list closes and the focus
    # and the next typing land in "Cơ quan chủ quản" (an open list used to cover it and the type was silently lost).
    env = dict(os.environ, DISPLAY=args.display)
    focus_window(args.display)
    d.dialog.getControl("type").setFocus()
    time.sleep(0.5)
    subprocess.run(["xdotool", "type", "--delay", "50", "quyet"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    opened = wizard.picker.open
    subprocess.run(["xdotool", "key", "Tab"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    subprocess.run(["xdotool", "type", "--delay", "50", "UBND"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    hst_gui.screenshot(os.path.join(args.out, "type-then-tab.png"), args.display)
    check("a typed query opens the list", opened)
    check("Tab takes the highlighted type and closes the list", wizard.picker.current == "quyet-dinh" and not wizard.picker.open,
          (wizard.picker.current, wizard.picker.open))
    check("after Tab the next typing lands in Cơ quan chủ quản", model.getByName("parentAgency").Text == "UBND",
          repr(model.getByName("parentAgency").Text))
    one = peer.convertSizeToPixel(Size(0, 1), APPFONT).Height
    print("one AppFont unit: %s px; heights: %s" % (one, {n: model.getByName(n).Height for n in d._single_lines}))
    hst_gui.screenshot(os.path.join(args.out, "heights.png"), args.display)
    d.dialog.endExecute()
    thread.join(10)
    close(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-field-switch"))
    parser.add_argument("--port", type=int, default=2195)
    parser.add_argument("--max-median-ms", type=int, default=100)
    parser.add_argument("--max-ms", type=int, default=500)
    parser.add_argument("--skip-heights", action="store_true", help="timing only (an office without this checkout's dialogs.py)")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "office"), args.port, display=args.display).start()
    try:
        time.sleep(5)  # let the start-up dialogs settle (the welcome watcher closes them)
        timing(office, args)
        if not args.skip_heights:
            heights(office, args)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
