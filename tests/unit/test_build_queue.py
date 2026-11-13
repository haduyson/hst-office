# SPDX-License-Identifier: AGPL-3.0-only
"""Local build queue: submit/dedupe/cancel/wait/retention (scripts/build-queue.py) and the dispatcher's
scheduling order (scripts/build-queue-dispatcher.py), with fake runners instead of real builds."""
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bq = load("build_queue_for_test", "scripts/build-queue.py")
bqd = load("build_queue_dispatcher_for_test", "scripts/build-queue-dispatcher.py")
SHA_A = "a" * 40
SHA_B = "b" * 40


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = bq.Store(tmp.name)
        self.shas = {"rc/1.0.2-batch4": SHA_A, "feat/x": SHA_B}

    def submit(self, platform="linux", ref="rc/1.0.2-batch4", **kw):
        return bq.submit(self.store, platform, ref, resolver=lambda r: self.shas.get(r, r), submitter="t", **kw)

    def finish(self, job, files=("HSTOffice.deb",), finished=None):
        out = self.store.job_out(job["id"])
        os.makedirs(out, exist_ok=True)
        paths = []
        for name in files:
            p = os.path.join(out, name)
            Path(p).write_text("x")
            paths.append(p)
        return self.store.update(job["id"], state="done", output=paths, finished=finished or job["submitted"])


class SubmitTest(QueueTestCase):
    def test_submit_records_a_queued_job(self):
        job, dup = self.submit(priority=5)
        self.assertFalse(dup)
        self.assertRegex(job["id"], bq.ID_RE)
        self.assertEqual((job["state"], job["sha"], job["label"], job["priority"]), ("queued", SHA_A, "rc_1.0.2-batch4", 5))
        self.assertEqual(self.store.load(job["id"])["key"], f"linux:{SHA_A}:package:")

    def test_identical_active_job_is_returned(self):
        first, _ = self.submit()
        again, dup = self.submit()
        self.assertTrue(dup)
        self.assertEqual(again["id"], first["id"])

    def test_options_and_platform_are_part_of_the_key(self):
        first, _ = self.submit()
        self.assertFalse(self.submit(package=False)[1])
        self.assertFalse(self.submit(platform="windows")[1])
        mods, _ = self.submit(modules=["sw", "sc"])
        same, dup = self.submit(modules=["sc", "sw"])
        self.assertTrue(dup)
        self.assertEqual(same["id"], mods["id"])
        self.assertFalse(mods["package"])
        self.assertNotEqual(mods["id"], first["id"])

    def test_done_job_with_output_is_reused_but_not_after_retention_or_failure(self):
        job, _ = self.submit()
        self.finish(job)
        self.assertEqual(self.submit()[0]["id"], job["id"])
        self.store.update(job["id"], output_deleted=True)
        fresh, dup = self.submit()
        self.assertFalse(dup)
        self.store.update(fresh["id"], state="failed")
        self.assertFalse(self.submit()[1])

    def test_validation(self):
        with self.assertRaises(bq.QueueError):
            self.submit(platform="mac")
        with self.assertRaises(bq.QueueError):
            self.submit(priority=1000)
        with self.assertRaises(bq.QueueError):
            self.submit(platform="windows", package=False)
        with self.assertRaises(bq.QueueError):
            bq.parse_modules("sc,../x")
        self.assertEqual(bq.parse_modules("sc, sw"), ["sc", "sw"])
        with self.assertRaises(bq.QueueError):
            bq.resolve_ref("a..b")

    def test_label_for_sha_refs(self):
        self.assertEqual(bq.label_for("abcdef1", "abcdef1" + "0" * 33), "commit")
        self.assertEqual(bq.label_for("feat/x", SHA_B), "feat_x")


class CancelWaitTest(QueueTestCase):
    def test_cancel_queued_and_running(self):
        job, _ = self.submit()
        self.assertEqual(bq.cancel(self.store, job["id"])["state"], "cancelled")
        with self.assertRaises(bq.QueueError):
            bq.cancel(self.store, job["id"])
        other, _ = self.submit(ref="feat/x")
        self.store.update(other["id"], state="running")
        self.assertTrue(bq.cancel(self.store, other["id"])["cancel_requested"])

    def test_wait_prints_outputs_or_log_tail(self):
        job, _ = self.submit()
        done = self.finish(job)
        out = io.StringIO()
        self.assertEqual(bq.wait(self.store, job["id"], out=out), 0)
        self.assertEqual(out.getvalue().strip(), done["output"][0])
        bad, _ = self.submit(ref="feat/x")
        Path(bad["log"]).write_text("line1\nmake: *** [all] Error 2\n")
        self.store.update(bad["id"], state="failed", error="local-build.sh exit 2")
        out = io.StringIO()
        self.assertEqual(bq.wait(self.store, bad["id"], out=out), 1)
        self.assertIn("Error 2", out.getvalue())

    def test_wait_times_out(self):
        job, _ = self.submit()
        self.assertEqual(bq.wait(self.store, job["id"], timeout=0, interval=0, out=io.StringIO()), 2)

    def test_bad_ids_are_rejected(self):
        with self.assertRaises(bq.QueueError):
            self.store.load("../etc/passwd")


class RetentionTest(QueueTestCase):
    def test_keeps_newest_per_platform_and_branch(self):
        ids = []
        for i in range(5):
            self.shas["rc/1.0.2-batch4"] = f"{i:040d}"
            job, _ = self.submit()
            self.finish(job, finished=1000 + i)
            ids.append(job["id"])
        self.shas["feat/x"] = "f" * 40
        other, _ = self.submit(ref="feat/x")
        self.finish(other, finished=1)
        bq.apply_retention(self.store, 3)
        deleted = {j["id"] for j in self.store.all() if j.get("output_deleted")}
        self.assertEqual(deleted, set(ids[:2]))
        for jid in ids[:2]:
            self.assertFalse(os.path.exists(self.store.job_out(jid)))
        self.assertTrue(os.path.exists(self.store.job_out(other["id"])))


class InfraFailureTest(QueueTestCase):
    def test_classification(self):
        self.assertTrue(bq.infra_failure("local-build.sh exit 2", "line 571: syntax error near unexpected token `)'"))
        self.assertTrue(bq.infra_failure("runner exited without a status", ""))
        self.assertTrue(bq.infra_failure("windows build failed", "urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]"))
        self.assertTrue(bq.infra_failure("start: ssh hst5 rc=255: Connection timed out", ""))
        self.assertFalse(bq.infra_failure("local-build.sh exit 2", "make: *** [Makefile:312: build] Error 2"))
        self.assertFalse(bq.infra_failure("windows build failed", "notebookbar.ui ... button-no-label"))

    def test_infra_failure_is_requeued_twice_then_fails(self):
        job, _ = self.submit()
        linux = FakeRunner(["1"])
        runners = {"linux": linux, "windows": FakeRunner([])}
        Path(job["log"]).write_text("local-build.sh: line 571: syntax error near unexpected token `)'\n")
        bqd.tick(self.store, runners, bq)
        for attempt in (1, 2):
            linux.results[job["id"]] = ("failed", {"error": "local-build.sh exit 2"})
            bqd.tick(self.store, runners, bq)   # requeued and, the slot being free, started again at once
            state = self.store.load(job["id"])
            self.assertEqual((state["state"], state["infra_retries"]), ("running", attempt))
        self.assertEqual(linux.started, [job["id"]] * 3)
        linux.results[job["id"]] = ("failed", {"error": "local-build.sh exit 2"})
        bqd.tick(self.store, runners, bq)
        self.assertEqual(self.store.load(job["id"])["state"], "failed")

    def test_build_failure_is_not_requeued(self):
        job, _ = self.submit()
        linux = FakeRunner(["1"])
        runners = {"linux": linux, "windows": FakeRunner([])}
        Path(job["log"]).write_text("make: *** [Makefile:312: build] Error 2\n")
        bqd.tick(self.store, runners, bq)
        linux.results[job["id"]] = ("failed", {"error": "local-build.sh exit 2"})
        bqd.tick(self.store, runners, bq)
        self.assertEqual(self.store.load(job["id"])["state"], "failed")


class FakeRunner:
    def __init__(self, slots):
        self.slots = list(slots)
        self.started = []
        self.results = {}
        self.cancelled = []

    def want(self, job):
        return 8 if job["modules"] else 20

    def free_slot(self, jobs, want=None):
        running = {j.get("slot") for j in jobs if j["state"] == "running"}
        for s in self.slots:
            if s not in running:
                return s
        return None

    def start(self, job, slot):
        if slot == "broken":
            raise RuntimeError("cannot start")
        self.started.append(job["id"])
        return {"slot": slot, "host": "fake"}

    def check(self, job):
        return self.results.pop(job["id"], None)

    def cancel(self, job):
        self.cancelled.append(job["id"])


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
