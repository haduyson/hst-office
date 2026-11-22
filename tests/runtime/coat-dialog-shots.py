#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Before/after screenshots of the HST coat on ten pilot dialogs, on Linux gtk3.

Usage: coat-dialog-shots.py --instdir DIR --work DIR --out DIR [--display :143] [--port N] [--look after-light-100 ...]
       [dialog ...]

One package gives both looks: "before" runs with HST_UI_COAT=0 (the platform's look), "after" with the
coat on. Each look is shot light and dark (GTK_THEME=Adwaita / Adwaita:dark) at 100 % and 125 %
(GDK_DPI_SCALE=1.25: fractional scaling on X11 scales text and therefore the layout). The display must
already run (an Xvfb of your own); this script never starts or kills it. Output:
<out>/<dialog>-<before|after>-<light|dark>-<100|125>.png, plus a list of the dialogs that did not open.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

from coat_dialog_cases import DIALOGS, FRAME_VIEWS, NO_PROMPTS  # noqa: E402

LOOKS = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in ("100", "125")]


def look_env(coat, theme, scale):
    env = {"HST_UI_COAT": "0" if coat == "before" else "1", "GTK_THEME": "Adwaita:dark" if theme == "dark" else "Adwaita"}
    if scale == "125":
        env["GDK_DPI_SCALE"] = "1.25"
    return env


def load(office, factory):
    from com.sun.star.beans import PropertyValue
    props = []
    for name, value in (("Hidden", False), ("OnMainThread", True)):
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        props.append(prop)
    return office.desktop().loadComponentFromURL(f"private:factory/{factory}", "_blank", 0, tuple(props))


def new_windows(office, before, display, timeout=45):
    """Top-level windows of our office that appeared after `before`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        now = [w for w in hst_gui.toplevels(display, pid=office.pid) if w[0] not in before]
        if now:
            time.sleep(1.5)  # let the dialog finish its first paint
            return [w for w in hst_gui.toplevels(display, pid=office.pid) if w[0] not in before]
        time.sleep(0.5)
    return []


def close_all(office, wins, display, before):
    for _ in range(5):
        for wid, _name in wins:
            hst_gui.send_close_request(wid, display)
        time.sleep(1)
        wins = [w for w in hst_gui.toplevels(display, pid=office.pid) if w[0] not in before]
        if not wins:
            return True
    return False


def shoot_frame_view(args, office, ui, name, look, failures):
    """A view shown inside a document window (HST's backstage print): a fresh document, the command, a shot of
    that document's window; closing the document afterwards cancels whatever the view started."""
    factory, command = DIALOGS[name]
    before = {w[0] for w in hst_gui.toplevels(args.display, pid=office.pid)}
    doc = load(office, factory)
    frames = new_windows(office, before, args.display)
    if not frames:
        failures.append(f"{name} {'-'.join(look)}: no document window")
        return
    ui.executeDialog(command)
    time.sleep(8)  # the view lays out its preview
    path = os.path.join(args.out, f"{name}-{'-'.join(look)}.png")
    os.makedirs(args.out, exist_ok=True)
    subprocess.run(["import", "-display", args.display, "-window", frames[0][0], path], check=True)
    print("shot", path, flush=True)
    try:
        doc.close(True)
    except Exception as error:  # noqa: BLE001 - the view may veto; the office is stopped after this look anyway
        failures.append(f"{name} {'-'.join(look)}: document did not close ({error})")


def shoot_look(args, look, names, failures):
    coat, theme, scale = look
    work = os.path.join(args.work, "-".join(look))
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display, config=NO_PROMPTS,
                            env=look_env(*look))
    office.start()
    try:
        ui = office.service("com.sun.star.ui.test.UITest")
        docs = {}
        for name in names:
            factory, command = DIALOGS[name]
            if factory not in docs:
                docs[factory] = load(office, factory)
                if factory == "swriter":
                    # misspelt words for the spelling dialog
                    docs[factory].getText().setString("Thử nghiệm lớp áo HST: chữ saii chính tả và tieng Viet.")
                time.sleep(2)
            if name in FRAME_VIEWS:
                shoot_frame_view(args, office, ui, name, look, failures)
                continue
            docs[factory].getCurrentController().getFrame().getContainerWindow().setFocus()
            before = {w[0] for w in hst_gui.toplevels(args.display, pid=office.pid)}
            ui.executeDialog(command)
            wins = new_windows(office, before, args.display)
            if not wins:
                failures.append(f"{name} {'-'.join(look)}: no dialog window")
                continue
            path = os.path.join(args.out, f"{name}-{coat}-{theme}-{scale}.png")
            os.makedirs(args.out, exist_ok=True)
            subprocess.run(["import", "-display", args.display, "-window", wins[-1][0], path], check=True)
            print("shot", path, flush=True)
            if not close_all(office, wins, args.display, before):
                failures.append(f"{name} {'-'.join(look)}: dialog did not close; later shots of this look skipped")
                break
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":143")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--look", action="append", default=[], help="only these looks, e.g. after-dark-125")
    parser.add_argument("dialogs", nargs="*", help=", ".join(DIALOGS))
    args = parser.parse_args()
    unknown = [name for name in args.dialogs if name not in DIALOGS]
    if unknown:
        parser.error("unknown dialog: " + ", ".join(unknown))
    args.port = args.port or hst_gui.free_port()
    os.environ["HST_VCLPLUGIN"] = "gtk3"
    hst_gui.setup_uno(args.instdir)
    names = args.dialogs or list(DIALOGS)
    looks = [look for look in LOOKS if not args.look or "-".join(look) in args.look]
    if not looks:
        parser.error("no look matches " + ", ".join(args.look))
    failures = []
    for look in looks:
        shoot_look(args, look, names, failures)
    with open(os.path.join(args.out, "failures.txt"), "w", encoding="utf-8") as out:
        out.write("".join(line + "\n" for line in failures))
    for line in failures:
        print("FAILED", line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
