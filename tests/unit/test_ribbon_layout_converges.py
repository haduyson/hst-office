# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""tests/runtime/check-ribbon-layout-converges.py (the ribbon's layout settles) and the settle wait of
collect-ribbon-v3-dumps.py: the parts that run without an office."""
import argparse
import importlib.util
import os
import tempfile
import threading
import time
import unittest

RUNTIME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime")


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(RUNTIME, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


converges = load("check-ribbon-layout-converges")
collect = load("collect-ribbon-v3-dumps")
LIMITS = argparse.Namespace(max_passes=4, max_cpu=0.05)


class Verdict(unittest.TestCase):
    def test_a_settled_ribbon_passes(self):
        self.assertEqual(converges.verdict("calc w1536 Xem", 0, 0.01, LIMITS)["problems"], [])
        self.assertEqual(converges.verdict("calc w1536 Xem", 4, 0.05, LIMITS)["problems"], [])

    def test_a_layout_that_does_not_settle_fails(self):
        self.assertTrue(converges.verdict("case", 5, 0.0, LIMITS)["problems"])
        self.assertTrue(converges.verdict("case", 0, 0.9, LIMITS)["problems"])

    def test_a_build_without_the_counter_is_judged_by_cpu_alone(self):
        self.assertEqual(converges.verdict("case", None, 0.0, LIMITS)["problems"], [])
        self.assertTrue(converges.verdict("case", None, None, LIMITS)["problems"])  # the office is gone

    def test_counter_and_cpu_readers(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(converges.layout_passes(tmp))
            with open(os.path.join(tmp, "layout-passes"), "w", encoding="ascii") as handle:
                handle.write("17\n")
            self.assertEqual(converges.layout_passes(tmp), 17)
        self.assertGreaterEqual(converges.cpu_seconds(os.getpid()), 0)
        self.assertIsNone(converges.cpu_seconds(2 ** 22 + 12345))


class Settle(unittest.TestCase):
    def test_without_a_counter_it_waits_the_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = time.monotonic()
            collect.settle(tmp, 0.3)
            self.assertGreaterEqual(time.monotonic() - start, 0.3)

    def test_it_returns_once_the_count_is_stable_for_a_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "layout-passes")

            def passes():
                for count in range(1, 6):
                    with open(path, "w", encoding="ascii") as handle:
                        handle.write(f"{count}\n")
                    time.sleep(0.3)

            with open(path, "w", encoding="ascii") as handle:
                handle.write("0\n")
            writer = threading.Thread(target=passes)
            start = time.monotonic()
            writer.start()
            collect.settle(tmp, 0.0, longest=10.0)
            elapsed = time.monotonic() - start
            writer.join()
            self.assertGreaterEqual(elapsed, 1.5)  # 5 passes 0.3 s apart, then a second of quiet
            self.assertLess(elapsed, 5.0)

    def test_the_counter_is_not_moved_with_the_dumps(self):
        with tempfile.TemporaryDirectory() as tmp:
            live, target = os.path.join(tmp, "live"), os.path.join(tmp, "w1366")
            os.makedirs(live)
            for name in ("layout-passes", "pmhbHome-1366.json"):
                open(os.path.join(live, name), "w", encoding="ascii").close()
            self.assertEqual(collect.move_dumps(live, target), 1)
            self.assertEqual(os.listdir(live), ["layout-passes"])


if __name__ == "__main__":
    unittest.main()
