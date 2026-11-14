# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the HASON TECH banner is visible in every app and every user interface (gtk3, real GUI).

Usage: python3 tests/runtime/check-banner-everywhere.py --instdir DIR [--display :171] [--out DIR]
           [--apps writer,calc,impress,draw,pdf] [--sizes 1366x768,1920x1080] [--shots DIR]

Owner decision 14/11/2026 (docs/BANNERS.md, "Every window"): no user interface hides the banner. Per app
(Writer, Sheets, Slides, Draw) every user interface the app offers is chosen in turn (.uno:ToolbarMode, as
View > User Interface does), and at every window size the screenshot must show exactly one banner:
  - exactly one visible accessible link named "<name> — <tagline>" (AT-SPI, as a screen reader finds it);
  - at least 260 x 75 logical px, inside the window, in its top chrome (above the document's middle);
  - drawn as one of the bundled artworks (recognised in the screenshot, never a text card).
HST PDF: the viewer's BannerScreen (HSTPdfInfo) is at least 260 x 75 and shows a bundled artwork.
Writes results.json and one screenshot per case (--shots: also copied there as <app>-<mode>-<size>.png);
exit 1 when any case has no banner, more than one, a small one or one that is not the artwork.
The X display must already run (this script never starts or stops it). Run as root, it runs itself again as the
build user under dbus-run-session (AT-SPI needs a session bus).
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_banner_probe as probe  # noqa: E402
from banner_everywhere_cases import MODES, NAMES, judge, mode_label, prop, visible_boxes  # noqa: E402
from ribbon_banner_run import geometry, xdo  # noqa: E402

def record(results, shots, case, path, ok, detail):
    results.append({"case": case, "status": "PASS" if ok else "FAIL", "detail": detail, "shot": path})
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}", flush=True)
    if shots:
        os.makedirs(shots, exist_ok=True)
        shutil.copy(path, os.path.join(shots, f"{case}.png"))


def run_app(args, app, catalogue, results):
    work = os.path.join(args.out, app)
    office = hst_gui.Office(args.instdir, work, hst_gui.free_port(), display=args.display,
                            extra_args=[f"--{app}"], nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"), appearance(args)])
    office.start()
    try:
        time.sleep(8)
        office.close_welcome()
        wid = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n][0]
        xdo(args.display, "windowmove", wid, "0", "0")
        frame = office.desktop().getCurrentFrame()
        for mode in MODES[app]:
            office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", mode),))
            time.sleep(4)
            for width, height in args.sizes:
                xdo(args.display, "windowsize", wid, str(width), str(height))
                time.sleep(4)
                box = geometry(args.display, wid)
                case = f"{app}-{mode_label(mode)}-{width}x{height}" + ("-dark" if args.appearance == "dark" else "")
                path = os.path.join(work, f"{case}.png")
                for attempt in range(2):  # a shot taken during the 300 ms cross-fade shows two cards
                    office.screenshot(path)
                    ok, detail = judge(visible_boxes(box), box, path, catalogue)
                    if ok or "artwork" not in detail:
                        break
                    time.sleep(1.5)
                record(results, args.shots, case, path, ok, detail)
        office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", "notebookbar.ui"),))  # back to the default
    finally:
        office.stop()


def appearance(args):
    return ("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", {"light": "1", "dark": "2"}[args.appearance])


def run_pdf(args, catalogue, results):
    import pdf_selection_highlight as selection
    import pdf_viewer_toolbar_layout as toolbar_layout
    from pdf_viewer_uno import info, open_viewer
    work = os.path.join(args.out, "pdf")
    os.makedirs(work, exist_ok=True)
    pdf = selection.write(os.path.join(work, "banner.pdf"))
    office = hst_gui.Office(args.instdir, os.path.join(work, "office"), hst_gui.free_port(), display=args.display,
                            config=[appearance(args)])
    office.start()
    try:
        frame, _ = open_viewer(office, pdf)
        time.sleep(2)
        wid = subprocess.run(["xdotool", "search", "--name", "HST PDF"], capture_output=True, text=True,
                             env=dict(os.environ, DISPLAY=args.display), check=True).stdout.split()[-1]
        xdo(args.display, "windowmove", wid, "0", "0")
        for width, height in args.sizes:
            xdo(args.display, "windowsize", wid, str(width), str(height))
            time.sleep(4)
            box = geometry(args.display, wid)
            case = f"pdf-toolbar-{width}x{height}" + ("-dark" if args.appearance == "dark" else "")
            path = os.path.join(work, f"{case}.png")
            for attempt in range(2):
                hst_gui.screenshot(path, args.display)
                data = info(office, frame)
                ok, detail = judge([list(data["BannerScreen"])] if data.get("BannerScreen") else [], box, path, catalogue)
                layout = data.get("ToolbarLayout", ())
                spread = toolbar_layout.row_spread(layout)
                count = len(toolbar_layout.rows([c for c in toolbar_layout.parse(layout) if c["id"] != "menu"]))
                if ok and count != 2:
                    ok, detail = False, f"the toolbar has {count} rows beside the banner, not 2"
                elif ok and spread > toolbar_layout.ROW_SPREAD:  # the two rows beside the banner end together
                    ok, detail = False, f"toolbar rows end {spread} px apart"
                elif ok:
                    detail += f"; toolbar rows end {spread} px apart"
                if ok or "artwork" not in detail:
                    break
                time.sleep(1.5)
            record(results, args.shots, case, path, ok, detail)
        frame.close(True)
    finally:
        office.stop()


def session_bus_call(*method):
    reply = subprocess.run(["dbus-send", "--session", "--print-reply=literal", *method], capture_output=True,
                           text=True, timeout=30, check=False)
    if reply.returncode:
        raise RuntimeError(f"dbus-send {method[1]} failed: {reply.stderr.strip()}")
    return reply.stdout.strip()


def private_atspi_bus():
    """This run's own AT-SPI bus (address, launcher pid), activated on the private session bus. libatspi, in the
    harness and in the office, reads AT_SPI_BUS_ADDRESS before the display's AT_SPI_BUS property, which an earlier
    run on a reused display may have left pointing at a bus this user cannot open."""
    address = session_bus_call("--dest=org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus.GetAddress")
    if not address.startswith(("unix:", "tcp:")):
        raise RuntimeError(f"no private AT-SPI bus address: {address!r}")
    pid = session_bus_call("--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
                           "org.freedesktop.DBus.GetConnectionUnixProcessID", "string:org.a11y.Bus").split()[-1]
    return address, int(pid)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":171")
    parser.add_argument("--out", default="tests/output/banner-everywhere")
    parser.add_argument("--apps", default="writer,calc,impress,draw,pdf")
    parser.add_argument("--sizes", default="1366x768,1920x1080")
    parser.add_argument("--shots", default=None)
    parser.add_argument("--appearance", choices=("light", "dark"), default="light")
    args = parser.parse_args()
    if os.geteuid() == 0:  # as the build user under a session bus of its own (AT-SPI needs one)
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    address, launcher = private_atspi_bus()  # dbus-run-session ends without stopping the launcher it activated
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", AT_SPI_BUS_ADDRESS=address)
    try:
        return run_cases(args)
    finally:
        try:
            os.kill(launcher, signal.SIGTERM)
        except ProcessLookupError:
            pass


def run_cases(args):
    args.sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes.split(",")]
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    catalogue, _ = probe.items(args.instdir)
    results = []
    for app in args.apps.split(","):
        try:
            if app == "pdf":
                run_pdf(args, catalogue, results)
            else:
                run_app(args, app, catalogue, results)
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
