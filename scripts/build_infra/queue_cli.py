# SPDX-License-Identifier: AGPL-3.0-only
"""HST Office local build queue: agents submit builds themselves, a dispatcher runs them on the build slots.

  build-queue.sh submit --platform linux|windows --ref <branch|sha> [--priority N] [--no-package] [--modules a,b]
                        [--test "CppunitTest_sc_ucalc ..."]   (Linux) build, then run the test targets
                        [--integrator] [--force]
                                                  prints the job id (an existing identical job's id when deduplicated);
                                                  priority > 50 only for the integrator; a commit that only changes
                                                  tests/ docs/ plans/ *.md since the branch's last build is refused
                                                  (--force: integrator); a newer commit cancels the branch's queued job
  build-queue.sh pin <id> --reason TEXT | unpin <id>   keep a done job's output out of retention (or release it)
  build-queue.sh disk-report [--host H] [--refresh]   Windows hosts: free space and the largest D:\\hst-test folders
                                                  (size, newest file, owner from the folder's .hst-owner file)
  build-queue.sh retention [--dry-run]            apply output retention now; prints what is deleted and the space freed
  build-queue.sh train add|remove|status|wait|start ...   build train (scripts/build_infra/queue_train_cli.py)
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
on disk is returned instead of a new one. Retention (queue_rules.retention_victims): the newest
`retention_per_branch` outputs per platform + branch + kind are kept, failed/cancelled/invalidated outputs and builds
of commits merged into the integration branch go after a grace period; job records stay, marked output_deleted.

"""
import argparse
import json
import os
import sys

from .queue_ops import cancel, drain, invalidate, submit
from .queue_report import compare, describe, print_tests, wait
from .queue_retention import apply_retention, pin
from . import queue_train_cli
from .queue_rules import order_key, parse_modules, parse_tests
from .queue_store import ACTIVE, PLATFORMS, TERMINAL, QueueError, Store

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
    s.add_argument("--integrator", action="store_true", help="the integrator's submit (priority above 50, --force)")
    s.add_argument("--force", action="store_true", help="integrator: build even a tests/docs-only commit")
    pn = sub.add_parser("pin")
    pn.add_argument("id")
    pn.add_argument("--reason", required=True)
    up = sub.add_parser("unpin")
    up.add_argument("id")
    dk = sub.add_parser("disk-report")
    dk.add_argument("--host")
    dk.add_argument("--refresh", action="store_true", help="ask the host(s) now instead of the last saved report")
    rt = sub.add_parser("retention")
    rt.add_argument("--dry-run", action="store_true")
    queue_train_cli.add_parser(sub)
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
                              parse_modules(args.modules), tests=parse_tests(args.test), force=args.force,
                              integrator=args.integrator)
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
                for k in ("submitted_at", "started_at", "finished_at", "host", "error", "pinned", "train",
                          "output_deleted_reason"):
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
                for line in disk_warnings(store):
                    print(line, file=sys.stderr)
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
        if args.cmd in ("pin", "unpin"):
            job = pin(store, args.id, args.reason if args.cmd == "pin" else None)
            print(f"{job['id']}: {'pinned: ' + job['pinned'] if job.get('pinned') else 'unpinned'}")
            return 0
        if args.cmd == "disk-report":
            return disk_report(store, args.host, args.refresh)
        if args.cmd == "retention":
            freed = apply_retention(store, dry_run=args.dry_run)
            for job_id, reason, size in freed:
                print(f"{job_id}  {size / 2**30:6.2f} GiB  {reason}")
            verb = "would free" if args.dry_run else "freed"
            print(f"{len(freed)} outputs, {verb} {sum(f[2] for f in freed) / 2**30:.2f} GiB")
            return 0
        if args.cmd == "train":
            return queue_train_cli.run(store, args)
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


def disk_warnings(store, max_age=7200):
    """Low-disk warnings of Windows hosts from their last report (shown above `list`)."""
    import time
    cfg = store.config()
    try:
        with open(os.path.join(store.root, "windows-disk.json"), encoding="utf-8") as f:
            reports = json.load(f)
    except (FileNotFoundError, ValueError):
        return []
    return [f"WARNING {h}: D: {r['d_free_gib']} GiB free (< {cfg['windows_warn_free_gib']}); "
            f"`build-queue.sh disk-report --host {h}`" for h, r in sorted(reports.items())
            if r.get("d_free_gib", 1e9) < cfg["windows_warn_free_gib"] and time.time() - r.get("fetched", 0) < max_age]


def disk_report(store, host=None, refresh=False, out=sys.stdout):
    cfg = store.config()
    hosts = sorted({s["host"] for s in cfg["windows_slots"]})
    if host and host not in hosts:
        raise QueueError(f"unknown Windows host {host!r}; known: {', '.join(hosts)}")
    reports = {}
    if refresh:
        from .dispatch_windows import WindowsRunner
        runner = WindowsRunner(store, cfg)
        for h in [host] if host else hosts:
            try:
                reports[h] = runner.disk_report(h)
            except (RuntimeError, OSError, ValueError) as exc:
                print(f"{h}: disk report failed: {exc}", file=out)
    else:
        try:
            with open(os.path.join(store.root, "windows-disk.json"), encoding="utf-8") as f:
                reports = {h: r for h, r in json.load(f).items() if not host or h == host}
        except (FileNotFoundError, ValueError):
            reports = {}
        if not reports:
            print("no saved report; use --refresh", file=out)
    for h, r in sorted(reports.items()):
        print(f"{h}: D: {r['d_free_gib']} GiB free, C: {r['c_free_gib']} GiB free (taken {r['taken']})", file=out)
        for d in r.get("folders", []):
            print(f"  {d['gib']:8.2f} GiB  {d['newest'][:16]}  {d.get('owner') or '-':<20} D:\\hst-test\\{d['name']}",
                  file=out)
    return 0

