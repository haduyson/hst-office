#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Collect macOS build metrics: phase timings, compile progress, disk, memory, log tails.

Usage: python -I scripts/macos/summarize-build.py --work ~/hst --out ~/hst/artifacts --arch arm64
Writes metrics.json, build-tail.log, copies of the phase logs and a markdown summary (stdout).
Never fails because a phase did not run; missing inputs are reported as null.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

STEP = re.compile(r"^\[build (\w+)\]\s+(\S+)")
LOGS = ("tools.log", "extract.log", "patch.log", "configure.log", "fetch.log", "showmodules.log",
        "ccache-stats.txt", "runner-probe.txt", "free-disk.txt")


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
    parser.add_argument("--arch", required=True)
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
    errors = [line for line in log if re.search(r"\b(error|Error \d+)\b", line)][-200:]
    (args.out / "build-errors.log").write_text("\n".join(errors) + "\n", encoding="utf-8")
    config_log = work / "lo" / "config.log"
    if config_log.is_file():
        shutil.copyfile(config_log, args.out / "config.log")
    for name in LOGS:
        source = work / "logs" / name
        if source.is_file():
            shutil.copyfile(source, args.out / name)
    installation = work / "lo" / "workdir" / "installation"
    for logfile in installation.glob("*/dmg/logging/**/*.log") if installation.is_dir() else []:
        shutil.copyfile(logfile, args.out / f"installer-{logfile.parent.name}-{logfile.name}")
    free = [s["free_gib"] for s in samples if s.get("free_gib") is not None]
    build = next((row for row in phases if row.get("phase") == "build"), None)
    metrics = {
        "arch": args.arch,
        "phases": phases,
        "build_steps_by_kind": kinds,
        "build_steps_total": sum(kinds.values()),
        "modules_touched": len(modules),
        "last_target": last_target,
        "build_seconds": build.get("seconds") if build else None,
        "progress_samples": len(samples),
        "min_free_gib": min(free) if free else None,
        "max_mem_used_gib": max((s.get("mem_used_gib", 0) for s in samples), default=None),
        "max_swap_used_gib": max((s.get("swap_used_gib", 0) for s in samples), default=None),
        "dmg_found": sorted(str(p) for p in (work / "dmg").glob("*.dmg")) if (work / "dmg").is_dir() else [],
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (args.out / "progress.jsonl").write_text("\n".join(json.dumps(s) for s in samples) + "\n", encoding="utf-8")
    print(f"### macOS {args.arch} build metrics")
    print("| phase | seconds | status | free GiB |\n|---|---|---|---|")
    for row in phases:
        print(f"| {row.get('phase')} | {row.get('seconds')} | {row.get('status')} | {row.get('free_gib')} |")
    print(f"\n- build steps: {metrics['build_steps_total']} {kinds}")
    print(f"- last target: `{last_target}`; modules touched: {len(modules)}")
    print(f"- min free disk (GiB): {metrics['min_free_gib']}; peak memory used (GiB): {metrics['max_mem_used_gib']}; "
          f"peak swap (GiB): {metrics['max_swap_used_gib']}")
    print(f"- dmg: {metrics['dmg_found'] or 'none'}")


if __name__ == "__main__":
    main()
