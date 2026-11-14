# SPDX-License-Identifier: AGPL-3.0-only
"""desktop-macos.yml signs only on main (the macos-signing environment admits no other ref): elsewhere the sign job
is skipped by its condition and the build leaves a "Signing skipped" notice, so release-candidate runs pass and
r1-auto-macos can gate them. The r1 old-profile upload runs only when its check ran."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
VERIFY = "Verify dmg (app name, bundle id, architecture, icons, layout, Vietnamese resources)"

spec = importlib.util.spec_from_file_location("check_workflows", ROOT / "scripts" / "check-workflows.py")
CHECK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)


def read(name):
    return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=CHECK.WorkflowLoader)


def step(workflow, job, name):
    return next(s for s in workflow["jobs"][job]["steps"] if s.get("name") == name)


class MacosSigningMainOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def check(self, workflow, name="desktop-macos.yml"):
        path = Path(self.tmp.name) / name
        path.write_text(yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8")
        return CHECK.check_workflow(path, root=ROOT)

    def test_sign_job_runs_only_on_main(self):
        workflow = read("desktop-macos.yml")
        self.assertEqual([], self.check(workflow))
        self.assertIn("github.ref == 'refs/heads/main'", workflow["jobs"]["sign"]["if"])
        every_ref = copy.deepcopy(workflow)
        every_ref["jobs"]["sign"]["if"] = "${{ inputs.mode == 'full' }}"
        self.assertTrue(self.check(every_ref))

    def test_skipped_signing_is_announced(self):
        workflow = read("desktop-macos.yml")
        run = step(workflow, "build", VERIFY)["run"]
        self.assertIn('if [ "$GITHUB_REF" != refs/heads/main ]', run)
        self.assertIn("::notice title=Signing skipped::", run)
        silent = copy.deepcopy(workflow)
        step(silent, "build", VERIFY)["run"] = run.replace("Signing skipped", "x")
        self.assertTrue(self.check(silent))

    def test_old_profile_upload_only_after_its_check_ran(self):
        job = read("r1-auto-macos.yml")["jobs"]["old-profile"]
        ids = [s.get("id") for s in job["steps"]]
        self.assertIn("old_profile", ids)
        upload = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@"))
        self.assertEqual(upload["if"], "${{ always() && steps.old_profile.outcome != 'skipped' }}")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        self.assertGreater(job["steps"].index(upload), ids.index("old_profile"))


if __name__ == "__main__":
    unittest.main()
