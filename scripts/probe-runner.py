#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Record actual Linux resources; block before an infeasible source download/build."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GIB = 2**30


def command_output(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        return {"exit_code": result.returncode, "output": (result.stdout + result.stderr).strip()[:2000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "UNVERIFIED", "reason": str(error)}


def thresholds(config, requested_free):
    text = config.read_text(encoding="utf-8")
    limits = {"min_free_gib": 40.0, "min_ram_gib": 16.0, "reserve_gib": 10.0, "min_cpu": 1.0}
    declared = {}
    # Comment metadata preserves the coordinator's one-configure-option-per-line format.
    for key, value in re.findall(r"^\s*#\s*(min_free_gib|min_ram_gib|reserve_gib|min_cpu)\s*=\s*(\S+)\s*$", text, re.M):
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"invalid resource threshold: {key}")
        declared[key] = number
        limits[key] = max(limits[key], number)
    parallelism = re.search(r"^--with-parallelism=(\d+)\s*$", text, re.M)
    if parallelism:
        limits["min_cpu"] = max(limits["min_cpu"], int(parallelism[1]))
    limits["min_free_gib"] = max(limits["min_free_gib"], requested_free, limits["reserve_gib"])
    return limits, declared


def memory_bytes():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable"):
            values[key] = int(value.strip().split()[0]) * 1024
    # Account for an optional cgroup v2 cap instead of reporting host memory as usable.
    cap = Path("/sys/fs/cgroup/memory.max")
    if cap.exists() and cap.read_text().strip().isdigit():
        maximum = int(cap.read_text())
        used = int(Path("/sys/fs/cgroup/memory.current").read_text())
        values["MemTotal"] = min(values["MemTotal"], maximum)
        values["MemAvailable"] = min(values["MemAvailable"], max(0, maximum - used))
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "build-config/linux-x86_64.conf")
    parser.add_argument("--path", type=Path, default=ROOT)
    parser.add_argument("--min-free-gib", type=float, default=40, help="may raise, never lower the 40 GiB floor")
    parser.add_argument("--output", type=Path, default=ROOT / "build/metrics/runner-probe.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.min_free_gib) or args.min_free_gib <= 0:
        parser.error("--min-free-gib must be positive and finite")
    evidence = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
                "machine": platform.machine(), "cpu_count": os.cpu_count(), "path": str(args.path.resolve()),
                "config": str(args.config), "commit": command_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
                "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "quota_billing": "UNVERIFIED: account quota and billing require owner verification",
                "full_build": "UNVERIFIED: a resource probe is not build/package/runtime QA"}
    blockers = []
    try:
        if platform.system() != "Linux":
            raise ValueError("Linux runner required")
        limits, declared = thresholds(args.config, args.min_free_gib)
        memory = memory_bytes()
        disk = shutil.disk_usage(args.path)
        cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
        evidence.update({"thresholds": limits, "declared_thresholds": declared,
                         "threshold_basis": "config metadata plus conservative 40 GiB/16 GiB/10 GiB floors; peak build UNVERIFIED",
                         "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
                         "cpu_available": cpus, "ram_total_bytes": memory["MemTotal"],
                         "ram_available_bytes": memory["MemAvailable"], "disk_total_bytes": disk.total,
                         "disk_free_bytes": disk.free, "filesystem": command_output(["df", "-PT", str(args.path)])})
        for label, actual, required in (("free disk GiB", disk.free / GIB, limits["min_free_gib"]),
                                        ("available RAM GiB", memory["MemAvailable"] / GIB, limits["min_ram_gib"]),
                                        ("available CPUs", cpus, limits["min_cpu"])):
            if actual < required:
                blockers.append(f"{label}: {actual:.2f} < required {required:g}")
        evidence["tools"] = {name: command_output([name, "--version"]) for name in ("python3", "git", "gcc", "make")}
    except (OSError, ValueError, KeyError) as error:
        blockers.append(str(error))
    evidence.update({"status": "BLOCKED" if blockers else "PREFLIGHT_PASS", "blockers": blockers})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    if blockers:
        print("BLOCKED (OPS-01): " + "; ".join(blockers), file=sys.stderr)
        return 1
    print("PREFLIGHT_PASS: resource floors met; cold build, packaging and platform QA remain UNVERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
