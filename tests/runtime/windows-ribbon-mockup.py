#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the Writer ribbon tabs Trang đầu and Chèn against the mockup vectors, on an INSTALLED HST Office.

Run in the console session (under C:\\hst-test\\console-lock.txt) with the office's python.exe:
  "<install>\\program\\python.exe" tests/runtime/windows-ribbon-mockup.py --install DIR --out DIR [--sweep-step 10]
The checks are those of check-ribbon-mockup.py (rules in ribbon_mockup_rules.py). The window is resized through UNO
(setPosSize on the frame's container window); the tab is selected and the ribbon is read through MSAA with
windows-msaa-ribbon.ps1 (select-tab) and windows-ribbon-nodes.ps1 (the node dump), the same tree the keytips tools read.
Only 100 % scaling is measured here: set the display to 100 % before the run.
Evidence: <out>/results.json, <out>/measured.json, <out>/nodes-<tab>-<width>.tsv (the dump of each measured width).
"""
import argparse
import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402
import ribbon_mockup_geometry as geo  # noqa: E402
import ribbon_mockup_msaa as msaa  # noqa: E402
from ribbon_mockup_rules import monotonic_findings, width_findings  # noqa: E402

EXPECTED = {"writer": os.path.join(HERE, "ribbon-mockup-expected.json"),
            "calc": os.path.join(HERE, "ribbon-mockup-expected-sheets.json")}  # by app
FACTORY = {"writer": "private:factory/swriter", "calc": "private:factory/scalc"}
APP = ["writer"]  # set by main
TAB_NAMES = {"home": "Trang đầu", "insert": "Chèn"}
HEIGHT = 900
POWERSHELL = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
OUT = [""]  # the evidence folder, set by main


SKIPS = []  # (name, detail) of the checks that are information or not measurable through MSAA


def emit(res, name, ok, detail):
    """A result to the Results log; a None result is a SKIP with its reason (kept in measured.json)."""
    if ok is None:
        SKIPS.append({"check": name, "detail": str(detail)})
        print(f"SKIP  {name}  {detail}", flush=True)
        return
    res(name, ok, detail)


def _run(script, *args):
    result = subprocess.run(POWERSHELL + [os.path.join(HERE, script), *args], capture_output=True, check=False)
    return result.stdout.decode("utf-8", errors="replace")


def select_tab(pids, name):
    """Selects the shown ribbon tab `name` through MSAA; True when the tool reports OK."""
    for pid in pids:
        if _run("windows-msaa-ribbon.ps1", "-Action", "select-tab", "-OfficePid", str(pid), "-Name", name).startswith("OK"):
            return True
    return False


def dump_nodes(pids, tab, width):
    """The ribbon band nodes of the first office process whose tree holds page tabs; keeps the raw dump as evidence."""
    for pid in pids:
        text = _run("windows-ribbon-nodes.ps1", "-OfficePid", str(pid))
        if "\t37\t" in text or "\t37\r" in text:  # MSAA PAGETAB
            with open(os.path.join(OUT[0], f"nodes-{tab}-{width}.tsv"), "w", encoding="utf-8") as handle:
                handle.write(text)
            return msaa.parse(text)
    return []


def set_width(office, width):
    frame = office.desktop.getCurrentFrame()
    frame.getContainerWindow().setPosSize(0, 0, width, HEIGHT, 12)  # POSSIZE_WIDTH | POSSIZE_HEIGHT
    time.sleep(3)


def measure(nodes, tab):
    tab_top, strip = geo.tab_geometry(nodes)
    return {"groups": geo.groups(nodes, tab, APP[0]), "tab_top": tab_top, "strip": strip, "banner": geo.banner(nodes),
            "page": geo.page_box(nodes, tab_top),
            "font_box": geo.named_box(nodes, "Tên phông"), "size_box": geo.named_box(nodes, "Kích cỡ phông")}


def run_tab(res, office, tab, widths, expected, measured):
    levels = {}
    for width in widths:
        set_width(office, width)
        pids = sorted(office.bin_pids_of_profile())
        if not select_tab(pids, TAB_NAMES[tab]):
            res(f"[writer {tab} {width}] tab '{TAB_NAMES[tab]}' selected through MSAA", False, "no shown tab")
            continue
        time.sleep(2)
        nodes = dump_nodes(pids, tab, width)
        got = measure(nodes, tab)
        states = {k: v["state"] for k, v in got["groups"].items()}
        key = f"{tab}-{width}"
        measured[key] = {"states": states, "banner": got["banner"], "font_box": got["font_box"], "nodes": len(nodes)}
        if key in expected:
            for name, ok, detail in width_findings(tab, width, expected[key]["states"], got):
                emit(res, name, ok, detail)
        for group, value in got["groups"].items():
            levels.setdefault(group, []).append((width, value["state"]))
    return levels


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2391)
    parser.add_argument("--sweep-step", type=int, default=0)
    parser.add_argument("--app", default="writer", choices=sorted(EXPECTED))
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    OUT[0] = args.out
    APP[0] = args.app
    with open(EXPECTED[args.app], encoding="utf-8") as handle:
        expected = json.load(handle)["states"]
    if args.app == "calc":  # Sheets: the cell styles are part of Kiểu (owner decision)
        for value in expected.values():
            value["states"].pop("cellstyles", None)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    measured = {}
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        office.load(FACTORY[args.app])
        time.sleep(6)
        wg.dismiss_startup(office, os.path.join(args.out, "doc-startup.png"), timeout=8, settle=2)
        for tab in ("home", "insert"):
            widths = sorted({int(k.split("-")[1]) for k in expected if k.startswith(tab + "-")})
            if args.sweep_step:
                widths = list(range(1100, 1921, args.sweep_step))
            levels = run_tab(res, office, tab, widths, expected, measured)
            for name, ok, detail in monotonic_findings(levels, tab):
                emit(res, name, ok, detail)
    finally:
        office.stop()
    with open(os.path.join(args.out, "measured.json"), "w", encoding="utf-8") as handle:
        json.dump({"measured": measured, "skipped": SKIPS}, handle, ensure_ascii=False, indent=1, default=str)
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
