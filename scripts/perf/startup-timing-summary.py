#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Markdown table of every <label>.json that scripts/perf/startup-timing.py wrote in a directory.

Usage: startup-timing-summary.py OUT-DIR
"""
import glob
import json
import os
import sys


def rows(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    for start in data["starts"]:
        p, py = start["phases"], start.get("python") or {}
        slow = ", ".join("%s %.2f" % tuple(item) for item in py.get("slowest", [])[:4])
        net = [n for n in py.get("network", []) if n[3] == "MainThread"]
        before = py.get("before_frame") or {}
        yield "| %s | %d %s | %s | %s | %s | %d | %s | %s | %s | %s | %s |" % (
            data["label"], start["start"], start["kind"], p["launch_to_frame_s"], p["splash_shown"],
            p["splash_visible_s"], len(p["pids"]), start["exit"], py.get("python_init_s", ""), before.get("imports_s", ""),
            "%s in %s s" % (before.get("compiled", ""), before.get("compile_s", "")) if before else "",
            ("%d HST modules; %s; main-thread net %d" % (len(before.get("hst_modules", [])), slow, len(net))) if py else "")


def main():
    out = sys.argv[1]
    print("| run | start | launch to frame s | splash shown s | splash visible s | processes | exit | python up s |"
          " imports before frame s | compiled before frame | slowest imports s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for path in sorted(glob.glob(os.path.join(out, "*.json"))):
        if path.endswith("-samples.json"):
            continue
        try:
            for row in rows(path):
                print(row)
        except (KeyError, ValueError, TypeError) as error:
            print("| %s | unreadable: %s |" % (os.path.basename(path), error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
