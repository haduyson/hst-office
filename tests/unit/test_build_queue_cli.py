# SPDX-License-Identifier: AGPL-3.0-only
"""End to end through the real entry points (`python3 -I scripts/build-queue.py ...` and
`python3 -I scripts/linux/build-slots.py ...`), against a temporary queue and slot root: every CLI verb, a real
submit (git ref resolution, submitter from the environment) and one dispatcher loop iteration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "scripts/build-queue.py"
SLOTS = ROOT / "scripts/linux/build-slots.py"
HEAD = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                      check=True).stdout.strip()


class BuildQueueCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, "HST_QUEUE_ROOT": str(self.root / "queue"), "HST_BUILD_ROOT": str(self.root / "build"),
                    "SUDO_USER": "", "USER": "cli-test", "GIT_TERMINAL_PROMPT": "0"}
        self.env.pop("SUDO_USER")

    def run_cli(self, *args, script=QUEUE, ok=(0,)):
        done = subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True,
                              env=self.env, cwd=self.root, timeout=300, check=False)
        self.assertIn(done.returncode, ok, f"{args}: rc={done.returncode}\n{done.stdout}\n{done.stderr}")
        return done

    def job(self, job_id):
        return json.loads((self.root / "queue/jobs" / f"{job_id}.json").read_text())

    def finish(self, job_id, **fields):
        path = self.root / "queue/jobs" / f"{job_id}.json"
        data = json.loads(path.read_text())
        data.update(state="done", finished=data["submitted"], **fields)
        path.write_text(json.dumps(data))

    def test_every_queue_verb(self):
        job_id = self.run_cli("submit", "--platform", "linux", "--ref", HEAD, "--priority", "5").stdout.strip()
        job = self.job(job_id)
        self.assertEqual((job["state"], job["sha"], job["submitter"]), ("queued", HEAD, "cli-test"))
        again = self.run_cli("submit", "--platform", "linux", "--ref", HEAD, "--priority", "5")
        self.assertEqual(again.stdout.strip(), job_id)
        self.assertIn("deduplicated", again.stderr)
        self.assertIn(job_id, self.run_cli("status", job_id).stdout)
        self.assertEqual(json.loads(self.run_cli("status", job_id, "--json").stdout)["id"], job_id)
        self.assertIn(job_id, self.run_cli("list").stdout)
        self.assertEqual(len(json.loads(self.run_cli("list", "--all", "--json").stdout)), 1)
        self.assertIn("timeout", self.run_cli("wait", job_id, "--timeout", "0", ok=(2,)).stdout)
        self.assertIn("cancelled", self.run_cli("cancel", job_id).stdout)
        self.assertEqual(self.job(job_id)["state"], "cancelled")

        base = self.run_cli("submit", "--platform", "linux", "--ref", HEAD, "--test", "CppunitTest_a").stdout.strip()
        branch = self.run_cli("submit", "--platform", "linux", "--ref", HEAD, "--test",
                              "CppunitTest_a CppunitTest_b").stdout.strip()
        result = {"result": "pass", "exit": 0, "seconds": 1, "log": "test-logs/x.log"}
        self.finish(base, test_results={"CppunitTest_a": result})
        self.finish(branch, test_results={"CppunitTest_a": dict(result, result="fail"), "CppunitTest_b": result})
        self.assertIn("PASS CppunitTest_a", self.run_cli("wait", base).stdout)
        self.assertIn("FAIL CppunitTest_a", self.run_cli("wait", branch, ok=(3,)).stdout)
        self.assertIn("REGRESSION", self.run_cli("compare", base, branch, ok=(3,)).stdout)
        self.assertIn("invalidated", self.run_cli("invalidate", base, "--reason", "cli test").stdout)
        self.assertEqual(self.job(base)["state"], "failed")

        self.assertIn("draining", self.run_cli("drain", "hst4", "--no-wait").stdout)
        self.assertIn("cancelled", self.run_cli("drain", "hst4", "--cancel").stdout)
        self.assertIn("unknown Windows host", self.run_cli("drain", "nohost", ok=(2,)).stderr)
        self.assertIn("--platform", self.run_cli("submit", "--platform", "mac", "--ref", HEAD, ok=(2,)).stderr)

    def test_dispatcher_loop_runs_one_iteration(self):
        job_id = self.run_cli("submit", "--platform", "linux", "--ref", HEAD).stdout.strip()
        # No slot exists under the temporary build root: the job must stay queued and the tick must not fail.
        done = self.run_cli("dispatch", "--once")
        self.assertIn("dispatcher started", done.stdout)
        self.assertNotIn("tick failed", done.stdout)
        self.assertEqual(self.job(job_id)["state"], "queued")
        # The service already holds the lock: a second dispatcher refuses.
        import fcntl
        with open(self.root / "queue/dispatcher.lock", "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertIn("another dispatcher", self.run_cli("dispatch", "--once", ok=(1,)).stderr)

    def test_every_slots_verb(self):
        for n in (1, 2):
            (self.root / f"build/slots/{n}/src").mkdir(parents=True)
        self.assertEqual(self.run_cli("budget", "--jobs", "20", script=SLOTS).stdout.strip(), "12288")
        free = self.run_cli("free-slot", "--want", "4", script=SLOTS, ok=(0, 1))
        pid = str(os.getpid())
        if free.returncode == 0:   # enough memory/disk on this machine to admit a small slot
            self.assertEqual(free.stdout.strip(), "1")
        else:
            self.assertRegex(free.stderr, "memory|disk|idle")
        state = self.root / "build/locks/slots.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"slots": {"2": {"pid": int(pid), "want": 4, "jobs": 4, "budget_gib": 6.0,
                                                      "kind": "full", "admitted": 1, "frozen": False, "scope": ""}},
                                     "swap_base_gib": 1e9}))
        self.assertIn("ok ", self.run_cli("poll", "--slot", "2", "--jobs", "4", script=SLOTS).stdout)
        self.run_cli("update", "--slot", "2", "--jobs", "6", "--scope", "s2", script=SLOTS)
        self.assertEqual(json.loads(self.run_cli("status", "--json", script=SLOTS).stdout)["slots"]["2"]["jobs"], 6)
        self.assertIn("slot 2", self.run_cli("status", script=SLOTS).stdout)
        self.run_cli("release", "--slot", "2", script=SLOTS)
        self.assertEqual(json.loads(self.run_cli("status", "--json", script=SLOTS).stdout)["slots"], {})


if __name__ == "__main__":
    unittest.main()
