# SPDX-License-Identifier: AGPL-3.0-only
"""Markdown table of scripts/perf/large-file-open.py results: python large-file-open-summary.py <out-dir>.

One row per file, one column per label: "load / ready s, peak MB" (median over runs), "TIMEOUT@s" when the open did
not finish, "CRASH" when the office ended with an error code, "ERR" with the error text below the table.
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
            ok = [r for r in runs if "error" not in r and "office_exit" not in r]
            crashed = [r for r in runs if "office_exit" in r]
            if crashed:
                r = crashed[-1]
                cell = "CRASH 0x%X at %s s, %d MB" % (r["office_exit"] & 0xFFFFFFFF, r.get("after"), r["peak_mb"])
            elif ok:
                med = lambda k: statistics.median(r[k] for r in ok if k in r) if any(k in r for r in ok) else None  # noqa: E731
                cell = "%s / %s s, %d MB" % (med("load"), med("idle"), max(r["peak_mb"] for r in ok))
                if med("layout") is not None:
                    cell += ", laid out %s s (%d pages)" % (med("layout"), max(r.get("pages", 0) for r in ok))
                if med("save") is not None:
                    cell += ", save %s s" % med("save")
                if med("save_odf") is not None:
                    cell += ", ODF copy %s s" % med("save_odf")
                if any(r.get("modified") for r in ok):
                    cell += ", modified"
            elif runs:
                r = runs[-1]
                cell = "TIMEOUT@%s s (load %s), %d MB" % (r.get("after"), r.get("load", "-"), r["peak_mb"]) \
                    if r["error"] == "timeout" else "ERR"
            else:
                cell = ""
            for r in runs:
                if "error" in r and r["error"] != "timeout" and "office_exit" not in r:
                    errors.append("%s %s: %s" % (label, fname, r["error"]))
            cells.append(cell)
        print("| %s | %s | %s |" % (fname, size, " | ".join(cells)))
    print("\nload / ready s = loadComponentFromURL returned / office idle after it (visible window); laid out = whole"
          " text document laid out (page count known); median of runs.")
    for e in errors:
        print("- " + e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
