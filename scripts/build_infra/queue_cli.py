# SPDX-License-Identifier: AGPL-3.0-only
"""HST Office local build queue: agents submit builds themselves, a dispatcher runs them on the build slots.

  build-queue.sh submit --platform linux|windows --ref <branch|sha> [--priority N] [--no-package] [--modules a,b]
                        [--test "CppunitTest_sc_ucalc ..."]   (Linux) build, then run the test targets
                                                  prints the job id (an existing identical job's id when deduplicated)
  build-queue.sh status <id> [--json]             state, slot/host, output, log
  build-queue.sh wait <id> [--timeout S]          blocks; prints the output path(s) (exit 0) or the log tail (exit 1);
                                                  test jobs: PASS/FAIL per target (exit 3 when a test failed)
  build-queue.sh invalidate <id> --reason TEXT    a done job whose output turned out bad: marked failed (files kept),
                                                  so dedupe builds it again on the next submit
  build-queue.sh compare <base-id> <id>           test results of two jobs side by side (e.g. baseline vs branch)
  build-queue.sh list [--all] [--json]            queued/running jobs and the recent finished ones
  build-queue.sh cancel <id>                      queued: dropped at once; running: stopped by the dispatcher
  build-queue.sh drain <host> [--no-wait|--hold|--cancel] Windows host: no new jobs there, wait until it is idle, deploy the
                                                  current tools to it, resume (prints when done)
  build-queue.sh dispatch [--once]                the dispatcher (systemd unit hst-build-queue.service)

State lives under HST_QUEUE_ROOT (default /data/hst-build-queue): jobs/<id>.json, logs/<id>.log, out/<id>/,
config.json (optional overrides of DEFAULT_CONFIG). Jobs run by priority (higher first), then FIFO.
Dedupe: a job with the same platform + commit + options that is queued, running, or done with its output still
on disk is returned instead of a new one. Retention: the newest `retention_per_branch` finished outputs per
platform and branch are kept; older outputs are deleted (their job records stay, marked output_deleted).

"""
import argparse
import json
import sys

from .queue_core import *  # noqa: F401,F403
from .queue_core import ACTIVE, PLATFORMS, TERMINAL, QueueError, Store

def main(argv=None):
    parser = argparse.ArgumentParser(prog="build-queue.sh", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--platform", required=True, choices=PLATFORMS)
    s.add_argument("--ref", required=True)
    s.add_argument("--priority", type=int, default=0)
    s.add_argument("--no-package", action="store_true")
    s.add_argument("--modules", default="")
    s.add_argument("--test", default="", help="Linux: test targets to run after the build (space/comma separated)")
    st = sub.add_parser("status")
    st.add_argument("id")
    st.add_argument("--json", action="store_true")
    w = sub.add_parser("wait")
    w.add_argument("id")
    w.add_argument("--timeout", type=int)
    li = sub.add_parser("list")
    li.add_argument("--all", action="store_true")
    li.add_argument("--json", action="store_true")
    c = sub.add_parser("cancel")
    c.add_argument("id")
    iv = sub.add_parser("invalidate")
    iv.add_argument("id")
    iv.add_argument("--reason", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("base")
    cp.add_argument("id")
    dr = sub.add_parser("drain")
    dr.add_argument("host")
    dr.add_argument("--no-wait", action="store_true")
    dr.add_argument("--timeout", type=int)
    dr.add_argument("--cancel", action="store_true", help="stop draining (or end a hold) and resume scheduling")
    dr.add_argument("--hold", action="store_true", help="stay idle after deploying (maintenance, reboot)")
    d = sub.add_parser("dispatch")
    d.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    store = Store()
    try:
        if args.cmd == "submit":
            job, dup = submit(store, args.platform, args.ref, args.priority, not args.no_package,
                              parse_modules(args.modules), tests=parse_tests(args.test))
            if dup:
                print(f"deduplicated: identical job {job['id']} is {job['state']}", file=sys.stderr)
            print(job["id"])
            return 0
        if args.cmd == "status":
            job = store.load(args.id)
            if args.json:
                print(json.dumps(job, indent=1, sort_keys=True))
            else:
                print(describe(job))
                for k in ("submitted_at", "started_at", "finished_at", "host", "error"):
                    if job.get(k):
                        print(f"  {k}: {job[k]}")
                for p in job.get("output", []):
                    print(f"  output: {p}{' (deleted by retention)' if job.get('output_deleted') else ''}")
                if job.get("tests") and job["state"] == "done":
                    print_tests(store, job, sys.stdout)
                print(f"  log: {job['log']}")
            return 0
        if args.cmd == "wait":
            return wait(store, args.id, args.timeout)
        if args.cmd == "list":
            jobs = sorted(store.all(), key=lambda j: j["submitted"])
            if not args.all:
                active = [j for j in jobs if j["state"] in ACTIVE]
                jobs = sorted(active, key=order_key) + [j for j in jobs if j["state"] in TERMINAL][-10:]
            if args.json:
                print(json.dumps(jobs, indent=1, sort_keys=True))
            else:
                for job in jobs:
                    print(describe(job))
            return 0
        if args.cmd == "cancel":
            job = cancel(store, args.id)
            print(f"{job['id']}: {'cancel requested' if job['state'] == 'running' else job['state']}")
            return 0
        if args.cmd == "invalidate":
            job = invalidate(store, args.id, args.reason)
            print(f"{job['id']}: {job['error']}")
            return 0
        if args.cmd == "compare":
            return compare(store, args.base, args.id)
        if args.cmd == "drain":
            return drain(store, args.host, not args.no_wait, timeout=args.timeout, cancel=args.cancel, hold=args.hold)
        if args.cmd == "dispatch":
            from .dispatch_loop import run
            return run(store, once=args.once)
    except QueueError as exc:
        print(f"build-queue: {exc}", file=sys.stderr)
        return 2
    return 0

