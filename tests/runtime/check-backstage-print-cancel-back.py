#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
""""Hủy" (Cancel) and "Quay lại" (Back) of the Print page of the File panel (hst-backstage-print-cancel-back.patch)
in a visible office, driven by widget id through the UITest service (Linux X display, gtk3 or gen; Windows: the
test user's own session).

Per application (Writer, Sheets): .uno:Print opens the Print page; both buttons are there; a margins preset picked on
the page, then "Quay lại": the page closes and the margins stay (one undo step); a preset picked again, then "Hủy":
the page closes and the document has its margins of before. Screenshots of the page with --shot.
Usage: <office python> check-backstage-print-cancel-back.py --soffice PATH --out DIR [--shot CMD] [--dark]
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
_SPEC = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BASE)

# the second entry of the margins box: "Hẹp" (narrow) in both applications
NARROW = {"swriter": 1270, "scalc": 640}
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    failures.extend([] if ok else [text])


def load(office, app):
    """A new document; loaded on the main thread (a load on the bridge thread races with idle handlers)."""
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "OnMainThread", True
    return office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, (arg,))


def page_style(doc, app):
    controller = doc.getCurrentController()
    name = controller.ViewCursor.PageStyleName if app == "swriter" else controller.ActiveSheet.PageStyle
    return doc.StyleFamilies.getByName("PageStyles").getByName(name)


def margins(doc, app):
    style = page_style(doc, app)
    return style.LeftMargin, style.RightMargin, style.TopMargin, style.BottomMargin


def panel_button(office, oid, timeout=20):
    """The UI object of the Print page's widget with that id, None when the page is not shown."""
    for _ in range(timeout * 2):
        try:
            return office.ui.getTopFocusWindow().getChild(oid)
        except Exception:  # noqa: BLE001 - not (yet) there
            time.sleep(0.5)
    return None


def is_closed(office, timeout=10):
    for _ in range(timeout * 2):
        try:
            office.ui.getTopFocusWindow().getChild("back")
        except Exception:  # noqa: BLE001 - the page and its job are gone
            return True
        time.sleep(0.5)
    return False


def pick_narrow(office):
    from com.sun.star.beans import PropertyValue
    pos = PropertyValue()
    pos.Name, pos.Value = "POS", "1"
    panel_button(office, "marginsbox").executeAction("SELECT", (pos,))
    time.sleep(2)  # the page style changes after the event, the preview follows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-cb-"))  # noqa
    parser.add_argument("--shot", help="screenshot command with {} for the file, e.g. 'import -window root {}'")
    parser.add_argument("--dark", action="store_true", help="the dark application appearance")
    parser.add_argument("--apps", default="swriter,scalc")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    tag = "dark" if args.dark else "light"
    shot = lambda name: args.shot and subprocess.run(args.shot.format(os.path.join(out, name)), shell=True)  # noqa
    office = BASE.VisibleOffice(args.soffice, out, None)
    try:
        if args.dark:
            office.set_config("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", 2)
        for app in args.apps.split(","):
            doc = load(office, app)
            office.close_welcome()
            frame = doc.getCurrentController().getFrame()
            before = margins(doc, app)
            office.ui.executeCommandForProvider(".uno:Print", frame)
            cancel, back = panel_button(office, "cancel"), panel_button(office, "back")
            check(cancel is not None and back is not None, f"{app}: the Print page has Hủy and Quay lại")
            time.sleep(3)  # the preview is painted on idle
            shot(f"{app}-print-page-{tag}.png")
            if cancel is None or back is None:
                continue
            check(BASE.state(cancel).get("Text", "").replace("~", "") in ("Hủy", "Cancel")
                  and BASE.state(back).get("Text", "").replace("~", "") in ("Quay lại", "Back"),
                  f"{app}: labels {BASE.state(cancel).get('Text')!r}, {BASE.state(back).get('Text')!r}")

            pick_narrow(office)
            check(margins(doc, app)[0] == NARROW[app], f"{app}: the margins box changed the document's margins")
            panel_button(office, "back").executeAction("CLICK", ())
            check(is_closed(office), f"{app}: Quay lại closes the File panel")
            check(margins(doc, app)[0] == NARROW[app], f"{app}: after Quay lại the margins picked on the page stay")
            doc.getUndoManager().undo()  # the page's one undo step
            check(margins(doc, app) == before, f"{app}: one undo step takes the page's margins back")

            office.ui.executeCommandForProvider(".uno:Print", frame)
            if panel_button(office, "cancel") is None:
                check(False, f"{app}: the Print page opens again")
                continue
            pick_narrow(office)
            changed = margins(doc, app)
            panel_button(office, "cancel").executeAction("CLICK", ())
            check(is_closed(office), f"{app}: Hủy closes the File panel")
            check(changed[0] == NARROW[app] and margins(doc, app) == before,
                  f"{app}: Hủy restores the margins of before ({changed} -> {margins(doc, app)}, was {before})")
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
