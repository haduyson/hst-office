#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Before/after screenshots of the HST coat on the ten pilot dialogs, on Windows (VCL-drawn dialogs).

Usage, with the image's own python.exe in the console user's session (remote.py HOST ui ...):
    <img>\\program\\python.exe coat-dialog-shots-windows.py --instdir <img> --work DIR --out DIR --scale 100
        [--look after-light ...] [dialog ...]
"before" runs with HST_UI_COAT=0, "after" with the coat on; light and dark come from the profile's
Common/Appearance/ApplicationAppearance (1 light, 2 dark), so the user's Windows theme is never changed. The display
scaling is set and restored outside this script; --scale only names the files:
<out>/<dialog>-<before|after>-<light|dark>-<scale>.png, plus failures.txt.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui_windows  # noqa: E402
import windows_gui_dialogs  # noqa: E402
from coat_dialog_cases import DIALOGS, NO_PROMPTS  # noqa: E402

LOOKS = [(coat, theme) for coat in ("before", "after") for theme in ("light", "dark")]
SHOT = os.path.join(HERE, "coat-window-shot.ps1")


def office_config(theme):
    return list(NO_PROMPTS) + [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                                       "2" if theme == "dark" else "1")]


def shown(office):
    return {hwnd for hwnd in (windows_gui_dialogs.dialog_hwnd(w) for w, _t in windows_gui_dialogs.dialogs(office)) if hwnd}


def new_dialog(office, before, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for window, _title in windows_gui_dialogs.dialogs(office):
            hwnd = windows_gui_dialogs.dialog_hwnd(window)
            if hwnd and hwnd not in before:
                time.sleep(1.5)  # let it finish its first paint
                return window, hwnd
        time.sleep(0.5)
    return None, None


def shoot_look(args, look, names, failures):
    coat, theme = look
    work = os.path.join(args.work, "-".join(look))
    office = hst_gui_windows.Office(args.instdir, work, args.port, config=office_config(theme),
                                    env={"HST_UI_COAT": "0" if coat == "before" else "1"}, ui=True)
    office.start()
    try:
        inner = office.office
        ui = office.service("com.sun.star.ui.test.UITest")
        docs = {}
        for name in names:
            factory, command = DIALOGS[name]
            if factory not in docs:
                docs[factory] = office.load(f"private:factory/{factory}")
                if factory == "swriter":
                    docs[factory].getText().setString("Thử nghiệm lớp áo HST: chữ saii chính tả và tieng Viet.")
                time.sleep(2)
            before = shown(inner)
            ui.executeDialog(command)
            window, hwnd = new_dialog(inner, before)
            if not hwnd:
                failures.append(f"{name} {'-'.join(look)}: no dialog window")
                continue
            path = os.path.join(args.out, f"{name}-{coat}-{theme}-{args.scale}.png")
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SHOT,
                                     "-Hwnd", str(hwnd), "-Path", path], capture_output=True, text=True, timeout=120)
            print(result.stdout.strip() or result.stderr.strip(), flush=True)
            if result.returncode:
                failures.append(f"{name} {'-'.join(look)}: capture failed")
            if windows_gui_dialogs.close_dialog(window) == "open":
                failures.append(f"{name} {'-'.join(look)}: dialog did not close; later shots of this look skipped")
                break
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--scale", required=True, choices=["100", "125"])
    parser.add_argument("--port", type=int, default=2331)
    parser.add_argument("--look", action="append", default=[], help="only these looks, e.g. after-dark")
    parser.add_argument("dialogs", nargs="*", help=", ".join(DIALOGS))
    args = parser.parse_args()
    unknown = [name for name in args.dialogs if name not in DIALOGS]
    if unknown:
        parser.error("unknown dialog: " + ", ".join(unknown))
    looks = [look for look in LOOKS if not args.look or "-".join(look) in args.look]
    if not looks:
        parser.error("no look matches " + ", ".join(args.look))
    os.makedirs(args.out, exist_ok=True)
    failures = []
    for look in looks:
        shoot_look(args, look, args.dialogs or list(DIALOGS), failures)
    with open(os.path.join(args.out, "failures.txt"), "w", encoding="utf-8") as out:
        out.write("".join(line + "\n" for line in failures))
    for line in failures:
        print("FAILED", line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
