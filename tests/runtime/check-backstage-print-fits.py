#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The Print page of the File panel shows all of itself in a small window (hst-backstage-panel-beside-banner.patch):
in a visible office (Windows: the test user's own session, at the scaling under test, e.g. 125 %), the document
window is set to each width (1024, 1042, 1366 px by default), .uno:Print opens the Print page, and the page's
buttons ("In", "Hủy", "Quay lại") must end inside the panel and the printer's status inside its scrolled settings.
Positions are the UITest service's (AbsPosition, Size: the window's pixels). Screenshots with --shot.
Usage: <office python> check-backstage-print-fits.py --soffice PATH --out DIR [--shot CMD] [--widths 1024,1366]
       [--apps swriter,scalc]
Exit 1 on a failure.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("cancel_back", os.path.join(HERE, "check-backstage-print-cancel-back.py"))
CB = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CB)

BUTTONS = ("ok", "cancel", "back")  # In, Hủy, Quay lại


def rect(widget):
    """(left, top, right, bottom) of a UITest object, from its AbsPosition and Size."""
    state = CB.BASE.state(widget)
    x, y = (int(v) for v in state["AbsPosition"].split("x"))
    w, h = (int(v) for v in state["Size"].split("x"))
    return x, y, x + w, y + h


def check_fits(office, app, width):
    panel = CB.panel_button(office, "panel")
    settings = CB.panel_button(office, "scrolledwindow")
    if panel is None or settings is None:
        CB.check(False, f"{app} @{width}: the panel and the page's settings are found")
        return
    right, settings_right = rect(panel)[2], rect(settings)[2]
    for oid in BUTTONS:
        widget = CB.panel_button(office, oid)
        if widget is None:
            CB.check(False, f"{app} @{width}: {oid} is on the page")
            continue
        box = rect(widget)
        CB.check(box[2] <= right, f"{app} @{width}: {oid} ends at {box[2]}, inside the panel (right {right})")
    status = CB.panel_button(office, "status")
    if status is not None:
        box = rect(status)
        CB.check(box[2] <= settings_right,
                 f"{app} @{width}: the printer's status ends at {box[2]}, inside the settings (right {settings_right})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-fits-"))
    parser.add_argument("--shot", help="screenshot command with {} for the file")
    parser.add_argument("--widths", default="1024,1042,1366")
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--apps", default="swriter,scalc")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    shot = lambda name: args.shot and subprocess.run(args.shot.format(os.path.join(out, name)), shell=True)  # noqa
    office = CB.BASE.VisibleOffice(args.soffice, out, None)
    try:
        for app in args.apps.split(","):
            doc = CB.load(office, app)
            office.close_welcome()
            frame = doc.getCurrentController().getFrame()
            CB.FRAME[:] = [frame]
            container = frame.getContainerWindow()
            for width in (int(w) for w in args.widths.split(",")):
                container.IsMaximized = False
                container.setPosSize(0, 0, width, args.height, 15)  # PosSize.POSSIZE
                time.sleep(2)
                office.ui.executeCommandForProvider(".uno:Print", frame)
                if CB.panel_button(office, "back") is None:
                    CB.check(False, f"{app} @{width}: the Print page opens")
                    continue
                time.sleep(3)  # the preview is painted on idle
                shot(f"{app}-print-{width}.png")
                check_fits(office, app, width)
                CB.panel_button(office, "back").executeAction("CLICK", ())
                CB.check(CB.is_closed(office), f"{app} @{width}: Quay lại closes the File panel")
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(CB.failures)} failure(s)", flush=True)
    sys.exit(1 if CB.failures else 0)


if __name__ == "__main__":
    main()
