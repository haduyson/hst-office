# SPDX-License-Identifier: AGPL-3.0-only
"""Summarise one start-up probe run: startup-probe-summary.py <run-dir> <label> [close_ms].

Reads <run-dir>/launch.txt (epoch ms of the launch), samples.csv (startup-probe-sampler) and, when the
welcome dialog was closed by the probe, <run-dir>/closed.txt (epoch ms). Prints one markdown table row per
event: first window, welcome dialog (a window that appears after the first one and is smaller than it),
close, and the first moment after the close when only the large Start Center window is left."""
import csv
import sys
from pathlib import Path


def read_int(path):
    try:
        return int(Path(path).read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def size(text):
    width, height = text.split("x")
    return int(width), int(height)


def main(run, label):
    run = Path(run)
    launch, closed = read_int(run / "launch.txt"), read_int(run / "closed.txt")
    rows = [(int(r["epoch_ms"]), [size(s) for s in r["windows"].split("|") if s]) for r in csv.DictReader(open(run / "samples.csv"))]
    events = []
    first = next((t for t, w in rows if w), None)
    events.append(("first window on screen", first))
    big = max((s for _t, w in rows for s in w), key=lambda s: s[0] * s[1], default=None)
    dialog = None
    if big:
        dialog = next((t for t, w in rows if any(s[0] * s[1] < big[0] * big[1] * 0.7 for s in w) and t >= (first or 0)), None)
        center = next((t for t, w in rows if big in w), None)
        events.append(("Start Center-size window on screen", center))
        events.append(("smaller window (welcome dialog) on screen", dialog))
    if closed:
        events.append(("welcome closed by probe", closed))
        after = next((t for t, w in rows if t >= closed and w and all(s == big for s in w)), None)
        events.append(("only the Start Center left after close", after))
    print(f"\n#### {label}\n\n| event | ms after launch |\n|---|---|")
    for name, stamp in events:
        print(f"| {name} | {stamp - launch if stamp and launch else 'n/a'} |")


main(sys.argv[1], sys.argv[2])
