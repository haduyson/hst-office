# SPDX-License-Identifier: AGPL-3.0-only
"""Check the two even toolbar rows beside the window banner (gtk3, real GUI).

Usage: python3 tests/runtime/check-toolbar-two-rows.py --instdir DIR [--display :172] [--out DIR]
           [--apps writer,calc,impress,draw] [--sizes 1366x768,1920x1080] [--scale 1] [--appearance light|dark]
           [--shots DIR]

hst-toolbar-two-rows.patch: each toolbar user interface of each app (.uno:ToolbarMode, as View > User Interface
does) is chosen at every window size; toolbar_two_rows_probe.judge decides: the lone toolbar of Single toolbar,
Sidebar and Draw's Standard interface has two rows of about equal width (at most one button apart, same left
edge) centred vertically in the banner strip, left of the banner; the Standard interfaces with several toolbars
keep one row per toolbar. In Writer's Single toolbar interface the toolbar then goes through what users do with
it: another toolbar joins the top docking area (one row each), it is hidden again (two rows), the toolbar is
locked (two rows), undocked (floating) and docked again (two rows), and the persisted window state of the toolbar
is the same as before. --scale 2 runs under GDK_SCALE=2. Writes results.json and one screenshot per case.
The X display must already run (this script never starts or stops it).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import toolbar_two_rows_steps as steps  # noqa: E402
from banner_everywhere_cases import NAMES  # noqa: E402
from ribbon_banner_run import xdo  # noqa: E402


def run_app(args, app, results):
    tag = f"-x{args.scale}" + ("-dark" if args.appearance == "dark" else "")
    env = {"GDK_SCALE": str(args.scale)} if args.scale != 1 else {}
    office = hst_gui.Office(args.instdir, os.path.join(args.out, f"{app}{tag}"), hst_gui.free_port(),
                            display=args.display, extra_args=[f"--{app}"], nodefault=False, env=env,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"),
                                    ("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                                     {"light": "1", "dark": "2"}[args.appearance])])
    office.start()
    try:
        time.sleep(8)
        office.close_welcome()
        wid = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
        xdo(args.display, "windowmove", wid, "0", "0")
        frame = office.desktop().getCurrentFrame()

        def resize(width, height):
            xdo(args.display, "windowsize", wid, str(width * args.scale), str(height * args.scale))

        steps.run_modes(args, office, frame, app, results, tag, resize)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":172")
    parser.add_argument("--out", default="tests/output/toolbar-two-rows")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--sizes", default="1366x768,1920x1080")
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--appearance", choices=("light", "dark"), default="light")
    parser.add_argument("--shots", default=None)
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    args.sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes.split(",")]
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    results = []
    for app in args.apps.split(","):
        try:
            run_app(args, app, results)
        except Exception as error:  # noqa: BLE001 - one app failing must not hide the others
            results.append({"case": app, "status": "FAIL", "detail": repr(error)[:400]})
            print(f"FAIL  {app}  {error!r}", flush=True)
    ok = bool(results) and all(r["status"] == "PASS" for r in results)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
    print(f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} cases pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
