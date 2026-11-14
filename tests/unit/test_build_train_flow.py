# SPDX-License-Identifier: AGPL-3.0-only
"""Build train flow (scripts/build_infra/queue_train_tick.py + queue_train_ops.py) on a scratch origin, with the
build results written by the test: pass, patch attribution with carry-over, two-round bisect, retries without
blame, merge conflicts, a broken base, removal, restart idempotency and the deletion of old train branches."""
import io
import os
from pathlib import Path
import tempfile

from build_queue_fixtures import QueueTestCase, bq
from build_train_fixtures import BASE, GitWorld
from build_infra.queue_git import Git
from build_infra import queue_train_ops as ops
from build_infra.queue_train_git import TrainRepo
from build_infra.queue_train_store import TrainStore
from build_infra.queue_train_tick import TrainStep

T0 = 1_800_000_000


class TrainFlowTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.world = GitWorld(tmp.name)
        self.repo = TrainRepo(os.path.join(tmp.name, "train-repo"), source=str(self.world.clone),
                              remote_url=str(self.world.origin))
        self.qgit = Git(str(self.world.clone))
        self.ts = TrainStore(self.store)
        self.cfg = dict(bq.DEFAULT_CONFIG)
        self.now = T0
        self.logs = []

    def add(self, *names, platform="both"):
        for name in names:
            self.qgit.run("fetch", "-q", "origin")
            ops.add(self.store, name, platform, resolver=self.qgit.rev, git=self.qgit, submitter="t", now=self.now)

    def step(self, minutes=1):
        self.now += minutes * 60
        TrainStep(self.store, bq, self.cfg, self.repo, self.now, log=self.logs.append).run()

    def train(self, n):
        return self.ts.load(n)

    def cand(self, name):
        return self.ts.branches()[name]

    def finish(self, job_id, state="done", log="", error="local-build.sh exit 2"):
        job = self.store.load(job_id)
        Path(job["log"]).write_text(log)
        fields = {"state": state, "finished": self.now}
        if state == "done":
            out = self.store.job_out(job_id)
            os.makedirs(out, exist_ok=True)
            Path(out, "HSTOffice.pkg").write_text("x")
            fields["output"] = [os.path.join(out, "HSTOffice.pkg")]
        else:
            fields["error"] = error
        self.store.update(job_id, **fields)

    def members(self, n):
        return [m["branch"] for m in self.train(n)["members"]]

    # ------------------------------------------------------------------
    def test_validation_of_add(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        for bad, why in (("rc/1.0.2-batch9", "cannot ride"), ("train/1.0.2-001", "cannot ride"),
                         ("fix/none", "unknown ref|not on origin")):
            with self.assertRaisesRegex(bq.QueueError, why):
                self.add(bad)
        self.world.branch(BASE, {"scripts/y.py": "y\n"}, base="fix/a")   # fix/a becomes part of the base
        with self.assertRaisesRegex(bq.QueueError, "already merged"):
            self.add("fix/a")

    def test_train_starts_at_four_branches_and_passes(self):
        for i, name in enumerate("abcd"):
            self.world.member(f"fix/{name}", f"hst-{name}.patch", f"sw/{name}.cxx")
        self.add("fix/a", "fix/b", "fix/c")
        self.add("fix/d", platform="linux")
        self.step()
        rec = self.train(1)
        self.assertEqual((rec["name"], rec["state"]), ("train/1.0.2-001", "building"))
        self.assertEqual(self.members(1), ["fix/a", "fix/b", "fix/c", "fix/d"])
        self.assertIn("train/1.0.2-001", self.world.remote_heads())
        jobs = rec["jobs"]
        self.assertEqual(sorted(jobs), ["linux", "windows"])
        job = self.store.load(jobs["linux"])
        self.assertEqual((job["sha"], job["priority"], job["train"]), (rec["sha"], 70, "train/1.0.2-001"))
        self.assertEqual(self.cand("fix/a")["state"], "in-train")
        with self.assertRaisesRegex(bq.QueueError, "in train/1.0.2-001"):
            self.add("fix/a")
        self.step()
        self.assertEqual(self.train(1)["state"], "building")   # builds still running: nothing changes
        for jid in jobs.values():
            self.finish(jid)
        self.step()
        self.assertEqual(self.train(1)["state"], "passed")
        cand = self.cand("fix/d")
        self.assertEqual((cand["state"], cand["result"]["jobs"]), ("passed", jobs))
        out = io.StringIO()
        self.assertEqual(ops.wait(self.store, "fix/d", out=out), 0)
        self.assertIn("HSTOffice.pkg", out.getvalue())
        self.step()
        self.assertEqual(len(self.ts.trains()), 1)   # no new train without ready branches

    def test_interval_and_restart_idempotency(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        self.step(30)
        self.assertEqual(self.ts.trains(), [])
        self.step(61)                                  # the oldest ready branch waited 90 minutes
        rec = self.train(1)
        self.assertEqual(rec["platforms"], ["linux"])
        # A crash after the push: the record goes back to "merging"; the redo gives the same commit and job.
        rec.update(state="merging", jobs={}, sha=rec["sha"])
        self.ts.save(rec)
        jobs_before = len(self.store.all())
        self.step()
        again = self.train(1)
        self.assertEqual((again["state"], again["sha"]), ("building", rec["sha"]))
        self.assertEqual(len(self.store.all()), jobs_before)   # deduplicated: same commit, same job

    def test_patch_failure_ejects_the_owner_and_the_others_ride_the_next_train(self):
        for name in "abc":
            self.world.member(f"fix/{name}", f"hst-{name}.patch", f"sw/{name}.cxx")
        self.add("fix/a", "fix/b", "fix/c")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.finish(rec["jobs"]["windows"])
        self.finish(rec["jobs"]["linux"], "failed", "applied: hst-a.patch\ndoes not apply: hst-b.patch\n")
        self.step()
        rec = self.train(1)
        self.assertEqual((rec["state"], rec["attribution"]["method"], rec["attribution"]["blamed"]),
                         ("failed", "patch", ["fix/b"]))
        b = self.cand("fix/b")
        self.assertEqual(b["state"], "ejected")
        confirm = self.store.load(b["confirm"]["linux"])
        self.assertEqual((confirm["label"], confirm["sha"], confirm["priority"]), ("fix_b", rec["members"][1]["sha"], 40))
        self.assertEqual(list(b["confirm"]), ["linux"])
        # fix/a and fix/c were carried: the next train starts at once with them.
        self.assertEqual(self.train(2)["state"], "building")
        self.assertEqual(self.members(2), ["fix/a", "fix/c"])
        self.assertEqual(self.cand("fix/a")["attempts"], 0)   # carried, not blamed: no attempt used up
        out = io.StringIO()
        self.assertEqual(ops.wait(self.store, "fix/b", out=out), 1)
        self.assertIn("ejected from train/1.0.2-001", out.getvalue())

    def test_halves_that_pass_alone_report_an_interaction_not_a_pass(self):
        for name in "ab":
            self.world.member(f"fix/{name}", f"hst-{name}.patch", f"sw/{name}.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        self.finish(self.train(1)["jobs"]["linux"], "failed", "make: *** [Makefile:312: build] Error 2\n")
        self.step()
        self.finish(self.train(2)["jobs"]["linux"])
        self.finish(self.train(3)["jobs"]["linux"])
        self.step()
        for name in ("fix/a", "fix/b"):
            self.assertEqual(self.cand(name)["state"], "ejected")
            self.assertIn("interaction", self.cand(name)["note"])
        self.assertEqual(self.train(1)["attribution"]["blamed"], [])

    def test_crash_recovery_never_double_counts_and_frees_stuck_candidates(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/b.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.finish(rec["jobs"]["linux"], "cancelled")
        self.step()
        self.assertEqual(self.cand("fix/a")["attempts"], 1)
        # The record is evaluated again (as if the tick had died before saving it): nothing is counted twice.
        rec = self.train(1)
        rec["state"] = "building"
        self.ts.save(rec)
        self.step()
        self.assertEqual([c["attempts"] for c in self.ts.branches().values()], [1, 1])
        # A candidate left in-train by a crash, with its train already over, goes back to ready.
        branches = self.ts.branches()
        branches["fix/a"].update(state="in-train", train="train/1.0.2-001")
        self.ts.save_branches(branches)
        self.step()   # train 2 (the carry-overs) is still building: fix/a waits as a carry-over, nothing counted
        cand = self.cand("fix/a")
        self.assertEqual((cand["state"], cand["carry"], cand["attempts"]), ("ready", True, 1))
        self.assertIn("ended without a result", cand["note"])

    def test_confirmation_build_survives_the_agents_next_submit_and_results_are_protected(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.finish(rec["jobs"]["linux"], "failed", "does not apply: hst-a.patch\n")
        self.step()
        confirm = self.cand("fix/a")["confirm"]["linux"]
        self.assertEqual(self.store.load(confirm)["confirm_for"], "train/1.0.2-001")
        self.shas["fix/a"] = "c" * 40
        bq.submit(self.store, "linux", "fix/a", resolver=lambda r: "c" * 40, git=self.git, submitter="t",
                  err=io.StringIO())
        self.assertEqual(self.store.load(confirm)["state"], "queued")
        self.assertTrue({confirm, rec["jobs"]["linux"]} <= self.ts.protected_jobs())

    def test_a_branch_git_cannot_compare_fails_alone(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.orphan("fix/orphan")
        self.add("fix/a", platform="linux")
        self.qgit.run("fetch", "-q", "origin")
        ops.add(self.store, "fix/orphan", "linux", resolver=self.qgit.rev, git=self.qgit, now=self.now)
        ops.start(self.store)
        self.step()
        self.assertEqual(self.members(1), ["fix/a"])
        self.assertEqual(self.cand("fix/orphan")["state"], "failed")
        self.assertIn("git cannot compare", self.cand("fix/orphan")["note"])

    def test_two_round_bisect_finds_the_branch(self):
        for name in "abcd":
            self.world.member(f"fix/{name}", f"hst-{name}.patch", f"sw/{name}.cxx")
        self.add("fix/a", "fix/b", "fix/c", "fix/d")
        self.step()
        top = self.train(1)
        unknown = "undefined reference to `Foo::bar()'\nmake: *** [Makefile:312: build] Error 2\n"
        self.finish(top["jobs"]["windows"])
        self.finish(top["jobs"]["linux"], "failed", unknown)
        self.step()
        self.assertEqual(self.train(1)["state"], "bisecting")
        self.assertEqual((self.members(2), self.members(3)), (["fix/a", "fix/b"], ["fix/c", "fix/d"]))
        self.assertEqual(sorted(self.train(2)["jobs"]), ["linux"])   # only the failing platform
        self.finish(self.train(2)["jobs"]["linux"])
        self.finish(self.train(3)["jobs"]["linux"], "failed", unknown)
        self.step()
        self.assertEqual(self.cand("fix/a")["state"], "passed")
        self.assertEqual(self.cand("fix/a")["result"]["jobs"], {"linux": self.train(2)["jobs"]["linux"],
                                                                  "windows": top["jobs"]["windows"]})
        self.assertEqual((self.members(4), self.members(5)), (["fix/c"], ["fix/d"]))
        self.assertEqual(self.train(4)["round"], 2)
        self.finish(self.train(4)["jobs"]["linux"])
        self.finish(self.train(5)["jobs"]["linux"], "failed", unknown)
        self.step()
        self.assertEqual(self.train(5)["attribution"]["method"], "single")
        self.assertEqual(self.cand("fix/d")["state"], "ejected")
        self.assertEqual(self.cand("fix/c")["state"], "passed")
        self.step()   # the parents close once their halves are decided
        self.assertEqual(self.train(3)["attribution"]["blamed"], ["fix/d"])
        self.assertEqual((self.train(1)["state"], self.train(1)["attribution"]["blamed"]), ("failed", ["fix/d"]))

    def test_cancelled_or_infra_failure_retries_without_blame_then_gives_up(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        for attempt in range(1, 4):
            ops.start(self.store)
            self.step()
            rec = self.ts.trains()[-1]
            self.finish(rec["jobs"]["linux"], "cancelled" if attempt == 1 else "failed",
                        "ssh hst5 rc=255: Connection timed out\n", error="runner exited without a status")
            self.step()
            self.assertEqual(self.ts.trains()[-2 if attempt < 3 else -1]["state"], "error")
        self.assertEqual(self.cand("fix/a")["state"], "failed")
        self.assertIn("gave up after 3 trains", self.cand("fix/a")["note"])

    def test_merge_conflicts(self):
        self.world.branch("fix/c1", {"scripts/x.py": "x = 3\n"})
        self.world.branch("fix/c2", {"scripts/x.py": "x = 4\n"})
        self.world.branch("fix/stale", {"docs/a.md": "stale\n", "scripts/z.py": "z\n"})
        self.world.branch(BASE, {"docs/a.md": "new base\n"}, base=BASE)
        self.add("fix/c1", "fix/c2", "fix/stale")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.assertEqual(self.members(1), ["fix/c1"])
        self.assertEqual(sorted(rec["conflicts"]), ["fix/c2", "fix/stale"])
        self.assertEqual(self.cand("fix/stale")["state"], "ejected")
        self.assertIn("merge conflict with rc/1.0.2-batch5", self.cand("fix/stale")["note"])
        self.assertNotIn("confirm", self.cand("fix/stale"))
        self.assertEqual((self.cand("fix/c2")["state"], self.cand("fix/c2")["carry"]), ("ready", True))

    def test_broken_base_blames_nobody_and_overlapping_branches_wait(self):
        self.world.member("fix/a", "hst-a.patch", "sw/same.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/same.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.assertEqual(self.members(1), ["fix/a"])
        self.assertIn("same LibreOffice files as fix/a", rec["deferred"]["fix/b"])
        base_job, _ = bq.submit(self.store, "linux", BASE, resolver=lambda r: rec["base_sha"], git=self.git,
                                submitter="t")
        self.finish(base_job["id"], "failed", "make: *** [Makefile:312: build] Error 2\n")
        self.finish(rec["jobs"]["linux"], "failed", "make: *** [Makefile:312: build] Error 2\n")
        self.step()
        self.assertEqual(self.train(1)["state"], "error")
        self.assertEqual((self.cand("fix/a")["state"], self.cand("fix/a")["attempts"]), ("ready", 0))
        self.assertIn("fails to build", self.cand("fix/a")["note"])
        ops.start(self.store)
        self.step(100)
        self.assertEqual(len(self.ts.trains()), 1)          # held: the base has not moved
        self.world.branch(BASE, {"scripts/fix.py": "ok\n"}, base=BASE)
        self.step()
        self.assertEqual(self.train(2)["state"], "building")   # a new base commit: trains resume

    def test_remove_and_old_train_branches_are_deleted(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/b.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        ops.remove(self.store, "fix/b")
        self.assertTrue(self.cand("fix/b")["removed"])
        self.finish(self.train(1)["jobs"]["linux"])
        self.step()
        self.assertNotIn("fix/b", self.ts.branches())
        self.assertIn("train/1.0.2-001", self.world.remote_heads())
        self.step(47 * 60)
        self.assertIn("train/1.0.2-001", self.world.remote_heads())
        self.step(2 * 60)
        self.assertNotIn("train/1.0.2-001", self.world.remote_heads())
        self.assertTrue({BASE, "fix/a", "fix/b"} <= self.world.remote_heads())
        self.assertTrue(self.train(1)["ref_deleted"])
        with self.assertRaises(bq.QueueError):
            ops.remove(self.store, "fix/none")
