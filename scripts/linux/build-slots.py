#!/usr/bin/env python3
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
import contextlib
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.environ.get("HST_BUILD_ROOT", "/data/hst-build")
GIB = 1024 ** 3


def env_int(name, default):
    value = os.environ.get(name, "")
    if not value:
        return default
    if not value.isdigit():
        raise SystemExit(f"build-slots: {name} must be a non-negative integer, got {value!r}")
    return int(value)


class Config:
    def __init__(self):
        self.total_jobs = env_int("HST_TOTAL_JOBS", 28)
        self.max_jobs = env_int("HST_MAX_JOBS", 20)
        self.min_jobs = env_int("HST_MIN_JOBS", 4)
        self.headroom_gib = env_int("HST_HEADROOM_GIB", 8)
        self.min_free_gib = env_int("HST_MIN_FREE_GIB", 15)
        self.min_mem_gib = env_int("HST_MIN_MEM_GIB", 6)
        self.swap_grow_gib = env_int("HST_SWAP_GROW_GIB", 1)


def budget_gib(jobs):
    """Scope MemoryMax for a make with this many jobs (clang ~0.4 GiB/job + one heavy link)."""
    return round(min(12.0, max(6.0, 4.0 + 0.4 * jobs)), 1)


def waterfill(wants, total, max_jobs, min_jobs):
    """Share `total` jobs among slots (dict slot -> wanted jobs, in admission order).

    Each slot gets at most min(want, max_jobs); when the caps exceed `total`, the smallest requests are
    satisfied first and the rest share equally (earlier admissions get the remainder). Never below min_jobs."""
    caps = {s: max(min_jobs, min(w, max_jobs)) for s, w in wants.items()}
    alloc = {}
    remaining = dict(caps)
    budget = total
    while remaining:
        share = budget // len(remaining)
        small = {s: c for s, c in remaining.items() if c <= share}
        if not small:
            order = list(remaining)
            extra = budget - share * len(order)
            for i, s in enumerate(order):
                alloc[s] = share + (1 if i < extra else 0)
            break
        for s, c in small.items():
            alloc[s] = c
            budget -= c
            del remaining[s]
    return {s: max(min_jobs, alloc[s]) for s in wants}


# ---------------------------------------------------------------- host probes (patched in tests)
def meminfo():
    values = {}
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            key, rest = line.split(":", 1)
            values[key] = int(rest.split()[0]) * 1024
    return values


def mem_available_gib():
    return meminfo()["MemAvailable"] / GIB


def swap_used_gib():
    m = meminfo()
    return (m["SwapTotal"] - m["SwapFree"]) / GIB


def scope_memory_gib(scope):
    if not scope:
        return 0.0
    path = f"/sys/fs/cgroup/system.slice/{scope}.scope/memory.current"
    try:
        with open(path, encoding="ascii") as f:
            return int(f.read().strip()) / GIB
    except (OSError, ValueError):
        return 0.0


def disk_free_gib(path):
    return shutil.disk_usage(path).free / GIB


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def slot_dirs(root):
    base = os.path.join(root, "slots")
    try:
        names = os.listdir(base)
    except FileNotFoundError:
        return []
    return sorted(int(n) for n in names if n.isdigit() and os.path.isdir(os.path.join(base, n, "src")))


def slot_locked(root, slot):
    """True when a local-build.sh run holds the slot's lock (also catches runs not registered here yet)."""
    path = os.path.join(root, "slots", str(slot), ".lock")
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def agents_top(root, agents_dir="/data/hst-agents", count=5, max_age=600, du=None):
    """The largest agent directories ("name size" strings), cached in locks/agents-usage.json for max_age seconds:
    a disk refusal names who is filling /data (agents read /data/hst-office-build/src/lo instead of copying trees)."""
    cache = os.path.join(root, "locks", "agents-usage.json")
    try:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data["time"] < max_age:
            return data["top"]
    except (OSError, ValueError, KeyError):
        pass
    if du is None:
        try:
            done = subprocess.run(["du", "-sk", "--max-depth=1", agents_dir], capture_output=True, text=True,
                                  timeout=300, check=False)
            du = done.stdout
        except subprocess.TimeoutExpired:
            return []
    sizes = []
    for line in du.splitlines():
        kib, _, path = line.partition("\t")
        if kib.isdigit() and path.rstrip("/") != agents_dir.rstrip("/"):
            sizes.append((int(kib), os.path.basename(path)))
    top = [f"{name} {kib / 1048576:.1f}G" for kib, name in sorted(sizes, reverse=True)[:count]]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"time": time.time(), "top": top}, f)
    return top


def explain(root, reason):
    """Add the largest /data/hst-agents consumers to a disk refusal."""
    if not reason.startswith("disk"):
        return reason
    top = agents_top(root)
    return reason + ("; largest in /data/hst-agents: " + ", ".join(top) if top else "")


# ---------------------------------------------------------------- state
class Controller:
    def __init__(self, root=ROOT, config=None, probes=None):
        self.root = root
        self.config = config or Config()
        self.locks = os.path.join(root, "locks")
        self.state_path = os.path.join(self.locks, "slots.json")
        p = probes or {}
        self.mem_available_gib = p.get("mem_available_gib", mem_available_gib)
        self.swap_used_gib = p.get("swap_used_gib", swap_used_gib)
        self.scope_memory_gib = p.get("scope_memory_gib", scope_memory_gib)
        self.disk_free_gib = p.get("disk_free_gib", lambda: disk_free_gib(root))
        self.pid_alive = p.get("pid_alive", pid_alive)
        self.now = p.get("now", time.time)

    @contextlib.contextmanager
    def locked(self):
        os.makedirs(self.locks, exist_ok=True)
        with open(os.path.join(self.locks, "admission.lock"), "a+", encoding="ascii") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self._load()
            self._prune(state)
            yield state
            self._save(state)

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
        except FileNotFoundError:
            state = {}
        except (OSError, ValueError) as exc:
            print(f"build-slots: unreadable {self.state_path} ({exc}); starting empty", file=sys.stderr)
            state = {}
        state.setdefault("slots", {})
        state.setdefault("swap_base_gib", self.swap_used_gib())
        return state

    def _save(self, state):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, sort_keys=True)
        os.replace(tmp, self.state_path)

    def _prune(self, state):
        for slot, entry in list(state["slots"].items()):
            if not self.pid_alive(entry["pid"]):
                del state["slots"][slot]

    def _ordered(self, state):
        return dict(sorted(state["slots"].items(), key=lambda kv: kv[1]["admitted"]))

    def allocations(self, state, extra=None):
        wants = {s: e["want"] for s, e in self._ordered(state).items()}
        if extra:
            wants[extra[0]] = extra[1]
        c = self.config
        return waterfill(wants, c.total_jobs, c.max_jobs, c.min_jobs) if wants else {}

    def unused_reservation_gib(self, state):
        return sum(max(0.0, e["budget_gib"] - self.scope_memory_gib(e.get("scope", "")))
                   for e in state["slots"].values() if not e.get("frozen"))

    def check_admit(self, state, slot, want):
        """(jobs, budget, None) when `slot` may start now, else (None, None, reason)."""
        c = self.config
        if str(slot) in state["slots"]:
            return None, None, f"slot {slot} already registered"
        if (len(state["slots"]) + 1) * c.min_jobs > c.total_jobs:
            return None, None, "job limit reached"
        jobs = self.allocations(state, (str(slot), want))[str(slot)]
        budget = budget_gib(jobs)
        avail = self.mem_available_gib() - self.unused_reservation_gib(state)
        if avail < budget + c.headroom_gib:
            return None, None, (f"memory: {avail:.1f} GiB effectively available, need {budget} + "
                                f"{c.headroom_gib} GiB headroom for -j{jobs}")
        free = self.disk_free_gib()
        if free < c.min_free_gib + 2:
            return None, None, f"disk: {free:.1f} GiB free, need {c.min_free_gib + 2}"
        return jobs, budget, None

    def try_acquire(self, slot, pid, want, kind="full"):
        with self.locked() as state:
            jobs, budget, reason = self.check_admit(state, slot, want)
            if reason:
                return None, reason
            state["slots"][str(slot)] = {"pid": pid, "want": want, "jobs": jobs, "budget_gib": budget,
                                         "kind": kind, "admitted": self.now(), "frozen": False, "scope": ""}
            state["swap_base_gib"] = self.swap_used_gib()
            return (jobs, budget), None

    def poll(self, slot, current_jobs):
        """Decision for a running slot: ("ok", alloc) or ("freeze", reason)."""
        c = self.config
        with self.locked() as state:
            entry = state["slots"].get(str(slot))
            if entry is None:
                return "ok", current_jobs
            entry["jobs"] = current_jobs
            mem = self.mem_available_gib()
            swap_grow = self.swap_used_gib() - state["swap_base_gib"]
            reason = None
            if mem < c.min_mem_gib:
                reason = f"MemAvailable {mem:.1f} GiB below {c.min_mem_gib} GiB"
            elif swap_grow > c.swap_grow_gib:
                reason = f"swap use grew by {swap_grow:.1f} GiB (more than {c.swap_grow_gib} GiB)"
            if reason:
                running = [s for s, e in self._ordered(state).items() if not e.get("frozen")]
                if running and running[-1] == str(slot):
                    entry["frozen"] = True
                    return "freeze", reason
            return "ok", self.allocations(state)[str(slot)]

    def update(self, slot, jobs=None, want=None, scope=None, frozen=None):
        with self.locked() as state:
            entry = state["slots"].get(str(slot))
            if entry is None:
                return False
            if jobs is not None:
                entry["jobs"] = jobs
                entry["budget_gib"] = budget_gib(jobs)
            if want is not None:
                entry["want"] = want
            if scope is not None:
                entry["scope"] = scope
            if frozen is not None:
                entry["frozen"] = frozen
                if not frozen:
                    state["swap_base_gib"] = self.swap_used_gib()
            return True

    def release(self, slot):
        with self.locked() as state:
            state["slots"].pop(str(slot), None)
            state["swap_base_gib"] = self.swap_used_gib()

    def free_slot(self, want, exclude=()):
        """A slot number that is idle and admissible now, or (None, reason)."""
        with self.locked() as state:
            busy = set(state["slots"]) | {str(s) for s in exclude}
            for slot in slot_dirs(self.root):
                if str(slot) in busy or slot_locked(self.root, slot):
                    continue
                _, _, reason = self.check_admit(state, slot, want)
                return (slot, None) if reason is None else (None, reason)
            return None, "no idle slot"

    def status(self):
        with self.locked() as state:
            return {"slots": self._ordered(state), "allocations": self.allocations(state),
                    "mem_available_gib": round(self.mem_available_gib(), 1),
                    "unused_reservation_gib": round(self.unused_reservation_gib(state), 1),
                    "swap_used_gib": round(self.swap_used_gib(), 1), "disk_free_gib": round(self.disk_free_gib(), 1),
                    "configured_slots": slot_dirs(self.root)}


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
        last = ""
        while True:
            granted, reason = ctl.try_acquire(args.slot, args.pid, want, args.kind)
            if granted:
                print(f"{granted[0]} {granted[1]}")
                return 0
            if reason != last:
                print(f"[{time.strftime('%F %T')}] admission: slot {args.slot} waiting: {explain(ctl.root, reason)}",
                      file=sys.stderr)
                last = reason
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


if __name__ == "__main__":
    sys.exit(main())
