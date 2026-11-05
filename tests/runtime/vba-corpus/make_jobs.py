# SPDX-License-Identifier: AGPL-3.0-only
"""Turn a static scan into sandbox jobs. Usage: make_jobs.py SCAN.jsonl INDEX.json OUT.json [--benign-repo R]... [--limit N]"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macro_policy  # noqa: E402

EXCEL = (".xls", ".xla", ".xlt", ".xlsm", ".xltm", ".xlam", ".xlsb")
WORD = (".doc", ".dot", ".docm", ".dotm")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan")
    parser.add_argument("index")
    parser.add_argument("out")
    parser.add_argument("--benign-repo", action="append", default=[])
    parser.add_argument("--max-procs", type=int, default=40)
    args = parser.parse_args()
    with open(args.index, encoding="utf-8") as handle:
        index = {}
        for entry in json.load(handle):
            if "name" in entry:
                index.setdefault(entry["name"], entry)
    jobs, policy = [], {}
    with open(args.scan, encoding="utf-8") as handle:
        for line in handle:
            scan = json.loads(line)
            if not scan.get("has_macros"):
                continue
            name = scan["name"]
            entry = index.get(name, {})
            ext = os.path.splitext(name)[1].lower()
            kind = "calc" if ext in EXCEL else "writer" if ext in WORD else None
            verdict = macro_policy.decide(scan, entry.get("repo") in args.benign_repo)
            policy[name] = dict(verdict, kind=kind, app=scan.get("app"), repo=entry.get("repo"), path=entry.get("path"), licence=entry.get("licence"))
            if kind and verdict["run"]:
                jobs.append(dict(file=name, path=entry.get("path"), kind=kind, skip=verdict["skip"], max_procs=args.max_procs, recalc=kind == "calc"))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, ensure_ascii=False)
    with open(args.out + ".policy.json", "w", encoding="utf-8") as handle:
        json.dump(policy, handle, indent=0, ensure_ascii=False)
    print(f"{len(policy)} macro files, {len(jobs)} may run, {sum(not v['run'] for v in policy.values())} blocked, "
          f"{sum(bool(v['skip']) for v in policy.values())} with blocked procedures")


if __name__ == "__main__":
    main()
