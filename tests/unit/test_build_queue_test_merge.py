# SPDX-License-Identifier: AGPL-3.0-only
"""Test runs of one commit share one build: a `submit --test` that matches a queued, not yet started test job of the
same commit, platform, package and modules joins it (union of the test lists); collapse_test_jobs folds jobs that
are already queued; `wait` on a folded job follows it; the dispatcher freezes a job's test list when it starts it
(scripts/build_infra/queue_ops.py, queue_rules.py, queue_report.py, dispatch_loop.py)."""
import io
import unittest

from build_queue_fixtures import QueueTestCase, FakeRunner, bq, bqd

SHA_C = "c" * 40


class RecordingRunner(FakeRunner):
    def __init__(self, slots):
        super().__init__(slots)
        self.started_jobs = []

    def start(self, job, slot):
        self.started_jobs.append(job)
        return super().start(job, slot)


class TestJoinTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.shas["commit"] = SHA_C

    def run_tests(self, tests, modules=(), priority=None, ref="commit"):
        return self.submit(ref=ref, tests=tests, modules=modules, priority=priority, err=io.StringIO())

    def test_a_second_test_list_of_the_same_commit_joins_the_queued_job(self):
        first, dup = self.run_tests(["CppunitTest_sc_ucalc", "CppunitTest_sc_a"], modules=["sc"])
        self.assertFalse(dup)
        second, dup = self.run_tests(["CppunitTest_sc_a", "CppunitTest_sc_b"], modules=["sc"], priority=20)
        self.assertTrue(dup)
        self.assertEqual(second["id"], first["id"])
        job = self.store.load(first["id"])
        self.assertEqual(job["tests"], ["CppunitTest_sc_ucalc", "CppunitTest_sc_a", "CppunitTest_sc_b"])
        self.assertEqual(job["priority"], 20)
        self.assertEqual(job["key"], bq.job_key("linux", SHA_C, False, ["sc"], job["tests"]))
        self.assertEqual(job["merged_tests"][0]["added"], ["CppunitTest_sc_b"])
        self.assertEqual(len(self.store.all()), 1)
        # The union is itself a duplicate key now: the same union submitted again is the same job.
        again, dup = self.run_tests(job["tests"], modules=["sc"])
        self.assertEqual((again["id"], dup), (first["id"], True))

    def test_other_modules_platform_commit_or_a_started_job_are_never_joined(self):
        base, _ = self.run_tests(["CppunitTest_sc_a"], modules=["sc"])
        other_modules, _ = self.run_tests(["CppunitTest_sc_b"], modules=["sc", "formula"])
        full_build, _ = self.run_tests(["CppunitTest_sc_c"])
        other_commit, _ = self.run_tests(["CppunitTest_sc_d"], modules=["sc"], ref="feat/x")
        self.assertEqual(len({base["id"], other_modules["id"], full_build["id"], other_commit["id"]}), 4)
        self.store.update(base["id"], starting=1.0)   # the dispatcher is starting it
        late, dup = self.run_tests(["CppunitTest_sc_e"], modules=["sc"])
        self.assertFalse(dup)
        self.assertNotEqual(late["id"], base["id"])
        self.assertEqual(self.store.load(base["id"])["tests"], ["CppunitTest_sc_a"])
        requeued, _ = self.run_tests(["CppunitTest_sc_f"], modules=["sw"])
        self.store.update(requeued["id"], infra_retries=1)
        separate, dup = self.run_tests(["CppunitTest_sc_g"], modules=["sw"])
        self.assertNotEqual(separate["id"], requeued["id"])

    def test_train_and_confirmation_jobs_are_never_joined_or_joining(self):
        train, _ = self.submit(ref="commit", tests=["CppunitTest_a"], internal=True, train="train/1.0.3-001")
        mine, dup = self.run_tests(["CppunitTest_b"])
        self.assertFalse(dup)
        self.assertNotEqual(mine["id"], train["id"])
        self.assertTrue(train["package"])   # the train's Linux build packages after its tests
        internal, _ = self.submit(ref="commit", tests=["CppunitTest_c"], internal=True, package=False)
        self.assertNotEqual(internal["id"], mine["id"])
        self.assertEqual(self.store.load(mine["id"])["tests"], ["CppunitTest_b"])

    def test_collapse_folds_queued_duplicates_and_wait_follows_them(self):
        self.store.ensure()
        jobs = [bq.new_id(0) for _ in range(3)]
        made = []
        lists = (["CppunitTest_a", "CppunitTest_b"], ["CppunitTest_c"], ["CppunitTest_b", "CppunitTest_d"])
        for i, tests in enumerate(lists):
            job = {"id": jobs[i], "platform": "linux", "ref": "8db343ae", "sha": SHA_C, "label": "commit",
                   "priority": i * 5, "package": False, "modules": ["sc"], "tests": tests,
                   "key": bq.job_key("linux", SHA_C, False, ["sc"], tests), "state": "queued", "submitted": 100 + i,
                   "submitted_at": "", "submitter": "agent", "output": [], "log": self.store.log_path(jobs[i])}
            self.store.save(job)
            made.append(job)
        running = dict(made[0], id=bq.new_id(0), state="running", submitted=50, tests=["CppunitTest_x"])
        self.store.save(running)
        out = io.StringIO()
        self.assertEqual(bq.collapse_test_jobs(self.store, dry_run=True, out=out), [(jobs[0], jobs[1:])])
        self.assertEqual(self.store.load(jobs[1])["state"], "queued")
        bq.collapse_test_jobs(self.store, out=out)
        kept = self.store.load(jobs[0])
        self.assertEqual(kept["tests"], ["CppunitTest_a", "CppunitTest_b", "CppunitTest_c", "CppunitTest_d"])
        self.assertEqual(kept["priority"], 10)
        for jid in jobs[1:]:
            folded = self.store.load(jid)
            self.assertEqual((folded["state"], folded["merged_into"]), ("cancelled", jobs[0]))
        self.assertEqual(self.store.load(running["id"])["tests"], ["CppunitTest_x"])
        self.store.update(jobs[0], state="done", test_results={
            t: {"result": "pass", "exit": 0, "seconds": 1, "log": f"test-logs/{t}.log"} for t in kept["tests"]})
        out = io.StringIO()
        self.assertEqual(bq.wait(self.store, jobs[2], out=out), 0)
        self.assertIn(f"merged into {jobs[0]}", out.getvalue())
        self.assertIn("PASS CppunitTest_d", out.getvalue())

    def test_the_dispatcher_starts_the_current_record_and_freezes_it(self):
        job, _ = self.run_tests(["CppunitTest_a"])
        linux, windows = RecordingRunner(["1"]), FakeRunner([])
        bqd.tick(self.store, {"linux": linux, "windows": windows}, bq)
        self.assertEqual(linux.started_jobs[0]["tests"], ["CppunitTest_a"])
        self.assertIn("starting", self.store.load(job["id"]))
        self.assertEqual(self.store.load(job["id"])["state"], "running")


if __name__ == "__main__":
    unittest.main()
