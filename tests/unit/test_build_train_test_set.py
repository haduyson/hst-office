# SPDX-License-Identifier: AGPL-3.0-only
"""The build train's test set (scripts/build_infra/queue_train_judge.py, queue_train_tick.py): the Linux build of a
train runs train_tests plus the tests members declared and still packages; a branch passes only when builds and
tests pass; failing tests run on the base first and a target failing there too is never blamed; a new failure is
blamed by the assertion's file, else by single/bisect; numbers count per train_prefix next to old records."""
import io
import json
import os

from test_build_train_flow import TrainFlowCase   # first: its fixtures put scripts/ on sys.path
from build_infra import queue_train_ops as ops  # noqa: E402
from build_infra.queue_train_store import write_json  # noqa: E402
from build_infra import queue_train_cli as train_cli  # noqa: E402

SMOKE = "CppunitTest_sw_smoke"


class TrainTestSetTest(TrainFlowCase):
    def setUp(self):
        super().setUp()
        self.cfg["train_tests"] = [SMOKE]

    def baseline(self, n, field="baseline"):
        """The run of the failing targets on the base ("baseline") or again on the train commit ("reruns")."""
        rec = self.train(n)
        self.assertEqual(len(rec.get(field, {})), 1, rec.get("events"))
        return self.store.load(next(iter(rec[field].values())))

    def rerun(self, n):
        return self.baseline(n, "reruns")

    def test_linux_build_runs_the_fixed_and_declared_tests_and_still_packages(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sc/b.cxx")
        self.add("fix/a", tests=["CppunitTest_sw_a"])
        self.add("fix/b", platform="windows", tests=[SMOKE])
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.assertEqual(rec["tests"], [SMOKE, "CppunitTest_sw_a"])
        linux, windows = (self.store.load(rec["jobs"][p]) for p in ("linux", "windows"))
        self.assertEqual((linux["tests"], linux["package"]), ([SMOKE, "CppunitTest_sw_a"], True))
        self.assertEqual((windows["tests"], windows["package"]), ([], True))
        for jid in rec["jobs"].values():
            self.finish(jid)
        self.step()
        self.assertEqual(self.train(1)["state"], "passed")
        self.assertIn("2 of 2 tests passed", self.cand("fix/a")["note"])

    def test_a_windows_only_train_still_runs_the_tests_on_linux(self):
        self.world.member("fix/w", "hst-w.patch", "vcl/win/w.cxx")
        self.add("fix/w", platform="windows")
        ops.start(self.store)
        self.step()
        self.assertEqual(sorted(self.train(1)["jobs"]), ["linux", "windows"])

    def test_a_test_that_fails_on_the_base_too_is_reported_but_not_blamed(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.finish(rec["jobs"]["linux"], failing={SMOKE: "sw/qa/x.cxx:1:Assertion\n"})
        self.step()
        self.assertEqual(self.train(1)["state"], "building")   # waits for the base run of the failing target
        base = self.baseline(1)
        self.assertEqual((base["sha"], base["tests"], base["package"]), (rec["base_sha"], [SMOKE], False))
        self.step()
        self.assertEqual(self.baseline(1)["id"], base["id"])   # submitted once
        rerun = self.rerun(1)
        self.assertEqual((rerun["sha"], rerun["tests"], rerun["package"]), (rec["sha"], [SMOKE], False))
        self.finish(base["id"], failing={SMOKE: "sw/qa/x.cxx:1:Assertion\n"})
        self.finish(rerun["id"], failing={SMOKE: "sw/qa/x.cxx:1:Assertion\n"})
        self.step()
        rec = self.train(1)
        self.assertEqual((rec["state"], rec["base_test_failures"]), ("passed", [SMOKE]))
        self.assertIn("0 of 1 tests passed (1 failing on the base too, not counted)", self.cand("fix/a")["note"])

    def test_a_new_failure_is_blamed_on_the_branch_that_touches_the_asserting_file(self):
        self.world.member("fix/a", "hst-a.patch", "sw/qa/core/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/source/b.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        log = ("warn:sw.core:1:1:/data/hst-office-build/src/lo/sw/source/b.cxx:10: error: noisy SAL_WARN\n"
               "/data/hst-office-build/src/lo/sw/qa/core/a.cxx:42:Assertion\nTest name: A::test\n")
        self.finish(self.train(1)["jobs"]["linux"], failing={SMOKE: log})
        self.step()
        self.finish(self.baseline(1)["id"])   # passes on the base: the train broke it
        self.finish(self.rerun(1)["id"], failing={SMOKE: log})   # and fails again: not flaky
        self.step()
        rec = self.train(1)
        self.assertEqual((rec["state"], rec["attribution"]["method"], rec["attribution"]["blamed"]),
                         ("failed", "test", ["fix/a"]))
        self.assertEqual(rec["test_failures"], {"linux": [SMOKE]})
        confirm = self.store.load(self.cand("fix/a")["confirm"]["linux"])
        self.assertEqual((confirm["tests"], confirm["sha"]), ([SMOKE], rec["members"][0]["sha"]))
        self.assertEqual(self.members(2), ["fix/b"])   # carried, not blamed: it rides the next train at once

    def test_an_unattributed_test_failure_bisects_and_the_halves_run_the_tests(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/b.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        self.finish(self.train(1)["jobs"]["linux"], failing={SMOKE: "Test name: A::test\nequality failed\n"})
        self.step()
        base = self.baseline(1)
        self.finish(base["id"])
        self.finish(self.rerun(1)["id"], failing={SMOKE: "equality failed\n"})
        self.step()
        self.assertEqual(self.train(1)["state"], "bisecting")
        for n in (2, 3):
            self.assertEqual(self.store.load(self.train(n)["jobs"]["linux"])["tests"], [SMOKE])
        self.finish(self.train(2)["jobs"]["linux"])
        self.finish(self.train(3)["jobs"]["linux"], failing={SMOKE: "equality failed\n"})
        self.step()
        self.assertEqual(self.baseline(3)["id"], base["id"])   # the base run is shared
        self.finish(self.rerun(3)["id"], failing={SMOKE: "equality failed\n"})
        self.step()
        self.assertEqual((self.cand("fix/a")["state"], self.cand("fix/b")["state"]), ("passed", "ejected"))
        self.assertEqual(self.train(3)["attribution"]["method"], "single")

    def test_a_test_that_passes_when_run_again_is_flaky_and_never_blamed_or_bisected(self):
        self.world.member("fix/a", "hst-a.patch", "sw/qa/core/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sw/b.cxx")
        self.add("fix/a", "fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        log = "/data/hst-office-build/src/lo/sw/qa/core/a.cxx:42:Assertion\n"
        self.finish(self.train(1)["jobs"]["linux"], failing={SMOKE: log})
        self.step()
        self.assertEqual(self.train(1)["state"], "building")   # both runs of the failing target are queued
        self.finish(self.baseline(1)["id"])
        self.step()
        self.assertEqual(self.train(1)["state"], "building")   # the base passed; the rerun is still running
        self.assertIn(self.rerun(1)["id"], self.ts.protected_jobs())   # retention keeps it while the train decides
        self.finish(self.rerun(1)["id"])                        # passes the second time
        self.step()
        rec = self.train(1)
        self.assertEqual((rec["state"], rec["flaky_tests"]), ("passed", [SMOKE]))
        self.assertNotIn("attribution", rec)
        self.assertEqual(len(self.ts.trains()), 1)              # no bisect halves
        self.assertIn(f"1 passed only when run again: {SMOKE}", self.cand("fix/a")["note"])
        out = io.StringIO()
        self.assertEqual(ops.wait(self.store, "fix/a", out=out), 0)
        self.assertIn(f"FLAKY    train/1.0.2-001: {SMOKE} failed once", out.getvalue())   # never silent
        for what in ("fix/b", "train/1.0.2-001", None):
            out = io.StringIO()
            train_cli.status(self.store, what, False, out)
            self.assertIn("FLAKY", out.getvalue(), what)

    def test_a_base_run_that_cannot_finish_blames_nobody(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        ops.start(self.store)
        self.step()
        self.finish(self.train(1)["jobs"]["linux"], failing={SMOKE: ""})
        self.step()
        self.finish(self.baseline(1)["id"], "cancelled")
        self.step()
        self.assertEqual(self.train(1)["state"], "error")
        cand = self.cand("fix/a")
        self.assertIn(cand["state"], ("ready", "in-train"))   # retried: maybe already in the next train
        self.assertEqual(cand["attempts"], 1)

    def test_train_add_refuses_a_patch_that_would_land_at_the_source_root(self):
        bare = ("diff --git sw/CppunitTest_sw_x.mk sw/CppunitTest_sw_x.mk\n--- /dev/null\n+++ sw/CppunitTest_sw_x.mk\n"
                "@@ -0,0 +1 @@\n+x\n")
        self.world.branch("fix/bare", {"patches/libreoffice/hst-bare.patch": bare},
                          append={"patches/libreoffice/series": "hst-bare.patch"})
        with self.assertRaisesRegex(ops.QueueError, r"(?s)patch lint failed.*hst-bare\.patch:1: "):
            self.add("fix/bare")
        self.assertNotIn("fix/bare", self.ts.branches())

    def test_a_new_prefix_numbers_from_001_next_to_the_old_records(self):
        self.ts.ensure()
        old = {"number": 1, "name": "train/1.0.2-001", "kind": "train", "state": "passed", "created": 1,
               "members": [], "jobs": {}}
        write_json(os.path.join(self.ts.trains_dir, "001.json"), old)
        self.cfg["train_prefix"] = "train/1.0.3-"
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.add("fix/a", platform="linux")
        ops.start(self.store)
        self.step()
        rec = self.train(1)
        self.assertEqual(rec["name"], "train/1.0.3-001")
        self.assertIn("train/1.0.3-001", self.world.remote_heads())
        self.assertTrue(os.path.isfile(os.path.join(self.ts.trains_dir, "train_1.0.3-001.json")))
        with open(os.path.join(self.ts.trains_dir, "001.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), old)
        self.assertEqual(self.ts.load("train/1.0.2-001")["state"], "passed")
        self.assertEqual([r["name"] for r in self.ts.trains()], ["train/1.0.2-001", "train/1.0.3-001"])
        old["ref_deleted"] = True
        self.ts.save(old)   # an old record is rewritten in place, never duplicated
        self.assertEqual(sorted(os.listdir(self.ts.trains_dir)), ["001.json", "train_1.0.3-001.json"])
        self.finish(rec["jobs"]["linux"])
        self.step()
        self.world.member("fix/b", "hst-b.patch", "sw/b.cxx")
        self.add("fix/b", platform="linux")
        ops.start(self.store)
        self.step()
        self.assertEqual(self.train(2)["name"], "train/1.0.3-002")
