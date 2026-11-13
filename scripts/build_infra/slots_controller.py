# SPDX-License-Identifier: AGPL-3.0-only
"""Admission state of the Linux build slots ($HST_BUILD_ROOT/locks/slots.json under an flock).
"""
import contextlib
import fcntl
import json
import os
import sys
import time

from .slots_host import (disk_free_gib, mem_available_gib, pid_alive, scope_memory_gib, slot_dirs, slot_locked,
                         swap_used_gib)
from .slots_model import ROOT, Config, budget_gib, waterfill

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
