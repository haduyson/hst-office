# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up phases from window samples and the Python trace (scripts/perf/startup_phases.py)."""
import os
import sys
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "scripts", "perf"))
import startup_phases as sp  # noqa: E402

SPLASH = (644, 199)


class WindowKinds(unittest.TestCase):
    def test_the_splash_is_recognised_at_every_scale_and_with_window_positions(self):
        for scale in (1, 1.25, 1.5, 2):
            window = (1, round(644 * scale), round(199 * scale), "", "")
            self.assertEqual(sp.kind_of(window, SPLASH), "splash", scale)
        self.assertEqual(sp.kind_of((1, 644, 199, "", "", 300, 280), SPLASH), "splash")  # Windows: left, top added
        self.assertEqual(sp.kind_of((1, 1040, 744, "HST Office", "", 0, 0), SPLASH), "frame")
        self.assertEqual(sp.kind_of((1, 536, 191, "HST Office", "dialog"), SPLASH), "dialog")  # the OS said so

    def test_phases_of_a_start_with_a_restart(self):
        samples = [(0.1, []), (0.2, [(1, 644, 199, "", "")]), (0.9, []), (1.1, [(2, 644, 199, "", "")]),
                   (1.8, [(2, 644, 199, "", ""), (2, 1040, 744, "HST Office", "")]), (2.0, [(2, 1040, 744, "x", "")])]
        result = sp.phases(samples, SPLASH)
        self.assertEqual((result["splash_shown"], result["splash_gone"], result["frame_shown"]), (0.2, 1.1, 1.8))
        self.assertEqual(result["splash_visible_s"], 0.9)
        self.assertEqual(result["pids"], [1, 2])

    def test_no_window(self):
        self.assertIsNone(sp.phases([(0.1, []), (5.0, [])], SPLASH)["frame_shown"])


class PythonBreakdown(unittest.TestCase):
    def test_imports_and_compiles_are_split_at_the_first_window(self):
        launched = 1000.0
        events = [
            {"ev": "python-init", "t": 1000.5, "pid": 7},
            {"ev": "compile", "path": "b.py", "dt": 0.05, "t": 1000.65, "pid": 7},
            {"ev": "import", "mod": "hst_office.b", "dt": 0.1, "src": "py", "t": 1000.7, "pid": 7},  # inside a
            {"ev": "import", "mod": "hst_office.a", "dt": 0.3, "src": "py", "t": 1000.9, "pid": 7},
            {"ev": "compile", "path": "c.py", "dt": 0.2, "t": 1001.6, "pid": 7},
            {"ev": "import", "mod": "hst_office.c", "dt": 0.4, "src": "py", "t": 1001.8, "pid": 7},  # after the window
            {"ev": "call", "what": "hst_office.x.Job.execute", "dt": 0.01, "t": 1000.95, "thread": "MainThread"},
            {"ev": "net", "what": "connect", "host": "h", "t": 1002.0, "thread": "hst-update-check"}]
        out = sp.python_breakdown(events, launched, frame_shown=1.0)
        self.assertEqual(out["python_init_s"], 0.5)
        self.assertEqual(out["imports_s"], 0.7)  # top-level only: a (0.3) and c (0.4), b is nested in a
        self.assertEqual((out["compiled"], out["compile_s"]), (2, 0.25))
        before = out["before_frame"]
        self.assertEqual((before["modules"], before["compiled"], before["compile_s"]), (2, 1, 0.05))
        self.assertEqual(before["imports_s"], 0.3)
        self.assertEqual(before["hst_modules"], ["hst_office.a", "hst_office.b"])
        self.assertEqual(out["network"], [(2.0, "connect", "h", "hst-update-check")])
        self.assertEqual(out["calls"][0][1:], ("hst_office.x.Job.execute", 0.01, "MainThread"))


if __name__ == "__main__":
    unittest.main()
