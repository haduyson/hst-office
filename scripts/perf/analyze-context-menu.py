#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Summarise and compare context-menu latency runs (see context_menu_metrics.py)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_menu_metrics as m  # noqa: E402


def fmt(v):
    return "-" if v is None else f"{v:.1f}"


def print_summary(label: str, runs: dict) -> None:
    print(f"== {label}")
    print(f"{'cell':52} {'n':>4} {'to':>3} {'med':>8} {'p90':>8} {'p95':>8} {'max':>8}")
    for cell_id, doc in sorted(runs.items()):
        s = m.summarize_trials(doc["trials"])
        print(f"{cell_id:52} {s['n']:>4} {s['timeouts']:>3} {fmt(s['median_ms']):>8} "
              f"{fmt(s['p90_ms']):>8} {fmt(s['p95_ms']):>8} {fmt(s['max_ms']):>8}")


def print_samples(runs: dict) -> None:
    for cell_id, doc in sorted(runs.items()):
        sample = doc.get("sample_file")
        if not sample or not Path(sample).is_file():
            continue
        frames = m.parse_sample_top(Path(sample).read_text(encoding="utf-8", errors="replace"))
        print(f"-- sample {cell_id}: suspects={m.flag_suspects(frames) or 'none'}")
        for f in frames[:10]:
            print(f"   {f['samples']:>6}  {f['symbol']}  ({f['image']})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, help="run dir of the reference build (required to compare)")
    ap.add_argument("--candidate", type=Path, required=True, help="run dir under test")
    ap.add_argument("--warm-p95-ms", type=float, default=m.DEFAULT_TARGETS["warm_p95_ms"])
    ap.add_argument("--cold-p95-ms", type=float, default=m.DEFAULT_TARGETS["cold_p95_ms"])
    ap.add_argument("--regression-percent", type=float, default=10.0)
    ap.add_argument("--regression-floor-ms", type=float, default=20.0)
    ap.add_argument("--summary-only", action="store_true", help="no baseline; print statistics only")
    ap.add_argument("--json-out", type=Path, help="write comparison JSON here")
    args = ap.parse_args(argv)

    cand = m.load_runs(args.candidate)
    print_summary("candidate", cand)
    print_samples(cand)
    if args.summary_only:
        return 0
    if not args.baseline:
        print("ERROR: --baseline is required (missing baseline fails by design)", file=sys.stderr)
        return 2
    try:
        base = m.load_runs(args.baseline)
        result = m.compare_runs(base, cand, {"warm_p95_ms": args.warm_p95_ms,
                                             "cold_p95_ms": args.cold_p95_ms},
                                args.regression_percent, args.regression_floor_ms)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print_summary("baseline", base)
    for line in result["failures"]:
        print(f"FAIL {line}")
    print("PASS" if result["passed"] else "FAILED")
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
