# SPDX-License-Identifier: AGPL-3.0-only
"""Disk shortage on build hosts: it counts as an infrastructure failure (requeue, and no train blame), a Windows
slot whose drive is below windows_min_free_gib gets no job, and below windows_warn_free_gib the dispatcher writes a
warning with the largest D:\\hst-test folders (read only) that `list` and `disk-report` show."""
import io
import json
import os
import time

from build_queue_fixtures import QueueTestCase, bq, bqd
from build_infra import queue_cli
from build_infra.queue_train import job_outcome

SLOTS = [{"host": "hst5", "root": "D:\\hst-build", "jobs": 28}, {"host": "hst4", "root": "D:\\hst-build", "jobs": 28}]
REPORT = {"d_free_gib": 13.3, "c_free_gib": 40.0, "taken": "2026-11-14T18:00:00",
          "folders": [{"name": "launchers-images", "gib": 9.1, "files": 812, "newest": "2026-11-14T17:30:00",
                       "owner": "fix/ribbon-launchers"}, {"name": "old", "gib": 2.0, "files": 3,
                                                         "newest": "2026-11-12T09:00:00", "owner": ""}]}


class DiskShortageTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.cfg = dict(bq.DEFAULT_CONFIG, windows_slots=SLOTS)
        with open(os.path.join(self.store.root, "config.json"), "w") as f:
            json.dump({"windows_slots": SLOTS}, f)
        self.runner = bqd.WindowsRunner(self.store, self.cfg)
        self.free = {"hst5": 13.3, "hst4": 40.0}
        self.calls = []

        def remote(host, action, *args, **kw):
            self.calls.append((host, action))
            if action == "Probe":
                return {"busy": False, "free_gib": self.free[host]}
            if action == "DiskReport":
                return dict(REPORT, d_free_gib=self.free[host])
            raise AssertionError(action)
        self.runner.remote = remote

    def test_disk_shortage_is_infrastructure_and_never_blamed_on_a_branch(self):
        msg = "D: has 13.3 GiB free, below 15 GiB"
        self.assertTrue(bq.infra_failure(msg, ""))
        self.assertTrue(bq.infra_failure("local-build.sh exit 1", "local-build: disk-stop: less than 5 GiB free on /x"))
        self.assertFalse(bq.infra_failure("local-build.sh exit 2", "make: *** [Makefile:312: build] Error 2"))
        self.assertEqual(job_outcome({"state": "failed", "error": msg}, bq.infra_failure), "error")

    def test_low_disk_slot_gets_no_job_and_a_warning_names_the_largest_folders(self):
        self.assertEqual(self.runner.free_slot([])["host"], "hst4")   # hst5 (13.3 GiB) skipped
        self.assertEqual(self.calls.count(("hst5", "DiskReport")), 1)
        with open(os.path.join(self.store.root, "alerts.log")) as f:
            alerts = f.read()
        self.assertIn("WARNING hst5 D: 13.3 GiB free (< 25 GiB)", alerts)
        self.assertIn("launchers-images 9.1 GiB", alerts)
        self.assertIn("owner fix/ribbon-launchers", alerts)
        self.runner.probes.clear()
        self.runner.free_slot([])
        self.assertEqual(self.calls.count(("hst5", "DiskReport")), 1)   # at most once an hour
        self.free["hst5"] = 20.0                                        # above the floor, below the warning
        self.runner.probes.clear()
        self.runner.warned.clear()
        self.assertEqual(self.runner.free_slot([])["host"], "hst5")
        self.assertEqual(self.calls.count(("hst5", "DiskReport")), 2)
        self.assertNotIn(("hst4", "DiskReport"), self.calls)            # 40 GiB: no report needed

    def test_list_warns_and_disk_report_prints_the_saved_report(self):
        self.runner.disk_report("hst5")
        self.assertEqual(queue_cli.disk_warnings(self.store),
                         ["WARNING hst5: D: 13.3 GiB free (< 25); `build-queue.sh disk-report --host hst5`"])
        out = io.StringIO()
        self.assertEqual(queue_cli.disk_report(self.store, "hst5", out=out), 0)
        text = out.getvalue()
        self.assertIn("hst5: D: 13.3 GiB free", text)
        self.assertIn("fix/ribbon-launchers", text)
        self.assertIn("D:\\hst-test\\launchers-images", text)
        with open(os.path.join(self.store.root, "windows-disk.json")) as f:
            saved = json.load(f)
        saved["hst5"]["fetched"] = time.time() - 3 * 3600   # an old report no longer warns
        with open(os.path.join(self.store.root, "windows-disk.json"), "w") as f:
            json.dump(saved, f)
        self.assertEqual(queue_cli.disk_warnings(self.store), [])
        with self.assertRaises(bq.QueueError):
            queue_cli.disk_report(self.store, "hst9")
