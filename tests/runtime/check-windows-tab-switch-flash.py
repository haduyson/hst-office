#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Switching document tabs or windows never shows the desktop for a moment, on an INSTALLED HST Office (Windows).

A tab switch shows the window of the new tab and hides the old one. Before hst-document-tab-switch-no-flash.patch
the new window had no picture yet when the old one was hidden, so the desktop showed through on every switch (error
report HSTO-000006). The matrix (tab_switch_flash_matrix.py): window modes office (one HST Office window with tabs of
every application and the Start Center), tabs (one window per application) and windows (separate windows); every
same-application and cross-application switch they offer; light or dark application colours. While the switches run,
screen_dxgi_win samples a grid of patches of the work area in every frame the compositor presents. A sampled frame of a
switch that shows the desktop (grabbed before the office started) where neither the screen before nor after the switch
does is a flash; a frame showing neither (blank or half painted window) is counted as partial.

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-tab-switch-flash.py --install DIR --out DIR
[--port 2167] [--modes office,tabs,windows] [--apps writer,calc,impress,draw,pdf] [--switches 22]
[--appearance light|dark]. Evidence: <out>/results.json, <out>/switches.jsonl. Exit 1 when a switch flashed.
"""
import argparse
import ctypes
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import screen_dxgi_win as dx  # noqa: E402
import tab_switch_flash_matrix as matrix  # noqa: E402
import windows_gui as wg  # noqa: E402


def work_area():
    rect = (ctypes.c_long * 4)()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, rect, 0)  # SPI_GETWORKAREA
    return tuple(rect)


class Office(wg.WinOffice):
    def set_config(self, node, name, value):
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (matrix.prop("nodepath", node),))
        access.setPropertyValue(name, value)
        access.commitChanges()


def start(office, out, appearance):
    office.start(fresh=True)
    wg.dismiss_startup(office, os.path.join(out, "startup.png"), timeout=30, settle=5)
    office.set_config("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", 2 if appearance == "dark" else 1)
    office.set_config("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", False)
    # a warm profile whose start shows no question: loads right after a start-up question crashed this harness
    for attempt in range(3):
        office.stop()
        office.start()
        if not wg.dismiss_startup(office, os.path.join(out, "startup-%d.png" % attempt), timeout=15, settle=3):
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2167)
    parser.add_argument("--modes", default="office,tabs,windows")
    parser.add_argument("--apps", default="writer,calc,impress,draw,pdf")
    parser.add_argument("--switches", type=int, default=22)
    parser.add_argument("--appearance", default="light", choices=("light", "dark"))
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    check = wg.Results(out, "tab-switch-flash")
    patches = dx.DxgiPatches(work_area())  # every presented frame (Desktop Duplication)
    desktop = patches.grab()  # before the office starts: the picture a flash shows
    office = Office(args.install, os.path.join(out, "profile"), args.port, os.path.join(out, "log"))
    log = open(os.path.join(out, "switches.jsonl"), "a", encoding="utf-8")
    try:
        start(office, out, args.appearance)
        pids = matrix.own_pids(office.profile)
        for mode in args.modes.split(","):
            try:
                matrix.open_documents(office, args.apps.split(","), mode, os.path.join(out, "docs", mode))
                for window, _title in wg.dialogs(office):
                    wg.close_dialog(window)
                if mode == "tabs":  # one window per application: switch in each of them
                    windows = matrix.visible_frames(office)
                    rows = [row for frame in windows for row in matrix.measure(
                        office, pids, patches, desktop, mode, max(args.switches // len(windows), 4), wg.chord, frame)]
                else:
                    rows = matrix.measure(office, pids, patches, desktop, mode, args.switches, wg.chord)
            except Exception as error:  # noqa: BLE001 - report the mode, go on with the next
                check("%s: switches ran" % mode, False, repr(error))
                rows = []
            for row in rows:
                log.write(json.dumps(dict(zip(("from", "to", "driven", "frames", "desktop", "partial", "capture", "odd"), row),
                                          mode=mode, appearance=args.appearance)) + "\n")
            pairs = {}
            for before, after, driven, _n, flash, partial, rate, _odd in rows:
                pairs.setdefault((before, after), []).append((driven, flash, partial, rate))
            for (before, after), items in sorted(pairs.items()):
                flashes = sum(1 for _d, f, _p, _r in items if f)
                detail = "%d switches, %d with desktop frames, %d with partial frames, capture %s, driven %s" % (
                    len(items), flashes, sum(1 for _d, _f, p, _r in items if p), items[0][3],
                    sorted({d for d, _f, _p, _r in items}))
                check("%s %s: %s -> %s shows no desktop" % (args.appearance, mode, before, after),
                      flashes == 0 and not any(d.startswith("skipped") for d, _f, _p, _r in items), detail)
            matrix.close_all(office)
    finally:
        log.close()
        office.stop()
        patches.close()
    return check.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
