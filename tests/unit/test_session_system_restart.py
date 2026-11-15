# SPDX-License-Identifier: AGPL-3.0-only
"""An unclosed session says whether the computer started again after the office's last sign of life.

Two reports from one PC (the second one describes only "sleep mode") both read "previous session not closed", no
crash signature, nothing from the system: an office ended in Task Manager and one
that went down with the computer (battery empty while asleep, power lost, a restart it was not told about) looked the
same. The next start now compares the system's boot time with the heartbeat (else the session's start).
"""
import os
import sys
import tempfile
import types
import unittest

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.task",
              "com.sun.star.awt"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import diag_crash, diag_log, system_boot  # noqa: E402

START = 1_763_120_035.0  # 2025-11-14T11:33:55Z
BEAT = START + 3600.0


class SinceTest(unittest.TestCase):
    def test_boot_after_last_heartbeat_is_a_restart(self):
        self.assertEqual(system_boot.since({"started": START, "beat": BEAT}, BEAT + 900), "restarted")

    def test_boot_before_the_session_is_running(self):
        self.assertEqual(system_boot.since({"started": START, "beat": BEAT}, START - 86400), "running")

    def test_heartbeat_wins_over_start(self):
        # Booted during the session but before its last heartbeat: the office lived on after that boot time
        # (clock moved), so this is no restart under the office.
        self.assertEqual(system_boot.since({"started": START, "beat": BEAT}, START + 600), "running")

    def test_no_heartbeat_uses_the_start(self):
        self.assertEqual(system_boot.since({"started": START}, START + 600), "restarted")

    def test_within_slack_is_running(self):
        self.assertEqual(system_boot.since({"started": START}, START + system_boot.SLACK - 1), "running")

    def test_unknown_times(self):
        self.assertIsNone(system_boot.since({"started": START}, None))
        self.assertIsNone(system_boot.since({}, START))
        self.assertIsNone(system_boot.since(None, START))


class BootTimeTest(unittest.TestCase):
    def test_this_system_has_a_boot_time_in_the_past(self):
        boot = system_boot.boot_time()
        if boot is None:
            self.skipTest("no boot time on this platform")
        self.assertLess(boot, system_boot.time.time())
        self.assertGreater(boot, 946684800)  # after 2000

    def test_unknown_platform(self):
        self.assertIsNone(system_boot.boot_time("Plan9"))


class PreviousSessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = diag_log.log_dir
        diag_log.log_dir = lambda: self.tmp.name

    def tearDown(self):
        diag_log.log_dir = self.old
        self.tmp.cleanup()

    def found(self, boot):
        marker = {"started": START, "pid": 4242, "version": "1.0.2", "beat": BEAT, "apps": ["calc"],
                  "active": "calc", "modified": 1, "loading": 0}
        return diag_crash.previous_session("Linux", marker=marker, stderr_text="", boot=boot)

    def test_restart_keeps_not_closed_and_adds_the_system_state(self):
        found = self.found(BEAT + 6000)
        self.assertEqual(found["ended"], "not closed")  # the crash question and recovery stay as they were
        self.assertEqual(found["system"], "restarted")
        lines = diag_crash.facts(found)
        self.assertIn("Crash signature: none recorded by the office or the system", lines)
        self.assertTrue(lines[-1].startswith("System started at 2025-11-14T14:13:55Z, after the session's last"))

    def test_system_kept_running(self):
        found = self.found(START - 7200)
        self.assertEqual(found["system"], "running")
        self.assertIn("no restart seen", diag_crash.facts(found)[-1])

    def test_unreadable_boot_time_adds_no_line(self):
        found = diag_crash.previous_session("Plan9", marker={"started": START}, stderr_text="")
        self.assertIsNone(found["system"])
        self.assertFalse([line for line in diag_crash.facts(found) if line.startswith("System ")])

    def test_old_previous_dict_without_system_adds_no_line(self):
        self.assertEqual(system_boot.facts({"ended": "not closed", "started": START}), [])

    def test_marker_and_lines_carry_no_names(self):
        found = self.found(BEAT + 6000)
        text = "\n".join(diag_crash.facts(found))
        self.assertNotIn(os.path.expanduser("~"), text)


if __name__ == "__main__":
    unittest.main()
