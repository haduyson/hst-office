# SPDX-License-Identifier: AGPL-3.0-only
"""Local build queue: submit/dedupe/validation, cancel/wait, invalidate, retention and infrastructure-failure
requeue (scripts/build-queue.py)."""
import io
import os
from pathlib import Path
import unittest

from build_queue_fixtures import SHA_A, SHA_B, FakeRunner, QueueTestCase, bq, bqd


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


class InvalidateTest(QueueTestCase):
    def test_invalidated_output_is_not_reused(self):
        job, _ = self.submit(platform="windows")
        self.finish(job, files=("HSTOffice.msi",))
        self.assertEqual(self.submit(platform="windows")[0]["id"], job["id"])
        bq.invalidate(self.store, job["id"], "stale vi catalogues")
        state = self.store.load(job["id"])
        self.assertEqual(state["state"], "failed")
        self.assertIn("stale vi catalogues", state["error"])
        self.assertTrue(os.path.exists(state["output"][0]))   # kept for forensics
        fresh, dup = self.submit(platform="windows")
        self.assertFalse(dup)
        with self.assertRaises(bq.QueueError):
            bq.invalidate(self.store, fresh["id"], "queued jobs cannot be invalidated")
        with self.assertRaises(bq.QueueError):
            bq.invalidate(self.store, job["id"], " ")


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
        bq.apply_retention(self.store, dict(bq.DEFAULT_CONFIG, retention_per_branch=3), git=self.git, protected=set())
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
        self.assertTrue(bq.infra_failure("windows build failed", ": ERROR: ERROR: extracting MergeModule.CABinet failed "
                                         "using C:/WINDOWS/System32/expand.exe MergeModule.CABinet"))
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


if __name__ == "__main__":
    unittest.main()
