#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Two even toolbar rows beside the window banner, on an INSTALLED HST Office (Windows).

The Windows counterpart of check-toolbar-two-rows.py (cases and judgement: toolbar_two_rows_steps.py and
toolbar_two_rows_probe.py). --scale sets the display's scale first (r1auto/windows_dpi.py, applied at once, 100% again
at the end); without it the session's scale is used. Usage:
"<install>\\program\\python.exe" tests/runtime/check-windows-toolbar-two-rows.py --install DIR --out DIR
[--apps writer,calc,impress,draw] [--sizes 1366x768,1920x1080] [--appearance light|dark] [--scale 150]
[--port 2171]
Run it in an interactive session (the console one only with C:\\hst-test\\console-lock.txt held). Evidence:
<out>/results.json and one full-screen PNG per case. Exit 1 on any FAIL.
"""
import argparse
import ctypes
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), "r1auto"))
import toolbar_two_rows_probe as probe  # noqa: E402
import toolbar_two_rows_steps as steps  # noqa: E402
import windows_gui as wg  # noqa: E402

FACTORY = {"writer": "private:factory/swriter", "calc": "private:factory/scalc",
           "impress": "private:factory/simpress", "draw": "private:factory/sdraw"}


class Adapter:
    """wg.WinOffice with the interface toolbar_two_rows_steps expects."""

    def __init__(self, office):
        self.office = office
        self.ctx = office.ctx

    def screenshot(self, path):
        wg.screenshot(path, cursor=False)

    def dispatch(self, frame, command, args=()):
        helper = self.office.service("com.sun.star.frame.DispatchHelper")
        return helper.executeDispatch(frame, command, "", 0, tuple(args))


def set_config(office, node, name, value):
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
                                                  (steps.prop("nodepath", node),))
    access.setPropertyValue(name, value)
    access.commitChanges()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--sizes", default="1366x768,1920x1080")
    parser.add_argument("--appearance", choices=("light", "dark"), default="light")
    parser.add_argument("--scale", type=int, default=0)
    parser.add_argument("--port", type=int, default=2171)
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    args.shots = None
    args.sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes.split(",")]
    os.makedirs(args.out, exist_ok=True)
    if args.scale:
        from windows_dpi import set_scale
        set_scale(args.scale)
        time.sleep(5)
    try:
        return run(args)
    finally:
        if args.scale:
            set_scale(100)


def run(args):
    scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) if hasattr(ctypes, "windll") else 100
    tag = f"-{scale}pct" + ("-dark" if args.appearance == "dark" else "")
    results = []
    office = wg.WinOffice(args.install, os.path.join(args.out, "profile"), args.port, os.path.join(args.out, "log"),
                          nodefault=True)
    try:
        office.start(fresh=True)
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"), timeout=30, settle=5)
        set_config(office, "/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                   {"light": 1, "dark": 2}[args.appearance])
        set_config(office, "/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", False)  # no template dialog
        adapter = Adapter(office)
        args.snapshot = lambda: probe.snapshot_msaa(os.path.abspath(args.install))
        for app in args.apps.split(","):
            try:
                document = office.load(FACTORY[app])
                frame = document.getCurrentController().getFrame()
                window = frame.getContainerWindow()
                time.sleep(4)

                def resize(width, height, window=window):
                    import uno
                    top = window.queryInterface(uno.getTypeByName("com.sun.star.awt.XTopWindow2"))
                    if top is not None:
                        top.IsMaximized = False  # a maximized window keeps the screen's size
                    time.sleep(1)
                    window.setPosSize(0, 0, width, height, 15)  # PosSize.POSSIZE, physical px

                steps.run_modes(args, adapter, frame, app, results, tag, resize)
                try:
                    document.setModified(False)
                    document.close(True)
                except Exception:  # noqa: BLE001 - a CloseVetoException: the frame goes anyway
                    frame.dispose()
            except Exception as error:  # noqa: BLE001 - one app failing must not hide the others
                results.append({"case": app + tag, "status": "FAIL", "detail": repr(error)[:400]})
                print(f"FAIL  {app}{tag}  {error!r}", flush=True)
    finally:
        office.stop()
    ok = bool(results) and all(r["status"] == "PASS" for r in results)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": results, "pass": ok}, handle, ensure_ascii=False, indent=1)
    print(f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} cases pass")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
