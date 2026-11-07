# SPDX-License-Identifier: AGPL-3.0-only
"""How tests/runtime/check-ribbon-scaling.py judges a sweep, without a GUI.

The sweep's measurements are faked: a blind scan (nothing found) must fail instead of passing every
invariant vacuously, and a sweep where a group folds and the others take back its room must pass.
"""
import importlib.util
import os
import sys
import types
import unittest

from _paths import ROOT

RUNTIME = os.path.join(ROOT, "tests", "runtime")


def load():
    sys.path.insert(0, RUNTIME)
    try:
        spec = importlib.util.spec_from_file_location("check_ribbon_scaling",
                                                      os.path.join(RUNTIME, "check-ribbon-scaling.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(RUNTIME)


class Judging(unittest.TestCase):
    def setUp(self):
        self.module = load()
        self.module.ROWS.clear()
        self.module.gui = types.SimpleNamespace(xdo=lambda *args, **kwargs: None)
        self.module.time = types.SimpleNamespace(sleep=lambda seconds: None)  # the module's own name only
        self.args = types.SimpleNamespace(display=":0", shots=None)

    def run_sweep(self, scans):
        results = iter(scans)
        self.module.scan = lambda display: next(results)
        self.module.sweep(self.args, "writer", "1", office=None)
        return {row["check"]: row["status"] for row in self.module.ROWS}

    def test_blind_scan_fails(self):
        blind = [({"__groups__": {}}, None, None, None)] * len(self.module.WIDTHS)
        rows = self.run_sweep(blind)
        self.assertEqual(rows.get("[writer] the ribbon was measured at every width"), "FAIL")
        self.assertNotIn("PASS", rows.values())

    def test_fold_with_refill_judged(self):
        banner = (1500, 50, 360, 104)
        scans = []
        for width in self.module.WIDTHS:
            if width >= 1366:  # everything fits
                bars = {"clip@3": [10, 60, 200, 80], "font@9": [220, 60, 500, 80]}
                groups = {"clip@3": [10, 55, 200, 100], "font@9": [220, 55, 500, 100]}
                chevron = None
            else:  # the clipboard folds; the font group takes back some room
                bars = {"font@9": [10, 60, 520, 80]}
                groups = {"font@9": [10, 55, 520, 100]}
                chevron = (600, 60, 25, 80)
            scans.append(({**bars, "__groups__": groups}, chevron, banner, 182))
        rows = self.run_sweep(scans)
        failed = [name for name, status in rows.items() if status != "PASS"]
        # the first fold (clipboard at 1280) leaves 70 px, less than the clipboard's 200
        self.assertEqual(failed, ["[writer] groups shrink before the first fold (1280 px)"])


if __name__ == "__main__":
    unittest.main()
