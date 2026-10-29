"""Run a heavy job under resource guard and record its footprint.

Usage:
  python3 scripts/measure-job.py [--min-free-gib 10] [--stop-free-gib 12] [--warn-free-gib 15]
                                 [--json out.json] [--interval 5] -- <command...>

- refuses to start below --min-free-gib (brief §8 keeps >= 10 GiB free);
- samples free disk, process-tree RSS and CPU every --interval seconds;
- terminates the job's own process group (SIGTERM, then SIGKILL) when free
  space drops below --stop-free-gib, so the 10 GiB floor is never crossed;
- never deletes anything.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

PAGE = os.sysconf("SC_PAGE_SIZE")
TICKS = os.sysconf("SC_CLK_TCK")


def free_gib(path):
    return shutil.disk_usage(path).free / 2**30


def process_group_stats(pgid):
    """Sum RSS (MiB) and CPU seconds of live processes in a process group."""
    rss, cpu, count = 0, 0.0, 0
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
            if int(fields[2]) != pgid:  # field 5 (pgrp) after the comm field
                continue
            cpu += (int(fields[11]) + int(fields[12])) / TICKS
            rss += int(fields[21]) * PAGE
            count += 1
        except (OSError, IndexError, ValueError):
            continue
    return rss / 2**20, cpu, count


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-free-gib", type=float, default=10.0)
    parser.add_argument("--stop-free-gib", type=float, default=12.0)
    parser.add_argument("--warn-free-gib", type=float, default=15.0)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--path", default="/home/office", help="filesystem to watch")
    parser.add_argument("--json", help="write measurements here")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing command after --")

    start_free = free_gib(args.path)
    if start_free < args.min_free_gib:
        print(f"measure-job: refusing to start, {start_free:.1f} GiB free < {args.min_free_gib}", file=sys.stderr)
        return 3
    started = time.monotonic()
    child = subprocess.Popen(command, start_new_session=True)
    state = {"minFree": start_free, "peakRssMiB": 0.0, "peakProcs": 0, "cpuSeconds": 0.0,
             "warned": False, "stoppedForDisk": False}

    def sample():
        while child.poll() is None:
            free = free_gib(args.path)
            rss, cpu, procs = process_group_stats(child.pid)
            state["minFree"] = min(state["minFree"], free)
            state["peakRssMiB"] = max(state["peakRssMiB"], rss)
            state["peakProcs"] = max(state["peakProcs"], procs)
            state["cpuSeconds"] = max(state["cpuSeconds"], cpu)
            if free < args.warn_free_gib and not state["warned"]:
                state["warned"] = True
                print(f"measure-job: WARNING {free:.1f} GiB free", file=sys.stderr)
            if free < args.stop_free_gib and not state["stoppedForDisk"]:
                state["stoppedForDisk"] = True
                print(f"measure-job: STOP {free:.1f} GiB free < {args.stop_free_gib}; terminating job", file=sys.stderr)
                os.killpg(child.pid, signal.SIGTERM)
                threading.Timer(30, lambda: child.poll() is None and os.killpg(child.pid, signal.SIGKILL)).start()
            time.sleep(args.interval)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        code = child.wait()
    except KeyboardInterrupt:
        os.killpg(child.pid, signal.SIGTERM)
        code = child.wait()
    sampler.join(timeout=args.interval + 1)
    result = {
        "command": command, "exitCode": code, "elapsedSeconds": round(time.monotonic() - started, 1),
        "cpuSecondsObservedMax": round(state["cpuSeconds"], 1), "peakProcessGroupRssMiB": round(state["peakRssMiB"], 1),
        "peakProcesses": state["peakProcs"], "freeGiBStart": round(start_free, 2),
        "freeGiBMin": round(state["minFree"], 2), "freeGiBEnd": round(free_gib(args.path), 2),
        "stoppedForDisk": state["stoppedForDisk"],
    }
    print("measure-job: " + json.dumps(result), file=sys.stderr)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    return 4 if state["stoppedForDisk"] else code


if __name__ == "__main__":
    sys.exit(main())
