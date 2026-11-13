# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue test mode (`submit --test`): target validation, dedupe key, PASS/FAIL output of `wait`, baseline
comparison, retention per job kind and the dispatcher passing/reading the test results."""
import io
import os
from pathlib import Path
import unittest

from build_queue_fixtures import QueueTestCase, bq, bqd


class TestModeTest(QueueTestCase):
    def finish_tests(self, job, results):
        out = self.store.job_out(job["id"])
        os.makedirs(os.path.join(out, "test-logs"), exist_ok=True)
        res = {}
        for target, ok in results.items():
            Path(out, "test-logs", target + ".log").write_text("ok\n" if ok else "Assertion failed\nError 1\n")
            res[target] = {"result": "pass" if ok else "fail", "exit": 0 if ok else 2, "seconds": 7,
                           "log": "test-logs/" + target + ".log"}
        return self.store.update(job["id"], state="done", output=[], test_results=res, finished=job["submitted"])

    def test_parse_and_validate_targets(self):
        self.assertEqual(bq.parse_tests("CppunitTest_sc_ucalc, CppunitTest_xmlsecurity_signing sw.check"),
                         ["CppunitTest_sc_ucalc", "CppunitTest_xmlsecurity_signing", "sw.check"])
        for bad in ("UITest_writer", "CppunitTest_sc;rm", "../x", "Library_merged"):
            with self.assertRaises(bq.QueueError):
                bq.parse_tests(bad)
        with self.assertRaises(bq.QueueError):
            self.submit(platform="windows", tests=["CppunitTest_sc_ucalc"])

    def test_tests_are_part_of_the_key_and_imply_no_package(self):
        build, _ = self.submit()
        test, dup = self.submit(tests=["CppunitTest_sc_ucalc"])
        self.assertFalse(dup)
        self.assertFalse(test["package"])
        self.assertNotEqual(build["id"], test["id"])
        same, dup = self.submit(tests=["CppunitTest_sc_ucalc"])
        self.assertTrue(dup)
        self.assertEqual(same["id"], test["id"])
        self.assertIn("tests 1", bq.describe(test))

    def test_wait_prints_pass_fail_and_exits_3_on_failure(self):
        job, _ = self.submit(tests=["CppunitTest_a", "CppunitTest_b"])
        self.finish_tests(job, {"CppunitTest_a": True, "CppunitTest_b": False})
        out = io.StringIO()
        self.assertEqual(bq.wait(self.store, job["id"], out=out), 3)
        text = out.getvalue()
        self.assertIn("PASS CppunitTest_a", text)
        self.assertIn("FAIL CppunitTest_b", text)
        self.assertIn("Assertion failed", text)
        ok, _ = self.submit(ref="feat/x", tests=["CppunitTest_a"])
        self.finish_tests(ok, {"CppunitTest_a": True})
        self.assertEqual(bq.wait(self.store, ok["id"], out=io.StringIO()), 0)

    def test_compare_flags_regressions_against_the_baseline(self):
        base, _ = self.submit(tests=["CppunitTest_a", "CppunitTest_b"])
        self.finish_tests(base, {"CppunitTest_a": True, "CppunitTest_b": False})
        branch, _ = self.submit(ref="feat/x", tests=["CppunitTest_a", "CppunitTest_b"])
        self.finish_tests(branch, {"CppunitTest_a": False, "CppunitTest_b": True})
        out = io.StringIO()
        self.assertEqual(bq.compare(self.store, base["id"], branch["id"], out=out), 3)
        self.assertIn("REGRESSION", out.getvalue())
        self.assertIn("fixed", out.getvalue())

    def test_retention_keeps_test_runs_apart_from_packages(self):
        pkg, _ = self.submit()
        self.finish(pkg, finished=1)
        for i in range(3):
            self.shas["rc/1.0.2-batch4"] = f"{i + 1:040d}"
            job, _ = self.submit(tests=["CppunitTest_a"])
            self.finish_tests(job, {"CppunitTest_a": True})
        bq.apply_retention(self.store, 1)
        self.assertFalse(self.store.load(pkg["id"]).get("output_deleted"))

    def test_linux_runner_passes_tests_and_reads_results(self):
        job, _ = self.submit(tests=["CppunitTest_a", "sc.check"])
        runner = bqd.LinuxRunner(self.store, bq.DEFAULT_CONFIG)
        cmd = []
        real_popen = bqd.subprocess.Popen

        class FakeProc:
            pid = 4242

        def fake_popen(args, **kw):
            cmd.extend(args)
            return FakeProc()
        bqd.subprocess.Popen = fake_popen
        try:
            runner.start(job, 2)
        finally:
            bqd.subprocess.Popen = real_popen
        self.assertEqual(cmd[cmd.index("--test") + 1], "CppunitTest_a sc.check")
        out = self.store.job_out(job["id"])
        os.makedirs(out, exist_ok=True)
        import json
        Path(out, "test-results.json").write_text(json.dumps({"results": {"CppunitTest_a": {
            "result": "pass", "exit": 0, "seconds": 3, "log": "test-logs/CppunitTest_a.log"}}}))
        Path(runner.rc_path(job)).write_text("0\n")
        state, fields = runner.check(job)
        self.assertEqual(state, "done")
        self.assertEqual(fields["test_results"]["CppunitTest_a"]["result"], "pass")
        Path(runner.rc_path(job)).write_text("0\n")
        os.remove(Path(out, "test-results.json"))
        self.assertEqual(runner.check(job)[0], "failed")


if __name__ == "__main__":
    unittest.main()
