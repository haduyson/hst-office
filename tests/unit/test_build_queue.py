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
