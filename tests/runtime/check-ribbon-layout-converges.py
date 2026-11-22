# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Checks that the ribbon's layout settles: after a resize and a tab switch, the next idle lays the ribbon out a few
times at most, not without end (a menu button's look and its group's look setting its style differently asked for a
new layout from every layout: the app used a CPU core while idle and the layout dump caught passes half done).

Usage: python3 tests/runtime/check-ribbon-layout-converges.py --instdir DIR --out DIR [--display :283]
           [--apps writer,calc] [--widths 1366,1536] [--idle 6] [--max-passes 4] [--max-cpu 0.05]

For every app, width and ribbon tab (opened through AT-SPI): the window is resized and the tab opened, the app gets
SETTLE seconds, then for --idle seconds nothing happens and the check measures
  - the fit passes of the ribbon's pages (<dumps>/layout-passes, written by hst-ribbon-v3-layout.patch under
    HST_RIBBON_DUMP_LAYOUT): at most --max-passes more (a build without the counter: not measured);
  - the CPU time of soffice.bin: at most --max-cpu of the idle time (the same loop on any build).
Writes <out>/converges.json; exit status 1 when a case fails. The X display must already run (as for
collect-ribbon-v3-dumps.py, whose office start it reuses).
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

_spec = importlib.util.spec_from_file_location("collect_ribbon_v3_dumps", os.path.join(HERE, "collect-ribbon-v3-dumps.py"))
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)

SETTLE = 3.0  # seconds after a resize or a tab switch before the idle window starts
CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


def cpu_seconds(pid):
    """User and system CPU time of a process so far (all its threads), in seconds; None when it is gone."""
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as handle:
            fields = handle.read().rsplit(")", 1)[1].split()
    except OSError:
        return None
    return (int(fields[11]) + int(fields[12])) / CLOCK_TICKS  # utime, stime (fields 14, 15 of stat)


def layout_passes(dumps):
    """The ribbon's fit passes so far, None for a build that does not count them."""
    try:
        with open(os.path.join(dumps, "layout-passes"), encoding="ascii") as handle:
            return int(handle.read().strip() or 0)
    except (OSError, ValueError):
        return None


def idle_window(office, dumps, seconds):
    """(fit passes, CPU share) of soffice.bin while nothing happens for SECONDS (passes None: not counted)."""
    pid = office.pid
    passes, cpu, start = layout_passes(dumps), cpu_seconds(pid), time.monotonic()
    time.sleep(seconds)
    passes_after, cpu_after, elapsed = layout_passes(dumps), cpu_seconds(pid), time.monotonic() - start
    delta = None if passes is None or passes_after is None else passes_after - passes
    share = None if cpu is None or cpu_after is None else (cpu_after - cpu) / elapsed
    return delta, share


def verdict(case, delta, share, args):
    problems = []
    if delta is not None and delta > args.max_passes:
        problems.append(f"{delta} layout passes while idle (at most {args.max_passes})")
    if share is None:
        problems.append("soffice.bin is gone")
    elif share > args.max_cpu:
        problems.append(f"{share:.0%} of a CPU while idle (at most {args.max_cpu:.0%})")
    return {"case": case, "passes": delta, "cpu": None if share is None else round(share, 3), "problems": problems}


def check_app(args, app):
    dumps = os.path.join(args.out, "dumps", app)
    os.makedirs(dumps, exist_ok=True)
    office, window = collect.start(args.instdir, app, args.display, os.path.join(args.out, "work", app), dumps)
    results = []
    try:
        for width in args.widths:
            gui.xdo(args.display, "windowsize", window, str(width), str(args.height))
            time.sleep(SETTLE)
            results.append(verdict(f"{app} w{width} resize", *idle_window(office, dumps, args.idle), args))
            for name in [n for n in gui.visible_names() if n and n != "Tệp tin"]:
                if not gui.open_tab(args.display, name):
                    results.append({"case": f"{app} w{width} {name}", "problems": ["cannot open the tab"]})
                    continue
                time.sleep(SETTLE)
                results.append(verdict(f"{app} w{width} {name}", *idle_window(office, dumps, args.idle), args))
    finally:
        office.stop()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":283")
    parser.add_argument("--apps", default="writer,calc")
    parser.add_argument("--widths", default="1366,1536")
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--idle", type=float, default=6.0, help="seconds of each idle window")
    parser.add_argument("--max-passes", type=int, default=4, help="fit passes allowed in an idle window")
    parser.add_argument("--max-cpu", type=float, default=0.05, help="share of a CPU allowed while idle")
    args = parser.parse_args()
    args.widths = [int(w) for w in args.widths.split(",") if w]
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "NO_AT_BRIDGE=0",
                              "GTK_MODULES=gail:atk-bridge", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    hst_gui.setup_uno(args.instdir)
    results = []
    for app in args.apps.split(","):
        try:
            results += check_app(args, app)
        except Exception as error:  # noqa: BLE001 - report the app and go on with the others
            results.append({"case": app, "problems": [f"error: {error}"]})
    with open(os.path.join(args.out, "converges.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    failed = [r for r in results if r["problems"]]
    for result in results:
        mark = "FAIL" if result["problems"] else "PASS"
        print(f"{mark}  {result['case']}  passes={result.get('passes')} cpu={result.get('cpu')}  "
              + "; ".join(result["problems"]), flush=True)
    print(f"{len(results)} cases, {len(failed)} failed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
