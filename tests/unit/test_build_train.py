# SPDX-License-Identifier: AGPL-3.0-only
"""Build train rules (scripts/build_infra/queue_train.py) and its git layer (queue_train_git.py) on a scratch
origin: start rule, member selection by LibreOffice files, job outcomes, failure attribution (patch, compile,
single, bisect), union merges of series/vi-overrides, conflicts, deterministic merges and the push/delete guards."""
import tempfile
import unittest

from build_queue_fixtures import bq  # loading the entry point puts scripts/ on sys.path
from build_train_fixtures import BASE, GitWorld, override
from build_infra import queue_train as qt  # noqa: E402
from build_infra import queue_train_git as qg  # noqa: E402

CFG = {"train_min_branches": 4, "train_interval_minutes": 20}


def cand(name, since=0, carry=False, files=()):
    return {"branch": name, "ready_since": since, "carry": carry, "lo_files": list(files)}


class StartAndSelectTest(unittest.TestCase):
    def test_start_rule(self):
        now = 10_000
        self.assertFalse(qt.should_start([], now, CFG, forced=True))
        self.assertFalse(qt.should_start([cand("a", now - 60)], now, CFG))
        self.assertTrue(qt.should_start([cand("a", now - 20 * 60)], now, CFG))
        self.assertTrue(qt.should_start([cand(c, now) for c in "abcd"], now, CFG))
        self.assertTrue(qt.should_start([cand("a", now, carry=True)], now, CFG))
        self.assertTrue(qt.should_start([cand("a", now)], now, CFG, forced=True))

    def test_order_and_lo_file_overlap(self):
        ready = sorted([cand("b", 5), cand("a", 9, carry=True), cand("c", 1)], key=qt.ready_order)
        self.assertEqual([c["branch"] for c in ready], ["a", "c", "b"])
        chosen, deferred = qt.select_members(
            [cand("a", files=["sw/x.cxx"]), cand("b", files=["sw/x.cxx", "sc/y.cxx"]), cand("c", files=["sc/y.cxx"]),
             cand("d"), cand("e")], 3)
        self.assertEqual([c["branch"] for c in chosen], ["a", "c", "d"])
        self.assertIn("same LibreOffice files as a: sw/x.cxx", deferred["b"])
        self.assertIn("train full", deferred["e"])

    def test_files_of_trains_in_flight_are_busy(self):
        trains = [{"name": "t/1", "state": "building", "kind": "train", "members": [{"lo_files": ["sw/x.cxx"]}]},
                  {"name": "t/2", "state": "bisecting", "kind": "train", "members": [{"lo_files": ["sc/y.cxx"]}]},
                  {"name": "t/3", "state": "building", "kind": "bisect", "parent": "t/2",
                   "members": [{"lo_files": ["sc/y.cxx"]}]},
                  {"name": "t/0", "state": "passed", "kind": "train", "members": [{"lo_files": ["sd/z.cxx"]}]}]
        busy = qt.in_flight_files(trains, ("merging", "building", "bisecting"))
        self.assertEqual(busy, {"sw/x.cxx": "t/1", "sc/y.cxx": "t/2"})
        chosen, deferred = qt.select_members(
            [cand("a", files=["sw/x.cxx"]), cand("b", files=["sd/z.cxx"]), cand("c", files=["sd/z.cxx"])], 8, busy)
        self.assertEqual([c["branch"] for c in chosen], ["b"])
        self.assertIn("same LibreOffice files as t/1, still building: sw/x.cxx", deferred["a"])
        self.assertIn("same LibreOffice files as b: sd/z.cxx", deferred["c"])
        old = [{"name": "t/9", "state": "building", "kind": "train", "members": [{"branch": "x"}]}]
        self.assertIsNone(qt.in_flight_files(old, ("building",)))   # no file list: nothing is provably disjoint


class OutcomeAndAttributionTest(unittest.TestCase):
    MEMBERS = [{"branch": "fix/a", "patches": ["hst-a.patch"], "lo_files": ["sw/source/core/a.cxx"]},
               {"branch": "fix/b", "patches": ["hst-b.patch"], "lo_files": ["xmlsecurity/uiconfig/ui/hstpdfviewer.ui"]},
               {"branch": "fix/c", "patches": ["hst-c.patch"], "lo_files": ["sc/source/ui/c.cxx"]}]

    def test_job_outcomes(self):
        infra = bq.infra_failure
        self.assertIsNone(qt.job_outcome({"state": "running"}, infra))
        self.assertEqual(qt.job_outcome({"state": "done"}, infra), "pass")
        self.assertEqual(qt.job_outcome({"state": "cancelled"}, infra), "error")
        self.assertEqual(qt.job_outcome(None, infra), "error")
        self.assertEqual(qt.job_outcome({"state": "failed", "error": "invalidated: x"}, infra), "error")
        self.assertEqual(qt.job_outcome({"state": "failed", "error": "runner exited without a status"}, infra), "error")
        self.assertEqual(qt.job_outcome({"state": "failed", "error": "local-build.sh exit 2"}, infra,
                                        "make: *** [Makefile:312: build] Error 2"), "fail")

    def test_patch_failure_names_the_owner(self):
        log = "applied: hst-base.patch\ndoes not apply: hst-c.patch\nFAILED line 205"
        self.assertEqual(qt.attribute(self.MEMBERS, log), ("patch", ["fix/c"], "does not apply: hst-c.patch"))

    def test_compile_errors_in_real_formats(self):
        gcc = "/data/hst-office-build/src/lo/sw/source/core/a.cxx:12:3: error: 'x' was not declared"
        msvc = r"D:\hst-build\lo\sc\source\ui\c.cxx(40): error C2065: 'y': undeclared identifier"
        a11y = "xmlsecurity/uiconfig/ui/hstpdfviewer.ui:631 FATAL WARNING: 'GtkImage' 'signatureimage' has no label"
        progress = "[build CXX] sw/source/core/a.cxx"
        self.assertEqual(qt.attribute(self.MEMBERS, gcc)[:2], ("compile", ["fix/a"]))
        self.assertEqual(qt.attribute(self.MEMBERS, msvc)[:2], ("compile", ["fix/c"]))
        self.assertEqual(qt.attribute(self.MEMBERS, a11y)[:2], ("compile", ["fix/b"]))
        self.assertIsNone(qt.attribute(self.MEMBERS, progress + "\nmake: *** [Makefile:312: build] Error 2"))
        self.assertEqual(qt.error_files("make[1]: *** [/data/x/src/lo/solenv/gbuild/UIConfig.mk:159: "
                                        "/data/x/src/lo/workdir/UIConfig/xmlsec.a11yerrors] Error 1"), set())

    def test_single_bisect_and_bisect_limit(self):
        unknown = "undefined reference to `Foo::bar()'\nmake: *** [Makefile:312: build] Error 2"
        self.assertEqual(qt.decide_failure(self.MEMBERS[:1], unknown, 0, 2)[:3], ("blame", "single", ["fix/a"]))
        self.assertEqual(qt.decide_failure(self.MEMBERS, unknown, 0, 2)[0], "bisect")
        self.assertEqual(qt.decide_failure(self.MEMBERS, unknown, 1, 2)[0], "bisect")
        self.assertEqual(qt.decide_failure(self.MEMBERS[:2], unknown, 2, 2)[:3],
                         ("blame", "bisect-limit", ["fix/a", "fix/b"]))
        self.assertEqual(qt.split_halves(self.MEMBERS), (self.MEMBERS[:2], self.MEMBERS[2:]))


    def test_test_set_and_failed_tests(self):
        members = [{"tests": ["CppunitTest_sw_a", "CppunitTest_smoke"]}, {}, {"tests": ["CppunitTest_sc_c"]}]
        self.assertEqual(qt.train_test_set({"train_tests": ["CppunitTest_smoke"]}, members),
                         ["CppunitTest_smoke", "CppunitTest_sw_a", "CppunitTest_sc_c"])
        self.assertEqual(qt.train_test_set({"train_tests": []}, [{}]), [])
        ok = {"result": "pass"}
        job = {"tests": ["T_a", "T_b", "T_c"], "test_results": {"T_a": ok, "T_b": {"result": "fail"}}}
        self.assertEqual(qt.failed_tests(job), ["T_b", "T_c"])   # no result recorded counts as failed
        self.assertEqual(qt.failed_tests({"tests": []}), [])

    def test_test_failures_are_blamed_by_the_assertion_location_only(self):
        noise = "warn:sw.core:1:1:/data/hst-office-build/src/lo/sc/source/ui/c.cxx:7: error while loading"
        assertion = "/data/hst-office-build/src/lo/sw/source/core/a.cxx:42:Assertion"
        self.assertEqual(qt.attribute(self.MEMBERS, noise + "\n" + assertion, "test")[:2], ("test", ["fix/a"]))
        self.assertIsNone(qt.attribute(self.MEMBERS, noise, "test"))   # SAL_WARN lines never blame
        self.assertEqual(qt.attribute(self.MEMBERS, noise)[:2], ("compile", ["fix/c"]))   # build logs: unchanged
        self.assertEqual(qt.decide_failure(self.MEMBERS, "test T failed", 0, 2, "test")[0], "bisect")


class DedupeTest(unittest.TestCase):
    def test_series_and_overrides(self):
        self.assertEqual(qg.dedupe_series("# c\na.patch\nb.patch\na.patch\n\n"), "# c\na.patch\nb.patch\n\n")
        text = "\n".join([override("Open", "Mở"), override("Save", "Lưu"), override("Open", "Mở tệp"), "junk"]) + "\n"
        self.assertEqual(qg.dedupe_overrides(text),
                         "\n".join([override("Save", "Lưu"), override("Open", "Mở tệp"), "junk"]) + "\n")
        self.assertEqual(qg.patch_files("--- a/sw/x.cxx\n+++ b/sw/x.cxx\n--- /dev/null\n+++ b/sw/new.hxx\n"),
                         {"sw/x.cxx", "sw/new.hxx"})


class TrainRepoTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.world = GitWorld(tmp.name)
        self.repo = qg.TrainRepo(f"{tmp.name}/train-repo", source=str(self.world.clone),
                                 remote_url=str(self.world.origin))
        self.repo.ensure()
        self.repo.fetch()

    def members(self, *names):
        self.repo.fetch()
        return [{"branch": n, "sha": self.repo.rev(n)} for n in names]

    def test_union_merge_is_deterministic_and_conflicts_are_skipped(self):
        self.world.member("fix/a", "hst-a.patch", "sw/source/a.cxx",
                          {"l10n/vi-overrides.jsonl": override("Open", "Mở") + "\n" + override("Save", "Lưu tệp") + "\n"})
        self.world.member("fix/b", "hst-b.patch", "sc/source/b.cxx")
        self.world.branch("fix/c", {"scripts/x.py": "x = 3\n"})
        self.world.branch("fix/d", {"scripts/x.py": "x = 4\n"})
        base = self.repo.rev(BASE)
        members = self.members("fix/a", "fix/b", "fix/c", "fix/d")
        sha, merged, conflicts = self.repo.merge(base, members, 1_800_000_000, "train/1.0.2-001")
        self.assertEqual(merged, ["fix/a", "fix/b", "fix/c"])
        self.assertEqual(list(conflicts), ["fix/d"])
        self.assertIn("scripts/x.py", conflicts["fix/d"])
        self.assertFalse(self.repo.conflicts_with_base(base, members[3]["sha"]))   # only clashes with fix/c
        self.assertEqual(self.world.show(members[0]["sha"], "patches/libreoffice/series"), "hst-base.patch\nhst-a.patch")
        again, _, _ = self.repo.merge(base, members, 1_800_000_000, "train/1.0.2-001")
        self.assertEqual(again, sha)
        self.assertEqual(self.repo.lo_files(base, members[0]["sha"]), (["hst-a.patch"], ["sw/source/a.cxx"]))
        self.assertTrue(self.repo.push("train/1.0.2-001", sha))
        self.assertFalse(self.repo.push("train/1.0.2-001", sha))   # idempotent
        series = self.world.show(sha, "patches/libreoffice/series").splitlines()
        self.assertEqual(series, ["hst-base.patch", "hst-a.patch", "hst-b.patch"])
        rows = self.world.show(sha, "l10n/vi-overrides.jsonl").splitlines()
        self.assertEqual(rows, [override("Open", "Mở"), override("Save", "Lưu tệp")])
        self.assertEqual(self.repo.remote_trains("train/1.0.2-"), {"train/1.0.2-001": sha})
        with self.assertRaises(qg.TrainGitError):
            self.repo.push("train/1.0.2-001", base)   # never moves an existing branch

    def test_guards_refuse_anything_but_train_branches(self):
        for name in ("main", BASE, "fix/a", "train/../main", "refs/heads/train/x"):
            with self.assertRaises(qg.TrainGitError):
                self.repo.push(name, self.repo.rev(BASE))
            with self.assertRaises(qg.TrainGitError):
                self.repo.delete_remote(name)
        self.repo.push("train/1.0.2-009", self.repo.rev(BASE))
        self.assertTrue(self.repo.delete_remote("train/1.0.2-009"))
        self.assertFalse(self.repo.delete_remote("train/1.0.2-009"))
        self.assertEqual(self.world.remote_heads(), {BASE})
        self.assertEqual(qg.scrub("https://user:tok@github.com/x"), "https://***@github.com/x")

    def test_conflict_with_the_base_is_detected(self):
        self.world.branch("fix/old", {"scripts/x.py": "x = 2\n"})
        old = self.repo.rev(BASE)
        self.world.branch(BASE, {"scripts/x.py": "x = 9\n"}, base=BASE)
        self.repo.fetch()
        self.assertTrue(self.repo.conflicts_with_base(self.repo.rev(BASE), self.repo.rev("fix/old")))
        self.assertFalse(self.repo.conflicts_with_base(old, self.repo.rev("fix/old")))


if __name__ == "__main__":
    unittest.main()
