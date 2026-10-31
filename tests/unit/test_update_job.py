# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up update job without an office: UNO modules are stubbed, settings and UI are recorded.

Covers: AutoCheck off, 24 h throttle (attempt time stored before the network), skip-version memory,
silent failure offline, and that the result reaches the UI through the main-thread hand-off only.
"""
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    """Any attribute is a fresh class, so `class X(unohelper.Base, XJob, ...)` builds without the office."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.document",
              "com.sun.star.frame", "com.sun.star.lang", "com.sun.star.task"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import update_job as job  # noqa: E402
from hst_office import update_logic as logic  # noqa: E402
from hst_office.update_fetch import UpdateError  # noqa: E402

NOW = 2_000_000_000
INFO = {"release": "1.0.0-beta.2", "channel": "beta", "test_mode": False}


def channels(version):
    rel = {"channel": "beta", "version": version, "date": "2026-10-30", "notes": "https://office.hasontech.vn/",
           "downloads": {"linux": "https://office.hasontech.vn/tai/linux"}, "critical": False}
    return {"stable": None, "beta": rel}


class StartupJob(unittest.TestCase):
    def setUp(self):
        self.prefs = {"AutoCheck": True, "ManualCheck": True, "CheckIntervalHours": 24, "LastCheck": 0,
                      "SkippedVersion": "", "Channel": ""}
        self.notified, self.fetches = [], []
        patches = [
            mock.patch.object(job.ui, "settings", lambda ctx: dict(self.prefs)),
            mock.patch.object(job.ui, "save", lambda ctx, k, v: self.prefs.__setitem__(k, v)),
            mock.patch.object(job.ui, "proxy", lambda ctx: None),
            mock.patch.object(job.ui, "on_main_thread", lambda ctx, fn: fn()),
            mock.patch.object(job.ui, "notify", lambda ctx, rel, installed: self.notified.append(rel["version"])),
            mock.patch.object(job.ui, "release_info_for",
                              lambda ctx: dict(INFO, channel=logic.effective_channel(INFO["channel"], self.prefs["Channel"]))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_check(self, result, now=NOW):
        def fake_fetch(info, proxy):
            self.fetches.append(info["release"])
            if isinstance(result, Exception):
                raise result
            return result
        with mock.patch.object(job, "fetch_channels", fake_fetch):
            thread = job.automatic_check(object(), now)
            if thread is not None:
                thread.join(10)
        return thread

    def test_new_version_is_announced_and_attempt_time_stored(self):
        self.run_check(channels("1.0.0"))
        self.assertEqual(self.notified, ["1.0.0"])
        self.assertEqual(self.prefs["LastCheck"], NOW)

    def test_interval_from_the_administrator_setting(self):
        self.prefs["CheckIntervalHours"] = 168
        self.run_check(channels("1.0.0"))
        self.assertIsNone(self.run_check(channels("1.0.0"), NOW + 7 * 24 * 3600 - 1))
        self.assertIsNotNone(self.run_check(channels("1.0.0"), NOW + 7 * 24 * 3600))
        self.assertEqual(len(self.fetches), 2)

    def test_channel_stable_hides_betas(self):
        self.prefs["Channel"] = "stable"
        self.run_check(channels("1.0.0"))
        self.assertEqual(self.notified, [])

    def test_at_most_once_per_24_hours(self):
        self.run_check(channels("1.0.0"))
        self.assertIsNone(self.run_check(channels("1.0.0"), NOW + logic.CHECK_INTERVAL - 1))
        self.assertEqual(len(self.fetches), 1)
        self.run_check(channels("1.0.0"), NOW + logic.CHECK_INTERVAL)
        self.assertEqual(len(self.fetches), 2)

    def test_auto_check_off_does_nothing(self):
        self.prefs["AutoCheck"] = False
        self.assertIsNone(self.run_check(channels("1.0.0")))
        self.assertEqual((self.fetches, self.prefs["LastCheck"]), ([], 0))

    def test_skipped_version_is_remembered(self):
        self.prefs["SkippedVersion"] = "1.0.0"
        self.run_check(channels("1.0.0"))
        self.assertEqual(self.notified, [])
        self.prefs["LastCheck"] = 0
        self.run_check(channels("1.0.1"))  # a later version is announced again
        self.assertEqual(self.notified, ["1.0.1"])

    def test_up_to_date_and_offline_are_silent(self):
        self.run_check(channels("1.0.0-beta.2"))
        self.prefs["LastCheck"] = 0
        with mock.patch("builtins.print"):
            self.run_check(UpdateError("URLError: offline"))
            self.prefs["LastCheck"] = 0
            self.run_check(RuntimeError("unexpected"))
        self.assertEqual(self.notified, [])


if __name__ == "__main__":
    unittest.main()
