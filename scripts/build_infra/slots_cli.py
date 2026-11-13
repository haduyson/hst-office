# SPDX-License-Identifier: AGPL-3.0-only
"""Admission controller for the parallel local Linux build slots (scripts/linux/local-build.sh --slot N).

All slots share one server (32 cores, 47 GB RAM shared with other services), so every slot asks this
controller before it starts make, and polls it while make runs. State lives in
$HST_BUILD_ROOT/locks/slots.json and every read-modify-write holds an exclusive flock on
$HST_BUILD_ROOT/locks/admission.lock.

Rules (environment overrides in brackets):
  - a slot is admitted only if total jobs stay <= HST_TOTAL_JOBS (28) and
      MemAvailable - (reserved but not yet used memory of running slots) >= budget(jobs) + HST_HEADROOM_GIB (8)
    and /data keeps HST_MIN_FREE_GIB (15) GiB free;
  - jobs are shared by water-filling: each slot gets min(its request, HST_MAX_JOBS (20)), scaled down to a fair
    share of HST_TOTAL_JOBS when several slots run (never below HST_MIN_JOBS (4)); running slots are told to
    restart make with the new -j by `poll`;
  - budget(jobs) = clamp(4 + 0.4 * jobs, 6, 12) GiB is the slot's systemd scope MemoryMax;
  - global memory guard: when MemAvailable < HST_MIN_MEM_GIB (6) or swap use grew by more than
    HST_SWAP_GROW_GIB (1) since the last admission/thaw, only the most recently admitted running (not frozen)
    slot is told to freeze; the next one follows if pressure persists.

  build-slots.py acquire --slot N --pid PID [--want J] [--kind full|modules]   blocks until admitted; prints "JOBS BUDGET_GIB"
  build-slots.py poll --slot N --jobs CUR                                       prints "ok ALLOC" or "freeze REASON"
  build-slots.py update --slot N [--jobs J] [--want J] [--scope UNIT] [--frozen 0|1]
  build-slots.py release --slot N
  build-slots.py free-slot [--want J] [--exclude 1,2]  prints a free, admissible slot number (exit 1 if none)
  build-slots.py budget --jobs J            prints the scope MemoryMax in MiB
  build-slots.py status [--json]

"""
import argparse
import json
import sys
import time

from .slots_controller import Controller
from .slots_host import explain
from .slots_model import budget_gib

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("--slot", type=int, required=True)
    a.add_argument("--pid", type=int, required=True)
    a.add_argument("--want", type=int, default=None)
    a.add_argument("--kind", choices=("full", "modules"), default="full")
    a.add_argument("--interval", type=int, default=15)
    p = sub.add_parser("poll")
    p.add_argument("--slot", type=int, required=True)
    p.add_argument("--jobs", type=int, required=True)
    u = sub.add_parser("update")
    u.add_argument("--slot", type=int, required=True)
    u.add_argument("--jobs", type=int)
    u.add_argument("--want", type=int)
    u.add_argument("--scope")
    u.add_argument("--frozen", type=int, choices=(0, 1))
    r = sub.add_parser("release")
    r.add_argument("--slot", type=int, required=True)
    f = sub.add_parser("free-slot")
    f.add_argument("--want", type=int, default=None)
    f.add_argument("--exclude", default="", help="comma-separated slots to skip (just started, not locked yet)")
    b = sub.add_parser("budget")
    b.add_argument("--jobs", type=int, required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "budget":
        print(int(budget_gib(args.jobs) * 1024))
        return 0
    ctl = Controller()
    want = getattr(args, "want", None)
    if want is None:
        want = ctl.config.max_jobs
    if want < 1:
        parser.error("--want must be positive")

    if args.cmd == "acquire":
        last, last_time = "", 0.0
        while True:
            granted, reason = ctl.try_acquire(args.slot, args.pid, want, args.kind)
            if granted:
                print(f"{granted[0]} {granted[1]}")
                return 0
            # One line per kind of reason (memory/disk/jobs), repeated every 5 min while it lasts.
            kind = reason.split(":", 1)[0]
            if kind != last or time.time() - last_time >= 300:
                print(f"[{time.strftime('%F %T')}] admission: slot {args.slot} waiting: {explain(ctl.root, reason)}",
                      file=sys.stderr)
                last, last_time = kind, time.time()
            time.sleep(args.interval)
    if args.cmd == "poll":
        action, value = ctl.poll(args.slot, args.jobs)
        print(f"{action} {value}")
        return 0
    if args.cmd == "update":
        frozen = None if args.frozen is None else bool(args.frozen)
        return 0 if ctl.update(args.slot, args.jobs, args.want, args.scope, frozen) else 1
    if args.cmd == "release":
        ctl.release(args.slot)
        return 0
    if args.cmd == "free-slot":
        exclude = [int(x) for x in args.exclude.split(",") if x.strip().isdigit()]
        slot, reason = ctl.free_slot(want, exclude)
        if slot is None:
            print(explain(ctl.root, reason), file=sys.stderr)
            return 1
        print(slot)
        return 0
    st = ctl.status()
    if args.json:
        print(json.dumps(st, indent=1, sort_keys=True))
    else:
        print(f"MemAvailable {st['mem_available_gib']} GiB (unused reservations {st['unused_reservation_gib']} GiB), "
              f"swap used {st['swap_used_gib']} GiB, /data free {st['disk_free_gib']} GiB, slots {st['configured_slots']}")
        for slot, e in st["slots"].items():
            print(f"  slot {slot}: pid {e['pid']} {e['kind']} -j{e['jobs']} (alloc {st['allocations'][slot]}, want "
                  f"{e['want']}) budget {e['budget_gib']} GiB{' FROZEN' if e.get('frozen') else ''} scope {e.get('scope') or '-'}")
    return 0

