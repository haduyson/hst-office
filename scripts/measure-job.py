"""Run a command and report wall time, CPU time, peak RSS and disk usage.

Usage: python3 scripts/measure-job.py [--min-free-gib 10] [--json out.json] -- <command...>
Refuses to start when free disk space is below --min-free-gib (brief §8: keep
>= 10 GiB free) instead of pruning anything.
"""
import argparse
import json
import resource
import shutil
import subprocess
import sys
import time


def free_gib(path="."):
    return shutil.disk_usage(path).free / 2**30


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-free-gib", type=float, default=10.0)
    parser.add_argument("--json", help="write measurements to this file")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing command after --")

    before = free_gib()
    if before < args.min_free_gib:
        print(f"refusing to run: {before:.1f} GiB free < {args.min_free_gib} GiB", file=sys.stderr)
        return 3
    start = time.monotonic()
    code = subprocess.call(command)
    elapsed = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "command": command,
        "exitCode": code,
        "elapsedSeconds": round(elapsed, 2),
        "cpuSeconds": round(usage.ru_utime + usage.ru_stime, 2),
        "peakRssMiB": round(usage.ru_maxrss / 1024, 1),  # Linux reports KiB
        "freeGiBBefore": round(before, 2),
        "freeGiBAfter": round(free_gib(), 2),
    }
    print("measure-job: " + json.dumps(result), file=sys.stderr)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    return code


if __name__ == "__main__":
    sys.exit(main())
