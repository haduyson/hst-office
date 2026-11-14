# SPDX-License-Identifier: AGPL-3.0-only
"""Remote Linux build host (scripts/build_infra/dispatch_remote_linux.py, dispatch_linux_pool.py) with a fake SSH
transport: slot choice, the bounded start command (slice, job caps, environment), log streaming, copying the
output back, offline detection with requeue to the dev server, leftover units on reconnect, the job timeout and
the pool order (dev server first, avoid_hosts)."""
import os
from pathlib import Path
import types

from build_queue_fixtures import FakeRunner, QueueTestCase, bq, bqd
from build_infra.dispatch_linux_pool import LinuxPool
from build_infra.dispatch_remote_linux import RemoteLinuxRunner
from build_infra.remote_host import HostStates, RemoteError

HOST = {"name": "vm103", "address": "192.0.2.10", "key": "/k", "known_hosts": "/kh", "slots": 2, "total_jobs": 12,
        "max_jobs": 12, "min_free_gib": 15, "ccache_max": "10G"}


class FakeHost:
    def __init__(self):
        self.calls = []
        self.down = False
        self.slot = "1"
        self.status = "RUNNING:active"
        self.log = ""
        self.out_files = {"HSTOffice_1.0.1_Linux_x86-64.deb": "deb"}
        self.units = ""
        self.user, self.address = "root", HOST["address"]

    def run(self, argv, timeout=60, check=True):
        if self.down:
            raise RemoteError("vm103: ssh failed: timed out")
        self.calls.append(argv)
        out, rc = "", 0
        if "free-slot" in argv:
            out, rc = (self.slot, 0) if self.slot else ("", 1)
        elif argv[:2] == ["sh", "-c"] and "@@LOG@@" in argv[2]:
            out = f"{self.status}\n@@LOG@@\n{self.log}"
        elif argv[:2] == ["systemctl", "list-units"]:
            out = self.units
        return types.SimpleNamespace(stdout=out, stderr="", returncode=rc)

    def rsync_from(self, remote, local, timeout=3600, append=False):
        if self.down:
            raise RemoteError("vm103: rsync timed out")
        for name, text in self.out_files.items():
            Path(local, name).write_text(text)

    def git_ssh(self):
        return "ssh"


class RemoteTestCase(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.t = [1_800_000_000.0]
        self.cfg = dict(bq.DEFAULT_CONFIG, linux_remote_hosts=[HOST])
        self.host = FakeHost()
        self.remote = RemoteLinuxRunner(self.store, self.cfg, HOST, host=self.host, now=lambda: self.t[0])
        self.remote.push = lambda sha, ref: self.host.calls.append(["push", sha, ref])
        self.remote.ensure_deployed = lambda: "/data/hst-build/infra-abc"

    def tick(self, seconds=60):
        self.t[0] += seconds

    def running_job(self, **kw):
        job, _ = self.submit(**kw)
        fields = self.remote.start(job, "vm103:1")
        return self.store.update(job["id"], state="running", started=self.t[0], **fields)


class RemoteRunnerTest(RemoteTestCase):
    def test_free_slot_and_bounded_start(self):
        self.assertEqual(self.remote.free_slot([], 20), "vm103:1")
        self.assertIn("HST_TOTAL_JOBS=12", self.host.calls[-1])
        self.assertEqual(self.host.calls[-1][self.host.calls[-1].index("--want") + 1], "12")   # capped at max_jobs
        job, _ = self.submit()
        self.assertIsNone(self.remote.free_slot([], 20, dict(job, avoid_hosts=["vm103"])))
        fields = self.remote.start(job, "vm103:2")
        self.assertEqual((fields["host"], fields["slot"]), ("vm103", "vm103:2"))
        run = self.host.calls[-1]
        self.assertEqual(run[0], "systemd-run")
        for want in ("--slice=hst-build.slice", f"--unit=hstq-{job['id']}", "OOMScoreAdjust=500", "Nice=10",
                     "--setenv=HST_LOCAL_SLICE=hst-build.slice", "--setenv=HST_MIN_FREE_GIB=15",
                     "--setenv=HST_LOCAL_MIN_FREE_GIB=15", "--setenv=HST_CCACHE_MAX=10G", job["sha"]):
            self.assertIn(want, run)
        self.assertEqual(run[run.index("-j") + 1], "12")
        self.assertEqual(run[run.index("--slot") + 1], "2")
        self.assertIn(["push", job["sha"], f"refs/q/{job['id']}"], self.host.calls)

    def test_log_streaming_then_output_copied_back_and_host_cleaned(self):
        job = self.running_job()
        self.host.log = "phase patch: start\n"
        self.assertIsNone(self.remote.check(job))
        self.assertIn("phase patch: start", Path(job["log"]).read_text())
        self.assertEqual(self.store.load(job["id"])["remote_log_offset"], len("phase patch: start\n"))
        self.assertIsNone(self.remote.check(self.store.load(job["id"])))   # polled at most every 30 s
        self.tick()
        self.host.status, self.host.log = "0", "output: done\n"
        state, fields = self.remote.check(self.store.load(job["id"]))
        self.assertEqual(state, "done")
        self.assertEqual([os.path.basename(p) for p in fields["output"]], ["HSTOffice_1.0.1_Linux_x86-64.deb"])
        self.assertTrue(any("rm -rf" in " ".join(c) and job["id"] in " ".join(c) for c in self.host.calls))

    def test_build_failure_and_vanished_unit(self):
        job = self.running_job()
        self.host.status = "2"
        self.assertEqual(self.remote.check(job), ("failed", {"error": "local-build.sh exit 2"}))
        other = self.running_job(ref="feat/x")
        self.host.status = "RUNNING:inactive"
        state, fields = self.remote.check(other)
        self.assertEqual(state, "failed")
        self.assertTrue(bq.infra_failure(fields["error"], ""))   # requeued by the dispatcher

    def test_unreachable_host_goes_offline_and_its_jobs_build_elsewhere(self):
        job = self.running_job()
        self.host.down = True
        for _ in range(4):   # first failure at +1 min, then 3 more minutes without an answer: not yet offline
            self.tick()
            self.assertIsNone(self.remote.check(self.store.load(job["id"])))
            self.remote.health(self.store.all())
        self.assertEqual(self.store.load(job["id"])["state"], "running")
        self.tick(130)   # 5 min 10 s since the first failed contact
        self.remote.check(self.store.load(job["id"]))
        self.remote.health(self.store.all())
        state = self.store.load(job["id"])
        self.assertEqual((state["state"], state["avoid_hosts"]), ("queued", ["vm103"]))
        self.assertIn("vm103 stopped answering", Path(job["log"]).read_text())
        self.assertEqual(HostStates(self.store).get("vm103")["state"], "offline")
        self.assertIsNone(self.remote.free_slot([], 20))   # offline: no ssh at all until the next probe
        # It answers again: online, and the unit it still runs for the requeued job is stopped.
        self.host.down = False
        self.host.units = f"  hstq-{job['id']}.service loaded active running hst\n"
        self.tick(61)
        self.assertEqual(self.remote.free_slot([], 20), "vm103:1")
        self.assertIn(["systemctl", "kill", "--signal=TERM", f"hstq-{job['id']}.service"], self.host.calls)
        self.assertEqual(HostStates(self.store).get("vm103")["state"], "online")

    def test_job_timeout_stops_and_requeues_elsewhere(self):
        job = self.running_job()
        self.tick(6 * 3600 + 1)
        state, fields = self.remote.check(job)
        self.assertEqual(state, "failed")
        self.assertTrue(fields["error"].startswith("dispatcher: vm103 job ran longer than 6 h"))
        self.assertIn(["systemctl", "kill", "--signal=TERM", f"hstq-{job['id']}.service"], self.host.calls)
        self.assertEqual(self.store.load(job["id"])["avoid_hosts"], ["vm103"])


class PoolTest(RemoteTestCase):
    def test_dev_server_first_then_remote_and_dispatch_by_host(self):
        local = FakeRunner([])
        pool = LinuxPool(self.store, self.cfg, local=local, remotes=[self.remote])
        job, _ = self.submit()
        self.assertEqual(pool.free_slot([], 20, job), "vm103:1")   # no local slot free
        local.slots = ["1"]
        self.assertEqual(pool.free_slot([], 20, job), "1")
        self.assertEqual(pool.free_slot([], 20, dict(job, avoid_hosts=["local"])), "vm103:1")
        runners = {"linux": pool, "windows": FakeRunner([])}
        local.slots = []
        bqd.tick(self.store, runners, bq)
        state = self.store.load(job["id"])
        self.assertEqual((state["state"], state["host"], state["slot"]), ("running", "vm103", "vm103:1"))
        self.host.status = "0"
        self.remote.next_poll.clear()
        bqd.tick(self.store, runners, bq)
        self.assertEqual(self.store.load(job["id"])["state"], "done")
        pool.cfg = dict(self.cfg, linux_remote_hosts=[dict(HOST, address="192.0.2.99")])
        self.assertEqual(pool.remotes[0].host.address, "192.0.2.99")
        pool.cfg = dict(self.cfg, linux_remote_hosts=[dict(HOST, enabled=False)])
        self.assertEqual(pool.remotes, [])


class SliceCgroupTest(RemoteTestCase):
    def test_a_dash_nests_slices(self):
        from build_infra.slots_host import slice_cgroup
        self.assertEqual(slice_cgroup("hst-build.slice"), "/sys/fs/cgroup/hst.slice/hst-build.slice")
        self.assertEqual(slice_cgroup("system.slice"), "/sys/fs/cgroup/system.slice")
        import subprocess
        from build_queue_fixtures import ROOT
        fn = subprocess.run(["sed", "-n", "/^slice_cg()/,/^}/p", str(ROOT / "scripts/linux/local-build.sh")],
                            capture_output=True, text=True, check=True).stdout
        out = subprocess.run(["bash", "-c", fn + "\nslice_cg hst-build.slice; slice_cg system.slice"],
                             capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(out, ["/sys/fs/cgroup/hst.slice/hst-build.slice", "/sys/fs/cgroup/system.slice"])


class RemoteOnlyLinuxTest(RemoteTestCase):
    """linux_local_enabled=false: every Linux build (package, train leg, --modules, --test) goes to the remote host;
    jobs already running on the dev server still finish; queued jobs show what they wait for."""

    def pool(self, local):
        cfg = dict(self.cfg, linux_local_enabled=False)
        with open(os.path.join(self.store.root, "config.json"), "w") as f:
            import json
            json.dump({"linux_local_enabled": False, "linux_remote_hosts": [HOST]}, f)
        p = LinuxPool(self.store, cfg, local=local, remotes=[self.remote])
        p._cfg = cfg
        return p

    def test_no_local_admission_and_every_kind_goes_remote(self):
        local = FakeRunner(["1", "2"])
        pool = self.pool(local)
        for kw in ({}, {"modules": ["sc"]}, {"tests": ["CppunitTest_sc_ucalc"]},
                   {"ref": "train/1.0.2-009", "internal": True, "train": "train/1.0.2-009"}):
            self.shas.setdefault("train/1.0.2-009", "9" * 40)
            job, _ = self.submit(**kw)
            self.remote.slot_cache = (0.0, None)
            self.assertEqual(pool.free_slot([], 20, job), "vm103:1", kw)
        avoided, _ = self.submit(ref="feat/x")
        self.remote.slot_cache = (0.0, None)
        self.assertEqual(pool.free_slot([], 20, dict(avoided, avoid_hosts=["vm103"])), "vm103:1")   # only host
        self.host.slot = ""                                    # vm103 full: nothing goes to the dev server
        self.remote.slot_cache = (0.0, None)
        self.assertIsNone(pool.free_slot([], 20, avoided))
        self.assertEqual(local.started, [])

    def test_a_local_job_already_running_finishes_normally(self):
        local = FakeRunner([])
        pool = self.pool(local)
        job, _ = self.submit()
        job = self.store.update(job["id"], state="running", host="local", slot="1")
        local.results[job["id"]] = ("done", {"output": []})
        self.assertEqual(pool.check(job), ("done", {"output": []}))

    def test_list_says_what_queued_linux_jobs_wait_for(self):
        self.pool(FakeRunner([]))
        running = self.running_job()
        queued, _ = self.submit(ref="feat/x")
        notes = __import__("build_infra.queue_cli", fromlist=["x"]).linux_waits(self.store, self.store.all())
        self.assertEqual(notes[queued["id"]], "  waiting for vm103 (vm103 1/2 slots busy)")
        self.assertNotIn(running["id"], notes)
        HostStates(self.store).offline("vm103", "test")
        notes = __import__("build_infra.queue_cli", fromlist=["x"]).linux_waits(self.store, self.store.all())
        self.assertEqual(notes[queued["id"]], "  waiting for vm103 (vm103 OFFLINE)")

    def test_cleanup_prunes_old_logs_and_stale_queue_files_on_the_host(self):
        self.remote.cleanup("q261114-000000-abcd")
        cmd = self.host.calls[-1][2]
        self.assertIn("slots/*/logs -mindepth 1 -maxdepth 1 -name '20*' -mtime +2", cmd)
        self.assertIn("-mtime +1 -exec rm -rf", cmd)
