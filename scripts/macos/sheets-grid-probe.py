#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Open a new HST Sheets document, type values over UNO and screenshot the grid at several zoom levels.

  sheets-grid-probe.py <office-pid> <out-dir> <label>

Run with the bundled Python while soffice listens on pipe "hstsheetgrid". Writes <label>-zoom<N>.png (full screen)
and <label>-zoom<N>.json with the zoom read back, the cell values read back and a grid-line count taken from a
vertical strip of the screenshot by sheets-grid-lines.py (run afterwards with a Python that has Pillow).
Evidence only: a missed measurement never fails the probe.
"""
import json
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

pid, out, label = int(sys.argv[1]), sys.argv[2], sys.argv[3]
# direct: a spreadsheet loaded straight from the factory URL; startcenter: the Start Center button path
mode = sys.argv[4] if len(sys.argv) > 4 else "direct"
ZOOMS = [100, 50, 200]


def pv(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def front():
    subprocess.run(["osascript", "-e",
                    'tell application "System Events" to set frontmost of (first process whose unix id is %d) to true' % pid],
                   check=False, timeout=30)


def shot(name):
    path = os.path.join(out, name)
    subprocess.run(["screencapture", "-x", path], check=False, timeout=60)
    return path


local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
ctx = None
for _ in range(180):
    try:
        ctx = resolver.resolve("uno:pipe,name=hstsheetgrid;urp;StarOffice.ComponentContext")
        break
    except Exception:
        time.sleep(1)
if ctx is None:
    print(json.dumps({"label": label, "error": "no UNO connection"}), flush=True)
    sys.exit(0)

desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
if mode == "startcenter":
    # Same route as the Start Center "Bảng tính" tile: its dispatch of private:factory/scalc with target _default,
    # sent through the current (Start Center) frame. Mouse clicks are not used.
    time.sleep(8)
    front()
    time.sleep(2)
    shot(f"{label}-startcenter.png")
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = "private:factory/scalc"
    frame = desktop.getCurrentFrame()
    dispatch = frame.queryDispatch(url, "_default", 0)
    dispatch.dispatch(url, ())
    doc = None
    for _ in range(60):
        cur = desktop.getCurrentComponent()
        if cur is not None and cur.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
            doc = cur
            break
        time.sleep(1)
    if doc is None:
        print(json.dumps({"label": label, "error": "no spreadsheet after the Start Center dispatch"}), flush=True)
        sys.exit(0)
    time.sleep(4)
else:
    doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (pv("Hidden", False),))
    time.sleep(4)
sheet = doc.Sheets.getByIndex(0)
sheet.getCellByPosition(0, 0).setValue(12345)
sheet.getCellByPosition(1, 1).setString("abc")
doc.calculateAll()
ctrl = doc.CurrentController
front()
time.sleep(2)

results = []
for z in ZOOMS:
    rec = {"label": label, "zoom_target": z}
    try:
        ctrl.ZoomValue = z
        time.sleep(3)
        rec["zoom_read"] = ctrl.ZoomValue
    except Exception as exc:  # the probe keeps going and records the failure
        rec["zoom_error"] = str(exc)
    rec["a1"] = sheet.getCellByPosition(0, 0).getString()
    rec["b2"] = sheet.getCellByPosition(1, 1).getString()
    front()
    time.sleep(1)
    name = f"{label}-zoom{z}.png"
    path = shot(name)
    rec["screenshot"] = name
    rec["grid_line_rows"] = None  # filled by sheets-grid-lines.py, which needs Pillow
    with open(os.path.join(out, f"{label}-zoom{z}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    results.append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)

doc.close(True)
