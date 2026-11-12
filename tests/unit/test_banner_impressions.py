# SPDX-License-Identifier: AGPL-3.0-only
"""Local banner display counts: day rollover, caps, 7-day retention, atomic shared file, batched writes."""
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401 - makes the extension package importable
from hst_office import banner_cache, banner_impressions as imp

NOW = 1795003200.0  # 2026-11-18T12:00:00Z: the same local day from UTC-11 to UTC+11
DAY = 86400


class Clock:
    def __init__(self, now=NOW):
        self.now, self.mono = now, 0.0

    def time(self):
        return self.now

    def monotonic(self):
        return self.mono


def day(timestamp):
    return imp.local_day(timestamp).isoformat()


class CounterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "hst-banners"
        self.clock = Clock()
        self.counter = imp.Counter(self.root, self.clock.time, self.clock.monotonic)

    def stored(self):
        return json.loads((self.root / imp.FILE).read_text())

    def test_records_stay_in_memory_until_sixty_seconds(self):
        self.assertTrue(self.counter.record("aios"))
        self.assertFalse((self.root / imp.FILE).exists())
        self.clock.mono = imp.FLUSH_SECONDS
        self.counter.record("aios")
        self.assertEqual(self.stored(), {"schemaVersion": 1, "days": {day(NOW): {"aios": 2}}})

    def test_explicit_flush_merges_with_the_file_of_other_processes(self):
        self.counter.record("aios")
        self.counter.flush()
        other = imp.Counter(self.root, self.clock.time, self.clock.monotonic)
        other.record("aios")
        other.record("hst-post")
        other.flush()
        self.assertEqual(self.stored()["days"], {day(NOW): {"aios": 2, "hst-post": 1}})

    def test_day_rollover_counts_into_the_new_local_day(self):
        self.counter.record("aios")
        self.clock.now += DAY
        self.counter.record("aios")
        self.counter.record("aios")
        self.counter.flush()
        self.assertEqual(self.stored()["days"], {day(NOW): {"aios": 1}, day(NOW + DAY): {"aios": 2}})

    def test_cap_per_id_and_day(self):
        self.counter.flush()
        with mock.patch.object(imp, "MAX_COUNT", 3):
            for _ in range(5):
                self.counter.record("aios")
            self.counter.flush()
            self.counter.record("aios")
            self.counter.flush()
        self.assertEqual(self.stored()["days"][day(NOW)], {"aios": 3})

    def test_at_most_24_ids_per_day(self):
        for n in range(30):
            self.counter.record("id-%d" % n)
        self.counter.flush()
        self.assertEqual(len(self.stored()["days"][day(NOW)]), imp.MAX_IDS)

    def test_invalid_ids_are_not_counted(self):
        for value in ("", "AIOS", "-x", "a" * 65, "a/b", None, 7, "aios\n"):
            self.assertFalse(self.counter.record(value))
        self.counter.flush()
        self.assertFalse((self.root / imp.FILE).exists())

    def test_seven_day_retention(self):
        for n in range(10):
            self.clock.now = NOW + n * DAY
            self.counter.record("aios")
            self.counter.flush()
        days = self.stored()["days"]
        self.assertEqual(sorted(days), [day(NOW + n * DAY) for n in range(3, 10)])

    def test_far_future_days_left_by_a_clock_set_back_are_dropped(self):
        self.clock.now = NOW + 30 * DAY
        self.counter.record("aios")
        self.counter.flush()
        self.clock.now = NOW
        self.counter.record("hst-post")
        self.counter.flush()
        self.assertEqual(self.stored()["days"], {day(NOW): {"hst-post": 1}})

    def test_write_is_atomic_and_a_failure_keeps_counts_pending(self):
        self.counter.record("aios")
        self.counter.flush()
        before = (self.root / imp.FILE).read_bytes()
        self.counter.record("aios")
        with mock.patch.object(banner_cache.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(self.counter.flush())
        self.assertEqual((self.root / imp.FILE).read_bytes(), before)
        self.assertEqual(sorted(os.listdir(self.root)), [imp.FILE, imp.LOCK])  # no temporary file left
        self.assertTrue(self.counter.flush())
        self.assertEqual(self.stored()["days"][day(NOW)], {"aios": 2})

    def test_read_only_profile_never_raises(self):
        self.counter.record("aios")
        with mock.patch.object(imp, "file_lock", side_effect=PermissionError("read-only")):
            self.assertFalse(self.counter.flush())
            self.clock.mono = imp.FLUSH_SECONDS
            self.assertTrue(self.counter.record("aios"))

    def test_corrupt_or_foreign_file_counts_as_empty(self):
        self.root.mkdir(parents=True)
        for content in (b"{not json", b"[]", json.dumps({"schemaVersion": 2, "days": {}}).encode()):
            (self.root / imp.FILE).write_bytes(content)
            self.assertEqual(imp.load(self.root, imp.local_day(NOW)), {})

    def test_prune_drops_malformed_entries(self):
        today = datetime.date(2026, 11, 18)
        days = {"2026-11-18": {"aios": 2, "Bad": 1, "zero": 0, "neg": -1, "flt": 1.5, "boo": True, "big": 9999},
                "2026-11-19": {"aios": 1}, "2026-11-20": {"aios": 1}, "2026-11-11": {"aios": 1},
                "2026-02-30": {"aios": 1}, "18/11/2026": {"aios": 1}, "2026-11-17": [], "2026-11-16": {}}
        self.assertEqual(imp.prune(days, today), {"2026-11-18": {"aios": 2, "big": imp.MAX_COUNT},
                                                  "2026-11-19": {"aios": 1}})
        self.assertEqual(imp.prune(None, today), {})


if __name__ == "__main__":
    unittest.main()
