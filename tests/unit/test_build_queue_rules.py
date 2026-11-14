# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue rules for agents: retention of failed/merged/old outputs with pins and active-train protection,
superseding a branch's queued job, refusing tests/docs-only commits (--force for the integrator) and the
priority cap (scripts/build_infra/queue_rules.py, queue_ops.py, queue_retention.py)."""
import io
import os
import time
import unittest

from build_queue_fixtures import SHA_A, SHA_B, QueueTestCase, bq

HOUR = 3600


class RetentionRulesTest(QueueTestCase):
    def cfg(self, **kw):
        return dict(bq.DEFAULT_CONFIG, **kw)

    def build(self, ref, sha, state="done", finished=None, platform="linux", **fields):
        self.shas[ref] = sha
        job, _ = self.submit(platform=platform, ref=ref)
        job = self.finish(job, finished=finished or time.time() - 100 * HOUR)
        return self.store.update(job["id"], state=state, **fields)

    def deleted(self):
        return {j["id"]: j.get("output_deleted_reason") for j in self.store.all() if j.get("output_deleted")}

    def retain(self, now=None, protected=frozenset(), **cfg):
        return bq.apply_retention(self.store, self.cfg(**cfg), now=now, git=self.git, protected=protected)

    def test_failed_cancelled_invalidated_go_after_the_grace_period(self):
        old = self.build("feat/a", "1" * 40, state="failed", error="local-build.sh exit 2")
        inv = self.build("feat/b", "2" * 40, state="failed", error="invalidated: stale mo")
        can = self.build("feat/c", "3" * 40, state="cancelled")
        fresh = self.build("feat/d", "4" * 40, state="failed", finished=time.time() - HOUR)
        freed = self.retain()
        self.assertEqual(self.deleted(), {old["id"]: "failed", inv["id"]: "invalidated", can["id"]: "cancelled"})
        self.assertNotIn(fresh["id"], self.deleted())
        self.assertFalse(os.path.exists(self.store.job_out(old["id"])))
        self.assertEqual(sum(f[2] for f in freed), 3)   # one 1-byte file per job

    def test_keeps_two_per_branch_three_train_builds_and_pinned_or_protected(self):
        ids = [self.build("feat/a", f"{i:040d}", finished=1000 + i)["id"] for i in range(4)]
        trains = [self.build(f"train/1.0.2-00{i}", f"{i + 5:040d}", finished=1000 + i, train=f"train/1.0.2-00{i}")["id"]
                  for i in range(5)]
        bq.pin(self.store, ids[0], "baseline for a regression hunt")
        self.retain(protected={trains[0]})
        self.assertEqual(set(self.deleted()), {ids[1], trains[1]})
        with self.assertRaises(bq.QueueError):
            bq.pin(self.store, ids[1], "already deleted")
        bq.pin(self.store, ids[0], None)
        self.retain(protected=set())
        self.assertIn(ids[0], self.deleted())

    def test_merged_branch_builds_go_but_integration_builds_stay(self):
        tip = "f" * 40
        self.git.tips["rc/1.0.2-batch5"] = tip
        merged = self.build("feat/merged", "1" * 40)
        recent = self.build("feat/merged2", "2" * 40, finished=time.time() - HOUR)
        live = self.build("feat/live", "3" * 40)
        batch = self.build("rc/1.0.2-batch4", "4" * 40)
        for sha in ("1" * 40, "2" * 40, "4" * 40):
            self.git.ancestors.add((sha, tip))
        self.retain()
        self.assertEqual(self.deleted(), {merged["id"]: "merged into rc/1.0.2-batch5"})
        for job in (recent, live, batch):
            self.assertNotIn(job["id"], self.deleted())


class SubmitRulesTest(QueueTestCase):
    def test_priority_is_capped_for_agents_but_not_the_integrator(self):
        err = io.StringIO()
        job, _ = self.submit(ref="feat/x", priority=95, err=err)
        self.assertEqual(job["priority"], 50)
        self.assertIn("capped at 50", err.getvalue())
        batch, _ = self.submit(ref="rc/1.0.2-batch5", priority=99)
        self.assertEqual((batch["priority"], batch["integrator"]), (99, True))
        self.shas["feat/y"] = "c" * 40
        flagged, _ = self.submit(ref="feat/y", priority=99, integrator=True)
        self.assertEqual(flagged["priority"], 99)

    def test_newer_commit_cancels_the_queued_job_of_the_same_branch_platform_and_kind(self):
        first, _ = self.submit(ref="feat/x")
        win, _ = self.submit(ref="feat/x", platform="windows")
        mods, _ = self.submit(ref="feat/x", modules=["sc"])
        self.shas["feat/x"] = "c" * 40
        running, _ = self.submit(ref="feat/x", platform="windows")   # cancels win (queued)
        self.store.update(running["id"], state="running")
        err = io.StringIO()
        newer, _ = self.submit(ref="feat/x", err=err)
        old = self.store.load(first["id"])
        self.assertEqual((old["state"], old["superseded_by"]), ("cancelled", newer["id"]))
        self.assertIn(first["id"], err.getvalue())
        self.assertEqual(self.store.load(win["id"])["state"], "cancelled")
        self.assertEqual(self.store.load(mods["id"])["state"], "queued")          # another kind
        self.shas["feat/x"] = "d" * 40
        self.submit(ref="feat/x", platform="windows")
        self.assertEqual(self.store.load(running["id"])["state"], "running")      # never a running job
        self.submit(ref=SHA_A[:12])                                               # bare sha: label "commit"
        self.assertEqual(self.store.load(newer["id"])["state"], "queued")

    def test_tests_or_docs_only_commit_is_refused_against_the_last_build(self):
        built, _ = self.submit(ref="feat/x")
        self.finish(built)
        self.shas["feat/x"] = "c" * 40
        self.git.changes[(SHA_B, "c" * 40)] = ["tests/unit/test_a.py", "docs/X.md", "plans/p.md", "README.md"]
        with self.assertRaisesRegex(bq.QueueError, f"only changes tests/.*{built['id']}"):
            self.submit(ref="feat/x")
        with self.assertRaisesRegex(bq.QueueError, "reserved for the integrator"):
            self.submit(ref="feat/x", force=True)
        forced, _ = self.submit(ref="feat/x", force=True, integrator=True)
        self.assertTrue(forced["forced"])
        self.shas["feat/x"] = "d" * 40
        self.git.changes[(SHA_B, "d" * 40)] = ["docs/X.md", "patches/libreoffice/hst-a.patch"]
        self.assertFalse(self.submit(ref="feat/x")[1])   # touches a patch: builds

    def test_without_a_build_the_merge_base_with_the_integration_branch_is_the_baseline(self):
        self.git.tips["rc/1.0.2-batch5"] = "f" * 40
        self.git.bases[("f" * 40, SHA_B)] = "e" * 40
        self.git.changes[("e" * 40, SHA_B)] = ["tests/unit/test_only.py"]
        with self.assertRaisesRegex(bq.QueueError, "rc/1.0.2-batch5 build"):
            self.submit(ref="feat/x")
        self.git.changes[("e" * 40, SHA_B)] = None   # git could not tell: never blocks a submit
        self.assertFalse(self.submit(ref="feat/x")[1])

    def test_internal_train_jobs_skip_the_agent_rules(self):
        self.shas["train/1.0.2-001"] = "c" * 40
        job, _ = self.submit(ref="train/1.0.2-001", priority=70, internal=True, train="train/1.0.2-001")
        self.assertEqual((job["priority"], job["train"]), (70, "train/1.0.2-001"))


if __name__ == "__main__":
    unittest.main()
