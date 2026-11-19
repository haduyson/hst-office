#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Checks the ribbon layout dumps written by the real app against the v3 rules (ribbon_v3_rules.py).

Usage: python3 tests/runtime/check-ribbon-v3-dumps.py --dumps DIR [--json OUT]
Reads every *.json dump under DIR (recursively), groups them by app and logical window width (window.w / scale) and
prints the violations per rule (0 = pass) with the banner min/median/max. Exit 1 on any violation, 2 when DIR has no dump.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ribbon_v3_rules import RULES, dump_width, summarize  # noqa: E402


def load_dumps(root):
    """(dumps, skipped paths): a JSON file is a dump when it has a "groups" list; other JSON files are listed as skipped."""
    dumps, skipped = [], []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and "groups" in data:
            dumps.append(data)
        else:
            skipped.append(path)
    return dumps, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dumps", required=True, help="directory with the layout dumps")
    parser.add_argument("--json", help="also write the per-group summaries here")
    args = parser.parse_args()
    dumps, skipped = load_dumps(args.dumps)
    if not dumps:
        print(f"no layout dump under {args.dumps}", file=sys.stderr)
        return 2
    by_group = {}
    for dump in dumps:
        by_group.setdefault((dump["app"], dump_width(dump)), []).append(dump)
    head = f"{'app':<8}{'width':>6}{'tabs':>5}  " + " ".join(f"{r:>13}" for r in RULES) + "  banner min/med/max"
    print(head)
    total, rows = 0, []
    for (app, width), group in sorted(by_group.items()):
        s = summarize(group)
        total += sum(s["rules"].values())
        banner = s["banner"]
        text = f"{banner['min']}/{banner['median']}/{banner['max']}" if banner else "-"
        print(f"{app:<8}{width:>6}{s['dumps']:>5}  " + " ".join(f"{s['rules'][r]:>13}" for r in RULES) + f"  {text}")
        rows.append({"app": app, "width": width, **s})
    for row in rows:
        if row["folded"] or row["more"]:
            print(f"  {row['app']} @{row['width']}: folded {row['folded']}; overflow {row['more']}")
    print(f"skipped {len(skipped)} JSON file(s) that are not layout dumps")
    print(f"{len(dumps)} dumps, {total} violations")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=1)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
