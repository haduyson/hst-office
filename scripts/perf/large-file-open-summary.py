# SPDX-License-Identifier: AGPL-3.0-only
"""Markdown table of scripts/perf/large-file-open.py results: python large-file-open-summary.py <out-dir>.

One row per file, one column per label: "load / ready s, peak MB" (median over runs), "TIMEOUT@s" when the open did
not finish, "ERR" with the error text below the table.
"""
import json
import os
import statistics
import sys


def main():
    out = sys.argv[1]
    rows, labels, errors = {}, [], []
    for name in sorted(os.listdir(out)):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(out, name), encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["label"] not in labels:
                    labels.append(r["label"])
                rows.setdefault((r["file"], r.get("size_mb")), {}).setdefault(r["label"], []).append(r)
    print("| file | MB | " + " | ".join(labels) + " |")
    print("|---|---|" + "---|" * len(labels))
    for (fname, size), by in sorted(rows.items()):
        cells = []
        for label in labels:
            runs = by.get(label, [])
            ok = [r for r in runs if "error" not in r]
            if ok:
                med = lambda k: statistics.median(r[k] for r in ok if k in r) if any(k in r for r in ok) else None  # noqa: E731
                cell = "%s / %s s, %d MB" % (med("load"), med("idle"), max(r["peak_mb"] for r in ok))
                if med("save") is not None:
                    cell += ", save %s s" % med("save")
                if any(r.get("modified") for r in ok):
                    cell += ", modified"
            elif runs:
                r = runs[-1]
                cell = "TIMEOUT@%s s (load %s), %d MB" % (r.get("after"), r.get("load", "-"), r["peak_mb"]) \
                    if r["error"] == "timeout" else "ERR"
            else:
                cell = ""
            for r in runs:
                if "error" in r and r["error"] != "timeout":
                    errors.append("%s %s: %s" % (label, fname, r["error"]))
            cells.append(cell)
        print("| %s | %s | %s |" % (fname, size, " | ".join(cells)))
    print("\nload = loadComponentFromURL returned; ready = office idle after it (visible window); median of runs.")
    for e in errors:
        print("- " + e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
