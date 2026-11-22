#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Windows: the v3 ribbon's layout dumps and screenshots of every main tab, on an INSTALLED HST Office (console session).

The office runs maximised with HST_RIBBON_DUMP_LAYOUT=<out>\\dumps\\<app>-<label>-live (hst-ribbon-v3-layout.patch
writes <box>-<logical width>.json when a tab's banner is placed). Every shown ribbon tab but "Tệp tin" is clicked
(rectangles through MSAA, windows-msaa-ribbon.ps1) and the screen's top RIBBON_HEIGHT px are saved as
<out>\\shots\\<app>-<label>-<index>.png; the dumps move to <out>\\dumps\\<app>-<label>\\. --label names the run (the
display scaling, e.g. 100 or 125: set it before, tests/runtime/r1auto/scaling.py). Check the dumps on Linux with
check-ribbon-v3-dumps.py. Usage (console session, under C:\\hst-test\\console-lock.txt):
  "<install>\\program\\python.exe" tests/runtime/collect-windows-ribbon-v3-dumps.py --install DIR --out DIR --label 100
Evidence: <out>\\collected-<label>.json, the shots and the dumps.
"""
import argparse
import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402

APPS = {"writer": ("private:factory/swriter", "HST Writer"), "calc": ("private:factory/scalc", "HST Sheets"),
        "impress": ("private:factory/simpress", "HST Slides"), "draw": ("private:factory/sdraw", "HST Draw")}
MSAA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows-msaa-ribbon.ps1")
RIBBON_HEIGHT = 260  # screen px kept: title, tab row and ribbon body at 125 %


def tab_rects(office):
    """[(name, (x, y, w, h))] of the shown ribbon tabs, left to right."""
    pid = office.bin_pids_of_profile()[0]
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", MSAA, "-Action", "rects",
                          "-OfficePid", str(pid)], capture_output=True, timeout=180, check=False)
    tabs = []
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        parts = line.strip().split(" ", 5)
        if len(parts) == 6 and parts[0] == "RECT":
            box = tuple(int(v) for v in parts[1:5])
            # the ribbon's tab row is at the window's top: Calc's sheet tabs and Draw's layer tabs are page tabs too
            if box[2] > 0 and box[3] > 0 and box[1] < 300:
                tabs.append((parts[5], box))
    return sorted(tabs, key=lambda tab: tab[1][0])


def crop_top(path):
    try:
        from PIL import Image
    except ImportError:  # the office's own python has no Pillow: the full screen stays, cropped on Linux
        return
    image = Image.open(path)
    image.crop((0, 0, image.width, min(image.height, RIBBON_HEIGHT))).save(path)


def collect(app, args, res):
    factory, title = APPS[app]
    live = os.path.join(args.out, "dumps", f"{app}-{args.label}-live")
    target = os.path.join(args.out, "dumps", f"{app}-{args.label}")
    os.makedirs(live, exist_ok=True)
    os.makedirs(target, exist_ok=True)
    os.environ["HST_RIBBON_DUMP_LAYOUT"] = live  # soffice inherits it
    os.environ["HST_RIBBON_DUMP_APP"] = app
    profile = os.path.join(args.out, f"profile-{app}")
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    names = []
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, f"{app}-startup.png"))
        office.load(factory)
        time.sleep(6)
        wg.dismiss_startup(office, os.path.join(args.out, f"{app}-doc-startup.png"), timeout=8, settle=2)
        office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
        time.sleep(4)
        window = wg.find_window(lambda text: title in text, timeout=30)
        if not res(f"[{app}] window", bool(window)):
            return names
        wg.foreground(window[0])
        tabs = [t for t in tab_rects(office) if t[0] != "Tệp tin"]
        res(f"[{app}] ribbon tabs found", len(tabs) >= 4, [t[0] for t in tabs])
        for index, (name, box) in enumerate(tabs):
            wg.click(box[0] + box[2] // 2, box[1] + box[3] // 2)
            time.sleep(2)
            shot = os.path.join(args.out, "shots", f"{app}-{args.label}-{index:02d}.png")
            os.makedirs(os.path.dirname(shot), exist_ok=True)
            wg.screenshot(shot, cursor=False)
            crop_top(shot)
            names.append(name)
        for name in os.listdir(live):
            os.replace(os.path.join(live, name), os.path.join(target, name))
        res(f"[{app}] dumps written", len(os.listdir(target)) >= len(tabs), len(os.listdir(target)))
    finally:
        try:
            office.desktop.getCurrentComponent().setModified(False)
        except Exception:  # noqa: BLE001 - no document, or the office is gone
            pass
        office.stop()
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default="100")
    parser.add_argument("--apps", default="writer,calc,impress,draw")
    parser.add_argument("--port", type=int, default=2383)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    res = wg.Results(args.out, os.path.join(args.out, "profile"))
    collected = {}
    for app in args.apps.split(","):
        try:
            collected[app] = collect(app, args, res)
        except Exception as error:  # noqa: BLE001 - one app's failure must not lose the others
            res(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, f"collected-{args.label}.json"), "w", encoding="utf-8") as handle:
        json.dump(collected, handle, ensure_ascii=False, indent=1)
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
