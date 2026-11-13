# SPDX-License-Identifier: AGPL-3.0-only
"""Admission controller of the parallel local Linux build slots (scripts/linux/build-slots.py)."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location("build_slots_for_test", ROOT / "scripts/linux/build-slots.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bs = load()


class WaterfillTest(unittest.TestCase):
    def test_single_slot_gets_its_request_up_to_max(self):
        self.assertEqual(bs.waterfill({"1": 20}, 28, 20, 4), {"1": 20})
        self.assertEqual(bs.waterfill({"1": 40}, 28, 20, 4), {"1": 20})

    def test_two_slots_share_the_total(self):
        self.assertEqual(bs.waterfill({"1": 20, "2": 20}, 28, 20, 4), {"1": 14, "2": 14})

    def test_small_request_leaves_the_rest_to_others(self):
        self.assertEqual(bs.waterfill({"1": 20, "2": 6}, 28, 20, 4), {"1": 20, "2": 6})
        self.assertEqual(bs.waterfill({"1": 20, "2": 20, "3": 4}, 28, 20, 4), {"1": 12, "2": 12, "3": 4})

    def test_four_slots_never_exceed_total_and_keep_minimum(self):
        alloc = bs.waterfill({str(i): 20 for i in range(1, 5)}, 28, 20, 4)
        self.assertEqual(sum(alloc.values()), 28)
        self.assertTrue(all(v >= 4 for v in alloc.values()))

    def test_remainder_goes_to_earlier_admissions(self):
        self.assertEqual(bs.waterfill({"1": 20, "2": 20, "3": 20}, 28, 20, 4), {"1": 10, "2": 9, "3": 9})


class BudgetTest(unittest.TestCase):
    def test_budget_is_clamped(self):
        self.assertEqual(bs.budget_gib(20), 12.0)
        self.assertEqual(bs.budget_gib(1), 6.0)
        self.assertEqual(bs.budget_gib(10), 8.0)


class Probes:
    def __init__(self):
        self.mem = 40.0
        self.swap = 10.0
        self.disk = 80.0
        self.scope_mem = {}
        self.alive = set()
        self.t = 1000.0

    def as_dict(self):
        def now():
            self.t += 1
            return self.t
        return {"mem_available_gib": lambda: self.mem, "swap_used_gib": lambda: self.swap,
                "disk_free_gib": lambda: self.disk, "scope_memory_gib": lambda s: self.scope_mem.get(s, 0.0),
                "pid_alive": lambda p: p in self.alive, "now": now}


class ControllerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        for n in (1, 2, 3, 4):
            os.makedirs(os.path.join(self.root, "slots", str(n), "src"))
        self.p = Probes()
        self.ctl = bs.Controller(self.root, bs.Config(), self.p.as_dict())

    def acquire(self, slot, pid, want=20):
        self.p.alive.add(pid)
        return self.ctl.try_acquire(slot, pid, want)

    def test_first_slot_gets_twenty_jobs_and_twelve_gib(self):
        granted, reason = self.acquire(1, 101)
        self.assertIsNone(reason)
        self.assertEqual(granted, (20, 12.0))

    def test_memory_gate_counts_unused_reservations(self):
        self.p.mem = 30.0
        self.assertIsNotNone(self.acquire(1, 101)[0])
        # 30 - 12 reserved (nothing used yet) = 18 < 9.6 + 8 for -j14? 18 >= 17.6: admitted
        granted, reason = self.acquire(2, 102)
        self.assertIsNone(reason, reason)
        self.assertEqual(granted[0], 14)
        # Third: 30 - 12 - 9.6 = 8.4 left: refused for memory.
        granted, reason = self.acquire(3, 103)
        self.assertIsNone(granted)
        self.assertIn("memory", reason)

    def test_used_memory_no_longer_counts_as_reservation(self):
        self.p.mem = 24.0
        self.acquire(1, 101)
        self.ctl.update(1, scope="s1")
        self.assertIn("memory", self.acquire(2, 102)[1])
        self.p.scope_mem["s1"] = 12.0   # the slot now uses its whole budget (already out of MemAvailable)
        self.assertIsNone(self.acquire(2, 102)[1])

    def test_disk_gate(self):
        self.p.disk = 16.0
        granted, reason = self.acquire(1, 101)
        self.assertIsNone(granted)
        self.assertIn("disk", reason)

    def test_running_slot_is_told_to_shrink_when_another_is_admitted(self):
        self.p.mem = 60.0
        self.acquire(1, 101)
        self.assertEqual(self.ctl.poll(1, 20), ("ok", 20))
        self.acquire(2, 102)
        self.assertEqual(self.ctl.poll(1, 20), ("ok", 14))
        self.ctl.release(2)
        self.assertEqual(self.ctl.poll(1, 14), ("ok", 20))

    def test_dead_runner_is_pruned(self):
        self.p.mem = 60.0
        self.acquire(1, 101)
        self.acquire(2, 102)
        self.p.alive.discard(102)
        self.assertEqual(self.ctl.poll(1, 14), ("ok", 20))
        self.assertEqual(list(self.ctl.status()["slots"]), ["1"])

    def test_only_the_youngest_running_slot_freezes(self):
        self.p.mem = 60.0
        self.acquire(1, 101)
        self.acquire(2, 102)
        self.p.mem = 4.0
        self.assertEqual(self.ctl.poll(1, 14)[0], "ok")
        self.assertEqual(self.ctl.poll(2, 14)[0], "freeze")
        # Slot 2 is frozen now; if pressure persists the next youngest (slot 1) follows.
        self.assertEqual(self.ctl.poll(1, 14)[0], "freeze")

    def test_swap_growth_triggers_the_guard_until_thaw_resets_the_base(self):
        self.p.mem = 60.0
        self.acquire(1, 101)
        self.p.swap += 1.5
        action, reason = self.ctl.poll(1, 20)
        self.assertEqual(action, "freeze")
        self.assertTrue(reason.startswith("swap"))
        self.ctl.update(1, frozen=False)
        self.assertEqual(self.ctl.poll(1, 20), ("ok", 20))

    def test_free_slot_skips_registered_locked_and_excluded_slots(self):
        self.p.mem = 60.0
        self.acquire(1, 101)
        self.assertEqual(self.ctl.free_slot(20), (2, None))
        self.assertEqual(self.ctl.free_slot(20, exclude=[2]), (3, None))
        with open(os.path.join(self.root, "slots", "3", ".lock"), "w") as lock:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(self.ctl.free_slot(20, exclude=[2]), (4, None))

    def test_duplicate_registration_is_refused(self):
        self.acquire(1, 101)
        self.assertIn("already", self.acquire(1, 102)[1])


class AgentsTopTest(unittest.TestCase):
    def test_disk_refusal_names_the_largest_agent_directories(self):
        with tempfile.TemporaryDirectory() as root:
            du = "20971520\t/data/hst-agents/large-open-ship\n1048576\t/data/hst-agents/citations\n" \
                 "3145728\t/data/hst-agents/engine-version\n25165824\t/data/hst-agents\n"
            self.assertEqual(bs.agents_top(root, du=du, count=2), ["large-open-ship 20.0G", "engine-version 3.0G"])
            # Cached: a second call does not need du output.
            self.assertEqual(bs.agents_top(root, du="")[:1], ["large-open-ship 20.0G"])
            self.assertIn("large-open-ship 20.0G", bs.explain(root, "disk: 12.0 GiB free, need 17"))
            self.assertEqual(bs.explain(root, "memory: x"), "memory: x")


if __name__ == "__main__":
    unittest.main()
