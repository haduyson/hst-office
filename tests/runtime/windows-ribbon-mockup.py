#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the Writer ribbon tabs Trang đầu and Chèn against the mockup vectors, on an INSTALLED HST Office.

Run in the console session (under C:\\hst-test\\console-lock.txt) with the office's python.exe:
  "<install>\\program\\python.exe" tests/runtime/windows-ribbon-mockup.py --install DIR --out DIR [--sweep-step 10]
The checks are those of check-ribbon-mockup.py (rules in ribbon_mockup_rules.py): ladder vectors, the 106 px body, the
147 px row, the banner rule, the font and size boxes, and optionally a monotonic sweep. The window is resized through
UNO (setPosSize on the frame's container window); the ribbon is read from the UNO accessibility tree. Only 100 %
scaling is measured here: set the display to 100 % before the run (windows_dpi.set_scale(100)).
Evidence: <out>/results.json, <out>/measured.json, <out>/writer-<tab>-<width>.bmp.
"""
import argparse
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
import windows_gui_a11y as a11y  # noqa: E402
import ribbon_mockup_geometry as geo  # noqa: E402
import ribbon_mockup_uno as uno_nodes  # noqa: E402
from ribbon_mockup_rules import monotonic_findings, width_findings  # noqa: E402

EXPECTED = os.path.join(HERE, "ribbon-mockup-expected.json")
TAB_NAMES = {"home": "Trang đầu", "insert": "Chèn"}
HEIGHT = 900


def find_tab(windows, name):
    """The page tab named `name` in the ribbon of the office windows (its accessibility context), or None."""
    import uno
    tab_role = uno.getConstantByName("com.sun.star.accessibility.AccessibleRole.PAGE_TAB")
    for window in windows:
        for context, _depth in a11y.walk(window, limit=20):
            try:
                if context.getAccessibleRole() == tab_role and context.getAccessibleName() == name:
                    return context
            except Exception:  # noqa: BLE001
                continue
    return None


def dump_tree(windows, path):
    """Writes the accessibility nodes of the windows (role, name, showing) for a missing tab: a diagnosis aid."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"top windows: {len(windows)}\n")
        for window in windows:
            count = 0
            for context, depth in a11y.walk(window, limit=20):
                count += 1
                try:
                    handle.write(f"{'  ' * depth}{context.getAccessibleRole()} | {context.getAccessibleName()!r} | "
                                 f"{a11y.showing(context)}\n")
                except Exception as error:  # noqa: BLE001
                    handle.write(f"{'  ' * depth}error {error!r}\n")
            handle.write(f"window nodes: {count}\n")


def measure(windows, tab):
    nodes = uno_nodes.ribbon_nodes(windows)
    tab_top, strip = geo.tab_geometry(nodes)
    return {"groups": geo.groups(nodes, tab), "tab_top": tab_top, "strip": strip, "banner": geo.banner(nodes),
            "font_box": geo.named_box(nodes, "Tên phông"), "size_box": geo.named_box(nodes, "Kích cỡ phông")}


def set_width(office, width):
    frame = office.desktop.getCurrentFrame()
    frame.getContainerWindow().setPosSize(0, 0, width, HEIGHT, 12)  # POSSIZE_WIDTH | POSSIZE_HEIGHT
    time.sleep(3)


OUT = [""]  # the evidence folder, set by main


def run_tab(res, office, tab, widths, expected, measured):
    levels = {}
    a11y_name = TAB_NAMES[tab]
    for width in widths:
        set_width(office, width)
        windows = office.top_windows()
        tab_context = find_tab(windows, a11y_name)
        if tab_context is None:
            dump_tree(windows, os.path.join(OUT[0], f"tree-{tab}-{width}.txt"))
            res(f"[writer {tab} {width}] tab '{a11y_name}' found", False, "no page tab")
            continue
        a11y.press(tab_context)
        time.sleep(2)
        got = measure(windows, tab)
        states = {k: v["state"] for k, v in got["groups"].items()}
        measured[f"{tab}-{width}"] = {"states": states, "banner": got["banner"], "font_box": got["font_box"]}
        key = f"{tab}-{width}"
        if key in expected:
            for name, ok, detail in width_findings(tab, width, expected[key]["states"], got):
                res(name, ok, detail)
        for group, value in got["groups"].items():
            levels.setdefault(group, []).append((width, value["state"]))
    return levels


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2391)
    parser.add_argument("--sweep-step", type=int, default=0)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    OUT[0] = args.out
    with open(EXPECTED, encoding="utf-8") as handle:
        expected = json.load(handle)["states"]
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    measured = {}
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        office.load("private:factory/swriter")
        time.sleep(6)
        wg.dismiss_startup(office, os.path.join(args.out, "doc-startup.png"), timeout=8, settle=2)
        for tab in ("home", "insert"):
            widths = sorted({int(k.split("-")[1]) for k in expected if k.startswith(tab + "-")})
            if args.sweep_step:
                widths = list(range(1100, 1921, args.sweep_step))
            levels = run_tab(res, office, tab, widths, expected, measured)
            for name, ok, detail in monotonic_findings(levels, tab):
                res(name, ok, detail)
    finally:
        office.stop()
    with open(os.path.join(args.out, "measured.json"), "w", encoding="utf-8") as handle:
        json.dump(measured, handle, ensure_ascii=False, indent=1, default=str)
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
