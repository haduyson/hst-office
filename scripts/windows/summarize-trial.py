#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Collect trial-build metrics: phase timings, compile progress, disk, log tails.

Usage: python -I scripts/windows/summarize-trial.py --work C:/hst --out C:/hst/artifacts
Writes metrics.json, build-tail.log, config.log copy and a markdown summary (stdout).
Never fails because a phase did not run; missing inputs are reported as null.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

STEP = re.compile(r"^\[build (\w+)\]\s+(\S+)")


def read_lines(path):
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def parse_jsonl(path):
    rows = []
    for line in read_lines(path):
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.work
    phases = parse_jsonl(work / "metrics" / "phases.jsonl")
    samples = parse_jsonl(work / "metrics" / "progress.jsonl")
    log = read_lines(work / "logs" / "build.log")
    kinds, last_target, modules = {}, None, set()
    for line in log:
        match = STEP.match(line)
        if match:
            kinds[match[1]] = kinds.get(match[1], 0) + 1
            last_target = match[2]
            modules.add(match[2].split("/")[0])
    (args.out / "build-tail.log").write_text("\n".join(log[-3000:]) + "\n", encoding="utf-8")
    config_log = work / "lo" / "config.log"
    if config_log.is_file():
        shutil.copyfile(config_log, args.out / "config.log")
    for name in ("configure.log", "extract.log", "cygwin-packages.txt"):
        source = work / "logs" / name
        if source.is_file():
            shutil.copyfile(source, args.out / name)
    free = [s.get("free_gib") for s in samples if s.get("free_gib") is not None]
    metrics = {
        "phases": phases,
        "build_steps_by_kind": kinds,
        "build_steps_total": sum(kinds.values()),
        "modules_touched": len(modules),
        "last_target": last_target,
        "progress_samples": len(samples),
        "min_free_gib": min(free) if free else None,
        "max_mem_used_gib": max((s.get("mem_used_gib", 0) for s in samples), default=None),
        "msi_found": [str(p) for p in (work / "lo" / "workdir").rglob("*.msi")] if (work / "lo" / "workdir").is_dir() else [],
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (args.out / "progress.jsonl").write_text("\n".join(json.dumps(s) for s in samples) + "\n", encoding="utf-8")
    print("### Windows trial metrics")
    print("| phase | seconds | status |\n|---|---|---|")
    for row in phases:
        print(f"| {row.get('phase')} | {row.get('seconds')} | {row.get('status')} |")
    print(f"\n- build steps: {metrics['build_steps_total']} {kinds}")
    print(f"- last target: `{last_target}`; modules touched: {len(modules)}")
    print(f"- min free disk (GiB): {metrics['min_free_gib']}; peak memory used (GiB): {metrics['max_mem_used_gib']}")
    print(f"- msi: {metrics['msi_found'] or 'none'}")


if __name__ == "__main__":
    main()
