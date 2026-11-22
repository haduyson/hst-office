# SPDX-License-Identifier: AGPL-3.0-only
"""Build windows of Windows slots (scripts/build_infra/slot_window.py + dispatch_windows.WindowsRunner): HST1 takes
new jobs Mon-Sat 18:00-07:30 and all Sunday (Saturday 18:00 to Monday 07:30, Asia/Saigon); a job still running when
the window closes is stopped and requeued, and a host not idle by 08:00 raises an alert."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from unittest import mock
import unittest

from build_queue_fixtures import QueueTestCase, bq, bqd
from build_infra import slot_window as sw

SAIGON = timezone(timedelta(hours=7))
HST1 = {"open": "18:00", "close": "07:30", "all_day": ["sun"], "idle_by": "08:00", "utc_offset_minutes": 420}


def at(day, hhmm):
    """Epoch seconds of 2026-11-<day> HH:MM Asia/Saigon (14 = Saturday, 15 = Sunday, 16 = Monday, 17 = Tuesday)."""
    hh, mm = map(int, hhmm.split(":"))
    return datetime(2026, 11, day, hh, mm, tzinfo=SAIGON).timestamp()


class WindowRuleTest(unittest.TestCase):
    def test_hst1_window(self):
        cases = [((14, "17:59"), False), ((14, "18:00"), True), ((15, "12:00"), True), ((16, "07:29"), True),
                 ((16, "07:31"), False), ((17, "12:00"), False), ((17, "18:00"), True), ((18, "07:29"), True),
                 ((18, "07:30"), False), ((15, "00:00"), True), ((16, "00:30"), True), ((13, "07:31"), False)]
        for (day, hhmm), want in cases:
            with self.subTest(day=day, time=hhmm):
                self.assertEqual(sw.is_open(HST1, at(day, hhmm)), want)

    def test_idle_by_and_daytime_windows(self):
        self.assertFalse(sw.overdue(HST1, at(16, "07:45")))
        self.assertTrue(sw.overdue(HST1, at(16, "08:00")))
        self.assertTrue(sw.overdue(HST1, at(17, "17:59")))
        self.assertFalse(sw.overdue(HST1, at(15, "12:00")))         # open: never overdue
        day = {"open": "09:00", "close": "17:00"}
        self.assertTrue(sw.is_open(day, at(17, "09:00")))
        self.assertFalse(sw.is_open(day, at(17, "17:00")))
        self.assertTrue(sw.is_open(None, at(17, "12:00")))          # no window: always open
        self.assertEqual(sw.describe(HST1), "18:00-07:30, all day sun, idle by 08:00 (UTC+7)")

    def test_malformed_windows_are_refused(self):
        for bad in ({"open": "18:00"}, {"open": "25:00", "close": "07:30"}, {"open": "18:00", "close": "18:00"},
                    {"open": "18:00", "close": "07:30", "all_day": ["sunday"]}, {"open": "18", "close": "07:30"},
                    {"open": "18:00", "close": "07:30", "tz": "Asia/Saigon"}, "18-07"):
            with self.subTest(bad=bad), self.assertRaises(sw.WindowError):
                sw.is_open(bad, at(17, "12:00"))


class WindowRunnerTest(QueueTestCase):
    SLOTS = [{"host": "hst1", "root": "D:\\hst-build", "jobs": 24, "window": HST1},
             {"host": "hst4", "root": "D:\\hst-build", "jobs": 24}]

    def setUp(self):
        super().setUp()
        self.runner = bqd.WindowsRunner(self.store, dict(bq.DEFAULT_CONFIG, windows_slots=self.SLOTS))
        self.calls = []
        self.status = {"state": "running"}

        def remote(host, action, *args, **kw):
            self.calls.append((host, action))
            if action == "Probe":
                return {"busy": False, "free_gib": 100}
            if action == "Status":
                return dict(self.status, log="")
            if action in ("Cancel", "Cleanup"):
                return {"ok": True}
            raise AssertionError(action)
        self.runner.remote = remote

    def free_host(self, when, jobs=()):
        self.runner.probes.clear()
        with mock.patch("time.time", return_value=when):
            slot = self.runner.free_slot(list(jobs))
        return slot and slot["host"]

    def running_on_hst1(self):
        job, _ = self.submit(platform="windows")
        Path(job["log"]).touch()
        return self.store.update(job["id"], state="running", slot="hst1:D:\\hst-build", host="hst1",
                                 win_root="D:\\hst-build", started=1)

    def test_new_jobs_only_inside_the_window(self):
        self.assertEqual(self.free_host(at(14, "18:00")), "hst1")
        self.assertEqual(self.free_host(at(17, "12:00")), "hst4")        # hst1 closed on a weekday
        busy = [{"platform": "windows", "state": "running", "slot": "hst4:D:\\hst-build"}]
        self.assertIsNone(self.free_host(at(17, "12:00"), busy))
        self.assertEqual(self.free_host(at(15, "12:00"), busy), "hst1")  # Sunday: all day

    def test_a_job_running_at_the_close_is_stopped_and_requeued(self):
        job = self.running_on_hst1()
        self.runner.enforce_windows(self.store.all(), now=at(16, "07:29"))
        self.assertNotIn(("hst1", "Cancel"), self.calls)                 # still open: untouched
        self.runner.enforce_windows(self.store.all(), now=at(16, "07:30"))
        self.assertIn(("hst1", "Cancel"), self.calls)
        self.assertTrue(self.store.load(job["id"])["window_stop"])
        self.runner.enforce_windows(self.store.all(), now=at(16, "07:31"))
        self.assertEqual(self.calls.count(("hst1", "Cancel")), 1)        # stopped once
        self.status = {"state": "failed", "error": "rc=130 (cancelled)"}
        self.assertIsNone(self.runner.check(self.store.load(job["id"])))
        again = self.store.load(job["id"])
        self.assertEqual((again["state"], again["slot"], again["window_stop"], again["window_requeues"]),
                         ("queued", None, False, 1))
        self.assertIn(("hst1", "Cleanup"), self.calls)
        self.assertIn("build window of hst1:D:\\hst-build closed", Path(job["log"]).read_text())

    def test_a_build_that_finished_before_the_stop_keeps_its_result(self):
        job = self.running_on_hst1()
        self.runner.enforce_windows(self.store.all(), now=at(16, "07:30"))
        self.status = {"state": "done", "out": "D:\\hst-build\\out\\q-x"}
        with mock.patch.object(bqd.subprocess, "run") as run:
            run.side_effect = lambda *a, **kw: os.makedirs(os.path.join(self.store.job_out(job["id"]), "q-x"),
                                                           exist_ok=True)
            state, _fields = self.runner.check(self.store.load(job["id"]))
        self.assertEqual(state, "done")

    def test_a_stop_that_fails_past_idle_by_is_an_alert(self):
        job = self.running_on_hst1()

        def broken(_job):
            raise RuntimeError("ssh: connect timed out")
        self.runner.cancel = broken
        self.runner.enforce_windows(self.store.all(), now=at(16, "07:30"))
        self.assertFalse(os.path.exists(os.path.join(self.store.root, "alerts.log")))
        self.runner.enforce_windows(self.store.all(), now=at(16, "08:00"))
        with open(os.path.join(self.store.root, "alerts.log")) as f:
            self.assertIn(f"{job['id']} still running after idle_by", f.read())
        self.assertFalse(self.store.load(job["id"]).get("window_stop"))   # retried next tick

    def test_a_malformed_window_keeps_the_slot_closed(self):
        self.runner.cfg["windows_slots"] = [dict(self.SLOTS[0], window={"open": "18:00"})]
        self.assertIsNone(self.free_host(at(14, "20:00")))


if __name__ == "__main__":
    unittest.main()
