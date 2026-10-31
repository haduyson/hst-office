# SPDX-License-Identifier: AGPL-3.0-only
"""Join UNO event timings with window samples: tab-probe-summary.py <out-dir> <mode> <pid>."""
import csv
import json
import sys

out, mode, pid = sys.argv[1], sys.argv[2], int(sys.argv[3])
events = json.load(open(f"{out}/events-{mode}.json", encoding="utf-8"))
origin = int(open(f"{out}/sampler-start-{mode}.txt", encoding="utf-8").read().strip())
rows = [(origin + int(r["t_ms"]), int(r["frontmost_pid"]), int(r["n_onscreen"]), int(r["n_fullscreen"]))
        for r in csv.DictReader(open(f"{out}/samples-{mode}.csv", encoding="utf-8")) if r["t_ms"].isdigit()]
starts = {e["event"][:-6]: e["t"] for e in events if e["event"].endswith(":start")}
print(f"## {mode}\n")
print("| action | call s | usable s | frontmost at end | zero-window ms | max windows | fullscreen change | front lost ms |")
print("|---|---|---|---|---|---|---|---|")
for e in events:
    if not e["event"].endswith(":end"):
        continue
    name = e["event"][:-4]
    t0 = starts.get(name)
    if t0 is None:
        continue
    win = [r for r in rows if t0 - 200 <= r[0] <= e["t"] + 1500]
    if not win:
        continue
    gap = 20 * sum(1 for r in win if r[2] == 0)
    lost = 20 * sum(1 for r in win if r[1] != pid)
    fs = sorted({r[3] for r in win})
    print(f"| {name} | {e.get('call', '')} | {e.get('usable', '')} | {e.get('frontmost', '')} | {gap} | "
          f"{max(r[2] for r in win)} | {'->'.join(map(str, fs))} | {lost} |")
for e in events:
    if e["event"] in ("enter-fullscreen",):
        print(f"\n{e['event']}: rc={e.get('rc')} {e.get('msg')}")
    if e["event"] == "cmdw:end":
        print(f"\nCmd+W: app frontmost afterwards = {e.get('frontmost')}, frames left = {e.get('frames')}")
