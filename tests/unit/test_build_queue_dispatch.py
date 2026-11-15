# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue dispatcher (scripts/build-queue-dispatcher.py): scheduling order, start failures, cancel, Windows
slot pool and drain, and the outputs a Linux job returns. Fake runners instead of real builds."""
import io
import os
from pathlib import Path
import unittest

from build_queue_fixtures import FakeRunner, QueueTestCase, bq, bqd


class LinuxOutputsTest(QueueTestCase):
    def test_linux_runner_collects_deb_rpm_appimage_and_overlays(self):
        job, _ = self.submit()
        runner = bqd.LinuxRunner(self.store, bq.DEFAULT_CONFIG)
        out = self.store.job_out(job["id"])
        os.makedirs(out)
        for name in ("a.deb", "a.rpm", "a.AppImage", "SHA256SUMS", "build.log"):
            Path(out, name).write_text("x")
        Path(runner.rc_path(job)).write_text("0\n")
        state, fields = runner.check(job)
        self.assertEqual(state, "done")
        self.assertEqual([os.path.basename(p) for p in fields["output"]], ["a.AppImage", "a.deb", "a.rpm"])


class DispatcherTest(QueueTestCase):
    def test_priority_then_fifo_per_platform(self):
        low, _ = self.submit(ref="feat/x")
        high, _ = self.submit(priority=10)
        win, _ = self.submit(platform="windows")
        linux, windows = FakeRunner(["1"]), FakeRunner(["hst4:D:\\hst-build"])
        bqd.tick(self.store, {"linux": linux, "windows": windows}, bq)
        self.assertEqual(linux.started, [high["id"]])
        self.assertEqual(windows.started, [win["id"]])
        self.assertEqual(self.store.load(low["id"])["state"], "queued")
        linux.results[high["id"]] = ("done", {"output": []})
        bqd.tick(self.store, {"linux": linux, "windows": windows}, bq)
        self.assertEqual(self.store.load(high["id"])["state"], "done")
        self.assertEqual(linux.started, [high["id"], low["id"]])

    def test_failed_start_marks_the_job_failed(self):
        job, _ = self.submit()
        runners = {"linux": FakeRunner(["broken"]), "windows": FakeRunner([])}
        for _ in range(3):   # a start failure counts as infrastructure: two retries, then failed
            bqd.tick(self.store, runners, bq)
        state = self.store.load(job["id"])
        self.assertEqual(state["infra_retries"], 2)
        self.assertEqual(state["state"], "failed")
        self.assertIn("cannot start", state["error"])

    def test_cancel_request_is_sent_once(self):
        job, _ = self.submit()
        linux = FakeRunner(["1"])
        runners = {"linux": linux, "windows": FakeRunner([])}
        bqd.tick(self.store, runners, bq)
        bq.cancel(self.store, job["id"])
        bqd.tick(self.store, runners, bq)
        bqd.tick(self.store, runners, bq)
        self.assertEqual(linux.cancelled, [job["id"]])
        linux.results[job["id"]] = ("cancelled", {"error": "stopped"})
        bqd.tick(self.store, runners, bq)
        self.assertEqual(self.store.load(job["id"])["state"], "cancelled")

    def test_windows_jobs_are_shared_per_host(self):
        runner = bqd.WindowsRunner(self.store, bq.DEFAULT_CONFIG)
        slot = {"host": "hst5", "root": "D:\\hst-build-s2", "jobs": 28}
        self.assertEqual(runner.jobs_for(slot), 28)
        job, _ = self.submit(platform="windows")
        self.store.update(job["id"], state="running", host="hst5")
        self.assertEqual(runner.jobs_for(slot), 14)
        self.assertEqual(runner.jobs_for({"host": "hst4", "root": "D:\\hst-build", "jobs": 28}), 28)

    def test_drain_holds_new_jobs_until_idle_then_deploys_and_resumes(self):
        cfg = dict(bq.DEFAULT_CONFIG, windows_slots=[{"host": "hst5", "root": "D:\\hst-build", "jobs": 28}])
        runner = bqd.WindowsRunner(self.store, cfg)
        deployed, busy = [], {"hst5": True}
        runner.host_busy = lambda host: busy[host]
        runner.deploy = lambda host, force=False: deployed.append((host, force)) or "abc123"
        runner.remote = lambda host, action, *a, **k: {"busy": False}
        with open(os.path.join(self.store.root, "config.json"), "w") as f:
            import json
            json.dump({"windows_slots": cfg["windows_slots"]}, f)
        out = io.StringIO()
        self.assertEqual(bq.drain(self.store, "hst5", wait_done=False, out=out), 0)
        self.assertIsNone(runner.free_slot([]))            # draining: no new job goes to hst5
        runner.process_drains([], bq)
        self.assertEqual(deployed, [])                      # a build still runs there
        busy["hst5"] = False
        runner.process_drains([], bq)
        self.assertEqual(deployed, [("hst5", True)])
        self.assertEqual(self.store.drains()["hst5"]["state"], "done")
        self.assertEqual(runner.free_slot([])["host"], "hst5")
        with self.assertRaises(bq.QueueError):
            bq.drain(self.store, "hst9", wait_done=False, out=out)
        bq.drain(self.store, "hst5", wait_done=False, out=out, hold=True)
        runner.process_drains([], bq)
        self.assertEqual(self.store.drains()["hst5"]["state"], "held")
        self.assertIsNone(runner.free_slot([]))            # held: stays idle after the deploy
        bq.drain(self.store, "hst5", cancel=True, out=out)
        self.assertEqual(runner.free_slot([])["host"], "hst5")
        bq.drain(self.store, "hst5", wait_done=False, out=out)
        bq.drain(self.store, "hst5", cancel=True, out=out)
        self.assertEqual(self.store.drains()["hst5"]["state"], "cancelled")
        self.assertEqual(runner.free_slot([])["host"], "hst5")
        with self.assertRaises(bq.QueueError):
            bq.drain(self.store, "hst5", cancel=True, out=out)

    def test_windows_task_names_fit_hst4_detach(self):
        job, _ = self.submit(platform="windows")
        self.assertRegex(bqd.win_task_name(job["id"]), r"^q-[0-9a-f-]{6,40}$")


if __name__ == "__main__":
    unittest.main()
