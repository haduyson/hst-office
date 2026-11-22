# SPDX-License-Identifier: AGPL-3.0-only
"""End to end through `python3 -I scripts/build-queue.py` on a scratch git origin (HST_QUEUE_REPO): priority cap,
superseding, the tests/docs-only refusal and its integrator override, pin/unpin and `retention`."""
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


class QueueRulesCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.world = GitWorld(self.root / "git")
        self.env = {**os.environ, "HST_QUEUE_ROOT": str(self.root / "queue"), "HST_BUILD_ROOT": str(self.root / "b"),
                    "HST_QUEUE_REPO": str(self.world.clone), "USER": "cli-test", "GIT_TERMINAL_PROMPT": "0"}
        self.env.pop("SUDO_USER", None)

    def cli(self, *args, ok=(0,)):
        done = subprocess.run([sys.executable, "-I", str(QUEUE), *args], capture_output=True, text=True,
                              env=self.env, timeout=300, check=False)
        self.assertIn(done.returncode, ok, f"{args}: rc={done.returncode}\n{done.stdout}\n{done.stderr}")
        return done

    def job_path(self, job_id):
        return self.root / "queue/jobs" / f"{job_id}.json"

    def finish(self, job_id, age=0):
        data = json.loads(self.job_path(job_id).read_text())
        out = self.root / "queue/out" / job_id
        out.mkdir(parents=True)
        (out / "HSTOffice.deb").write_bytes(b"x" * 4096)
        data.update(state="done", finished=time.time() - age, output=[str(out / "HSTOffice.deb")])
        self.job_path(job_id).write_text(json.dumps(data))

    def test_agent_rules(self):
        self.world.member("feat/x", "hst-x.patch", "sw/source/x.cxx")
        first = self.cli("submit", "--platform", "linux", "--ref", "feat/x", "--priority", "90")
        self.assertIn("capped at 50", first.stderr)
        job_id = first.stdout.strip()
        self.assertEqual(json.loads(self.job_path(job_id).read_text())["priority"], 50)

        self.world.branch("feat/x", {"sw/notes.md": "n\n", "patches/libreoffice/hst-x.patch": "changed\n"},
                          base="feat/x")
        newer = self.cli("submit", "--platform", "linux", "--ref", "feat/x")
        self.assertIn(f"cancelled queued job {job_id}", newer.stderr)
        newer_id = newer.stdout.strip()
        self.finish(newer_id)

        self.world.branch("feat/x", {"docs/x.md": "doc\n", "tests/unit/t.py": "t\n", "plans/p.md": "p\n"},
                          base="feat/x")
        refused = self.cli("submit", "--platform", "linux", "--ref", "feat/x", ok=(2,))
        self.assertIn("only changes tests/, docs/, plans/ or *.md", refused.stderr)
        self.assertIn(newer_id, refused.stderr)
        self.assertIn("reserved for the integrator",
                      self.cli("submit", "--platform", "linux", "--ref", "feat/x", "--force", ok=(2,)).stderr)
        forced = self.cli("submit", "--platform", "linux", "--ref", "feat/x", "--force", "--integrator",
                          "--priority", "99").stdout.strip()
        self.assertEqual(json.loads(self.job_path(forced).read_text())["priority"], 99)

        self.assertIn("pinned: keep", self.cli("pin", newer_id, "--reason", "keep").stdout)
        self.assertIn("unpinned", self.cli("unpin", newer_id).stdout)

    def test_retention_command_reports_the_freed_space(self):
        self.world.member("feat/gone", "hst-g.patch", "sw/source/g.cxx")
        job_id = self.cli("submit", "--platform", "linux", "--ref", "feat/gone").stdout.strip()
        self.finish(job_id, age=48 * 3600)
        data = json.loads(self.job_path(job_id).read_text())
        data["state"] = "failed"
        self.job_path(job_id).write_text(json.dumps(data))
        dry = self.cli("retention", "--dry-run").stdout
        self.assertIn(f"{job_id}", dry)
        self.assertIn("would free", dry)
        self.assertTrue((self.root / "queue/out" / job_id).exists())
        real = self.cli("retention").stdout
        self.assertIn("1 outputs, freed 0.00 GiB", real)
        self.assertFalse((self.root / "queue/out" / job_id).exists())
        self.assertTrue(json.loads(self.job_path(job_id).read_text())["output_deleted"])


if __name__ == "__main__":
    unittest.main()
