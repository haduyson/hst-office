# SPDX-License-Identifier: AGPL-3.0-only
"""Slot lock and clean (`build-queue.sh slot ...`, scripts/build_infra/slot_control.py), the dispatcher killing the
make scopes of a cancelled Linux job that keeps running, and the early warning for a low /data
(scripts/build_infra/data_disk.py)."""
import fcntl
import io
import os
from pathlib import Path
import subprocess
import tempfile
import time
import types

from build_queue_fixtures import FakeRunner, QueueTestCase, bq, bqd
from build_infra import data_disk, slot_control
from build_infra.dispatch_remote_linux import RemoteLinuxRunner
from build_infra.dispatch_windows import WindowsRunner
from test_build_queue_remote import HOST, FakeHost

CHECK = data_disk.check   # the fixture replaces it for the dispatch loop tests

S2 = "hst5:D:\\hst-build-s2"
WIN_SLOTS = [{"host": "hst5", "root": "D:\\hst-build", "jobs": 24}, {"host": "hst5", "root": "D:\\hst-build-s2",
                                                                      "jobs": 24}]


class FakeProc:
    pid = 4242


class SlotControlTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        Path(self.store.root, "config.json").write_text(
            bq.json.dumps({"windows_slots": WIN_SLOTS, "linux_remote_hosts": [HOST]}))
        self.ctl = slot_control.SlotControl(self.store)
        self.logs = []

    def test_lock_unlock_and_validation(self):
        slot, entry = slot_control.lock(self.store, S2, "LNK1136 investigation")
        self.assertEqual((slot, entry["locked"], entry["reason"]), (S2, True, "LNK1136 investigation"))
        self.assertEqual(self.ctl.locked_slots(), {S2})
        slot_control.unlock(self.store, S2)
        self.assertFalse(self.ctl.locked(S2))
        for args, why in (((S2, " "), "--reason"), (("hst9:D:\\x", "r"), "unknown slot"),
                          (("vm103:3", "r"), "unknown slot")):   # vm103 has 2 slots
            with self.assertRaisesRegex(bq.QueueError, why):
                slot_control.lock(self.store, *args)
        with self.assertRaisesRegex(bq.QueueError, "not locked"):
            slot_control.unlock(self.store, S2)
        self.assertEqual(slot_control.resolve_slot(self.store.config(), "vm103:2"), ("vm103:2", "remote"))
        self.assertEqual(slot_control.resolve_slot(self.store.config(), "3"), ("3", "local"))

    def test_a_linux_slot_is_only_cleaned_in_full(self):
        with self.assertRaisesRegex(bq.QueueError, "only cleaned with --full"):
            slot_control.request_clean(self.store, "vm103:1", "stale tree")
        _, entry = slot_control.request_clean(self.store, "vm103:1", "stale tree", full=True)
        self.assertTrue(entry["locked"])
        with self.assertRaisesRegex(bq.QueueError, "already requested"):
            slot_control.request_clean(self.store, "vm103:1", "again", full=True)
        with self.assertRaisesRegex(bq.QueueError, "unlocks the slot when it ends"):
            slot_control.unlock(self.store, "vm103:1")

    def test_clean_waits_for_the_running_job_then_runs_in_the_background_and_unlocks(self):
        job, _ = self.submit(platform="windows")
        self.store.update(job["id"], state="running", slot=S2)
        slot_control.request_clean(self.store, S2, "LNK1136")
        started = []

        def popen(argv, **kw):
            started.append(argv)
            kw["stdout"].write('{"cleaned": true, "full": false, "objects": {"checked": 9, "removed": 1}}\n')
            return FakeProc()
        cfg = self.store.config()
        slot_control.process(self.store, cfg, self.store.all(), self.logs.append, popen=popen)
        self.assertEqual(started, [])   # a job still runs on the slot
        self.store.update(job["id"], state="done")
        slot_control.process(self.store, cfg, self.store.all(), self.logs.append, popen=popen)
        self.assertEqual(started[0][-4:], ["-Action", "Clean", "-Root", "D:\\hst-build-s2"])
        self.assertEqual(self.ctl.get(S2)["clean"]["state"], "running")
        self.assertTrue(self.ctl.locked(S2))
        with unittest_mock_pid_dead():
            slot_control.process(self.store, cfg, self.store.all(), self.logs.append, popen=popen)
        entry = self.ctl.get(S2)
        self.assertEqual(entry["clean"]["state"], "done")
        self.assertEqual(entry["clean"]["result"]["objects"]["removed"], 1)
        self.assertFalse(entry["locked"])
        out = io.StringIO()
        self.assertEqual(slot_control.wait_clean(self.store, S2, out=out), 0)
        self.assertIn("clean done", out.getvalue())

    def test_a_failed_clean_or_a_slot_locked_before_stays_locked(self):
        slot_control.lock(self.store, S2, "kept by the integrator")
        slot_control.request_clean(self.store, S2, "full", full=True)
        self.assertEqual(self.ctl.get(S2)["reason"], "kept by the integrator")

        def popen(argv, **kw):
            self.assertIn("-Full", argv)
            kw["stdout"].write('{"cleaned": false, "reason": "busy"}\n')
            return FakeProc()
        cfg = self.store.config()
        slot_control.process(self.store, cfg, [], self.logs.append, popen=popen)
        with unittest_mock_pid_dead():
            slot_control.process(self.store, cfg, [], self.logs.append, popen=popen)
        entry = self.ctl.get(S2)
        self.assertEqual((entry["clean"]["state"], entry["locked"]), ("failed", True))
        self.assertEqual(slot_control.wait_clean(self.store, S2, out=io.StringIO()), 1)

    def test_windows_scheduling_skips_a_locked_slot(self):
        cfg = self.store.config()
        runner = WindowsRunner(self.store, cfg)
        runner.deploy = lambda host, force=False: "tools"
        for slot in WIN_SLOTS:
            runner.probes[f"{slot['host']}:{slot['root']}"] = (time.time(), {"busy": False, "free_gib": 100})
        slot_control.lock(self.store, "hst5:D:\\hst-build", "maintenance")
        self.assertEqual(runner.free_slot([])["root"], "D:\\hst-build-s2")
        slot_control.lock(self.store, S2, "maintenance")
        self.assertIsNone(runner.free_slot([]))

    def test_remote_linux_scheduling_excludes_a_locked_slot(self):
        host = FakeHost()
        runner = RemoteLinuxRunner(self.store, self.store.config(), HOST, host=host)
        runner.ensure_deployed = lambda: "/data/hst-build/infra-abc"
        slot_control.lock(self.store, "vm103:2", "disk check")
        runner.free_slot([], 12)
        argv = next(a for a in host.calls if "free-slot" in a)
        self.assertEqual(argv[argv.index("--exclude") + 1], "2")

    def test_the_linux_clean_holds_the_slot_lock_and_deletes_workdir_and_instdir(self):
        with tempfile.TemporaryDirectory() as root:
            lo = Path(root, "src", "lo")
            for d in ("workdir/CxxObject", "instdir/program", "sw"):
                (lo / d).mkdir(parents=True)
            script = slot_control.linux_clean_script(root)
            with open(Path(root, ".lock"), "w", encoding="ascii") as held:
                fcntl.flock(held, fcntl.LOCK_EX)   # a build holds the slot
                busy = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=False)
            self.assertEqual(busy.returncode, 1)
            self.assertIn('"cleaned": false', busy.stdout)
            self.assertTrue((lo / "workdir").exists())
            done = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=False)
            self.assertEqual((done.returncode, done.stdout.strip()), (0, '{"cleaned": true, "full": true}'))
            self.assertEqual(sorted(p.name for p in lo.iterdir()), ["sw"])
        cmd = slot_control.clean_command(self.store.config(), "vm103:1", "remote", True)
        self.assertIn("/data/hst-build/slots/1/.lock", cmd[-1])

    def test_cli_slot_commands(self):
        args = types.SimpleNamespace(slot_cmd="clean", slot=S2, reason="LNK1136", full=False, keep_locked=True,
                                     no_wait=True, timeout=None)
        out = io.StringIO()
        from build_infra.queue_cli import slot_cmd
        self.assertEqual(slot_cmd(self.store, args, out=out), 0)
        self.assertIn("it stays locked", out.getvalue())
        slot_cmd(self.store, types.SimpleNamespace(slot_cmd="list"), out=out)
        self.assertIn(f"{S2}  LOCKED", out.getvalue())


class unittest_mock_pid_dead:   # noqa: N801 - reads like the context manager it is
    """slot_control's pid check says the clean process ended."""
    def __enter__(self):
        self.real = slot_control._pid_alive
        slot_control._pid_alive = lambda pid: False

    def __exit__(self, *exc):
        slot_control._pid_alive = self.real


class CancelKillTreeTest(QueueTestCase):
    def test_a_cancelled_job_still_running_gets_its_process_tree_killed_once(self):
        linux = FakeRunner([1])
        linux.killed = []
        linux.kill_tree = lambda job: linux.killed.append(job["id"]) or True
        runners = {"linux": linux, "windows": FakeRunner([])}
        job, _ = self.submit()
        bqd.tick(self.store, runners, bq)
        bq.cancel(self.store, job["id"])
        bqd.tick(self.store, runners, bq)
        self.assertEqual((linux.cancelled, linux.killed), ([job["id"]], []))
        bqd.tick(self.store, runners, bq)
        self.assertEqual(linux.killed, [])   # within cancel_kill_after_seconds
        self.store.update(job["id"], cancel_sent_at=time.time() - 3600)
        bqd.tick(self.store, runners, bq)
        bqd.tick(self.store, runners, bq)
        self.assertEqual(linux.killed, [job["id"]])
        self.assertTrue(self.store.load(job["id"])["cancel_killed"])
        self.assertIn("make scopes of slot 1 killed", Path(job["log"]).read_text())

    def test_the_local_runner_kills_only_while_its_runner_lives(self):
        from build_infra import dispatch_linux
        runner = dispatch_linux.LinuxRunner(self.store, bq.DEFAULT_CONFIG)
        calls = []
        real = dispatch_linux.subprocess.run
        dispatch_linux.subprocess.run = lambda argv, **kw: calls.append(argv)
        try:
            self.assertFalse(runner.kill_tree({"pid": None, "slot": 3}))
            self.assertTrue(runner.kill_tree({"pid": os.getpid(), "slot": 3}))
        finally:
            dispatch_linux.subprocess.run = real
        self.assertEqual(calls, [["systemctl", "kill", "--signal=KILL", "hst-local-build-s3-*.scope"]])

    def test_the_remote_runner_kills_the_scopes_of_the_jobs_slot_while_its_unit_is_active(self):
        host = FakeHost()
        runner = RemoteLinuxRunner(self.store, dict(bq.DEFAULT_CONFIG, linux_remote_hosts=[HOST]), HOST, host=host)
        self.assertTrue(runner.kill_tree({"id": "q261122-140000-abcd", "slot": "vm103:2"}))
        script = host.calls[-1][2]
        self.assertIn("systemctl is-active -q hstq-q261122-140000-abcd.service || exit 3", script)
        self.assertIn("'hst-local-build-s2-*.scope'", script)


class DataDiskTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        data_disk._STATE.update(warned=0.0, du_running=False)
        self.logs = []

    def test_warns_below_the_limit_at_most_hourly_and_names_the_largest_directories(self):
        cfg, t = dict(bq.DEFAULT_CONFIG), 1_800_000_000.0
        self.assertIsNone(CHECK(self.store, cfg, self.logs.append, now=t, free=40.0))
        line = CHECK(self.store, cfg, self.logs.append, now=t, free=17.2, top=lambda: ["/data/hst-agents 80.0G"])
        self.assertIn("17.2 GiB free (< 25 GiB)", line)
        self.assertIsNone(CHECK(self.store, cfg, self.logs.append, now=t + 600, free=17.0))
        self.assertIsNotNone(CHECK(self.store, cfg, self.logs.append, now=t + 3600, free=17.0, top=lambda: []))
        alerts = Path(self.store.root, "alerts.log").read_text()
        self.assertIn("largest in", alerts)
        self.assertIn("/data/hst-agents 80.0G", alerts)
        self.assertEqual(len([m for m in self.logs if m.startswith("WARNING")]), 2)
        self.assertIsNone(data_disk.warning(self.store, dict(cfg, data_warn_free_gib=10), free=17.0))

    def test_largest_dirs_parses_du(self):
        du = "100\t/data/a\n9437184\t/data/hst-agents\n2097152\t/data/hst-build\n11534336\t/data\n"
        self.assertEqual(data_disk.largest_dirs("/data", du_output=du, count=2),
                         ["/data/hst-agents 9.0G", "/data/hst-build 2.0G"])


class WindowsHelperTextTest(QueueTestCase):
    """hst-queue-remote.ps1 runs only on the Windows hosts; these checks keep its kill rules from drifting."""

    def test_cancel_matches_only_slot_paths_and_never_mspdbsrv(self):
        from build_queue_fixtures import ROOT
        text = (ROOT / "scripts/windows/hst-queue-remote.ps1").read_text(encoding="utf-8")
        body = text[text.index("function Get-SlotProcesses"):text.index("function Stop-SlotBuild")]
        # one form per element: `"a", (b) + '/'` in an array literal once made the form "/" (every process)
        self.assertIn('$forms = @("$base\\", "$slash/", "$cygwin/")', body)
        self.assertIn("refusing to match processes", body)
        self.assertIn("mspdbsrv", body)
        self.assertIn("'Clean'", text[text.index("ValidateSet"):text.index("ValidateSet") + 200])
