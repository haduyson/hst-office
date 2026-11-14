# SPDX-License-Identifier: AGPL-3.0-only
"""The steps of check-toolbar-two-rows.py and check-windows-toolbar-two-rows.py (same cases on Linux and Windows).

`office` is any object with ctx, screenshot(path) and dispatch(frame, command, args); `args` has out and shots.
"""
import os
import shutil
import time

import toolbar_two_rows_probe as probe

SINGLE = "private:resource/toolbar/singlemode"
GUEST = "private:resource/toolbar/textobjectbar"
LABELS = {"Default": "standard", "Single": "single-toolbar", "Sidebar": "sidebar"}


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def record(args, results, case, path, ok, detail, data=None):
    results.append({"case": case, "status": "PASS" if ok else "FAIL", "detail": detail, "shot": path, "data": data})
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}", flush=True)
    if args.shots and path:
        os.makedirs(args.shots, exist_ok=True)
        shutil.copy(path, os.path.join(args.shots, f"{case}.png"))


def check(args, office, frame, results, app, mode, case, expect_two=True):
    time.sleep(3)
    path = os.path.join(args.out, f"{case}.png")
    office.screenshot(path)
    data = probe.measure(frame)
    ok, detail = probe.judge(app, mode if expect_two else "Default", data)
    record(args, results, case, path, ok, detail, data)


def window_state(office, app_module, url):
    states = office.ctx.getValueByName("/singletons/com.sun.star.ui.theWindowStateConfiguration")
    data = dict((p.Name, p.Value) for p in states.getByName(app_module).getByName(url))
    return {k: str(v) for k, v in data.items() if k in ("Docked", "DockingArea", "DockPos", "Locked", "Visible")}


def transitions(args, office, frame, results, tag):
    """Writer, Single toolbar: the other toolbar layouts and back, persisted state untouched."""
    layout = frame.LayoutManager
    module = "com.sun.star.text.TextDocument"
    before = window_state(office, module, SINGLE)
    layout.showElement(GUEST)
    check(args, office, frame, results, "writer", "Single", f"writer-single-guest-toolbar{tag}", expect_two=False)
    layout.hideElement(GUEST)
    check(args, office, frame, results, "writer", "Single", f"writer-single-guest-gone{tag}")
    layout.lockWindow(SINGLE)
    check(args, office, frame, results, "writer", "Single", f"writer-single-locked{tag}")
    layout.unlockWindow(SINGLE)
    layout.floatWindow(SINGLE)
    time.sleep(3)
    floating = layout.isElementFloating(SINGLE)
    record(args, results, f"writer-single-floating{tag}", None, floating, "floats" if floating else "still docked")
    layout.dockWindow(SINGLE, 0, top_left())  # DockingArea_DOCKINGAREA_TOP, first row
    check(args, office, frame, results, "writer", "Single", f"writer-single-docked-again{tag}")
    after = window_state(office, module, SINGLE)
    record(args, results, f"writer-single-window-state{tag}", None, after == before, f"before {before}, after {after}")


def run_modes(args, office, frame, app, results, tag, resize):
    """Every toolbar user interface of `app` at every size of args.sizes; Writer also goes through transitions()."""
    for mode in probe.MODES[app]:
        office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", mode),))
        time.sleep(4)
        for width, height in args.sizes:
            resize(width, height)
            check(args, office, frame, results, app, mode, f"{app}-{LABELS[mode]}-{width}x{height}{tag}")
    if app == "writer":
        office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", "Single"),))
        time.sleep(4)
        transitions(args, office, frame, results, tag)
    office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", "notebookbar.ui"),))  # back to the default


def top_left():
    import uno
    return uno.createUnoStruct("com.sun.star.awt.Point", 0, 0)
