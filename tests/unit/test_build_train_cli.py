# SPDX-License-Identifier: AGPL-3.0-only
"""Build train end to end through `python3 -I scripts/build-queue.py` and real dispatcher iterations
(`dispatch --once`) on a scratch origin (HST_QUEUE_REPO, no build slots, no Windows hosts): train add/status/
start/remove/wait, the train branch pushed to origin, its jobs, and the result after the builds finish."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from build_train_fixtures import GitWorld

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "scripts/build-queue.py"


class TrainCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.world = GitWorld(self.root / "git")
        (self.root / "queue").mkdir()
        (self.root / "queue/config.json").write_text(json.dumps({"windows_slots": [], "poll_seconds": 0}))
        self.env = {**os.environ, "HST_QUEUE_ROOT": str(self.root / "queue"), "HST_BUILD_ROOT": str(self.root / "b"),
                    "HST_QUEUE_REPO": str(self.world.clone), "USER": "cli-test", "GIT_TERMINAL_PROMPT": "0"}
        self.env.pop("SUDO_USER", None)

    def cli(self, *args, ok=(0,)):
        done = subprocess.run([sys.executable, "-I", str(QUEUE), *args], capture_output=True, text=True,
                              env=self.env, timeout=300, check=False)
        self.assertIn(done.returncode, ok, f"{args}: rc={done.returncode}\n{done.stdout}\n{done.stderr}")
        return done

    def finish(self, job_id):
        path = self.root / "queue/jobs" / f"{job_id}.json"
        data = json.loads(path.read_text())
        out = self.root / "queue/out" / job_id
        out.mkdir(parents=True)
        (out / "HSTOffice.deb").write_text("x")
        data.update(state="done", finished=time.time(), output=[str(out / "HSTOffice.deb")])
        path.write_text(json.dumps(data))

    def test_train_end_to_end(self):
        self.world.member("fix/a", "hst-a.patch", "sw/a.cxx")
        self.world.member("fix/b", "hst-b.patch", "sc/b.cxx")
        self.world.member("fix/c", "hst-c.patch", "sd/c.cxx")
        self.assertIn("ready at", self.cli("train", "add", "fix/a").stdout)
        self.cli("train", "add", "fix/b", "--platform", "linux")
        self.cli("train", "add", "fix/c")
        self.assertIn("removed", self.cli("train", "remove", "fix/c").stdout)
        self.assertIn("cannot ride", self.cli("train", "add", "rc/1.0.2-batch5", ok=(2,)).stderr)
        overview = self.cli("train", "status").stdout
        self.assertIn("ready     fix/a", overview)
        self.assertNotIn("fix/c", overview)

        self.cli("dispatch", "--once")   # 2 ready < 4 and nobody waited 90 min: no train yet
        self.assertNotIn("train/1.0.2-001", self.world.remote_heads())
        self.cli("train", "start", ok=(2,))   # --integrator is required
        self.assertIn("next dispatcher tick", self.cli("train", "start", "--integrator").stdout)
        tick = self.cli("dispatch", "--once").stdout
        self.assertIn("train train/1.0.2-001: started (forced)", tick)
        self.assertNotIn("train step failed", tick)
        self.assertIn("train/1.0.2-001", self.world.remote_heads())

        rec = json.loads(self.cli("train", "status", "train/1.0.2-001", "--json").stdout)
        self.assertEqual((rec["state"], [m["branch"] for m in rec["members"]]), ("building", ["fix/a", "fix/b"]))
        self.assertEqual(self.world.show(rec["sha"], "patches/libreoffice/series").splitlines(),
                         ["hst-base.patch", "hst-a.patch", "hst-b.patch"])
        branch = self.cli("train", "status", "fix/b").stdout
        self.assertIn("in-train", branch)
        self.assertIn(rec["jobs"]["linux"], branch)
        self.assertIn("timeout", self.cli("train", "wait", "fix/a", "--timeout", "0", ok=(2,)).stdout)
        listing = self.cli("list").stdout
        self.assertIn("train_1.0.2-001", listing)

        for job_id in rec["jobs"].values():
            self.finish(job_id)
        self.cli("dispatch", "--once")
        done = self.cli("train", "wait", "fix/a")
        self.assertIn("passed in train/1.0.2-001", done.stdout)
        self.assertIn("HSTOffice.deb", done.stdout)
        self.assertIn("passed", self.cli("train", "status", "train/1.0.2-001").stdout)


if __name__ == "__main__":
    unittest.main()
