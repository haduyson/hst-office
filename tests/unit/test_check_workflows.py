# SPDX-License-Identifier: AGPL-3.0-only
"""Workflow contract tests use synthetic YAML mutations, not native-build evidence."""
from contextlib import redirect_stderr
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load_script("check-workflows")
PROBE = load_script("probe-runner")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.quality = yaml.load((ROOT / ".github/workflows/quality.yml").read_text(), Loader=CHECK.WorkflowLoader)

    def check(self, workflow, name="quality.yml", root=ROOT):
        path = self.directory / name
        path.write_text(yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8")
        return CHECK.check_workflow(path, root=root)

    def test_actual_repository_workflows(self):
        for name in CHECK.REQUIRED:
            with self.subTest(name=name):
                self.assertEqual(CHECK.check_workflow(ROOT / ".github/workflows" / name), [])

    def test_unquoted_on_and_booleans(self):
        parsed = yaml.load("on: {workflow_dispatch: null}\ncancel: false\n", Loader=CHECK.WorkflowLoader)
        self.assertIn("on", parsed)
        self.assertIs(parsed["cancel"], False)

    def test_duplicate_yaml_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
            yaml.load("permissions: {}\npermissions: {contents: write}\n", Loader=CHECK.WorkflowLoader)

    def test_required_workflow_missing(self):
        with redirect_stderr(io.StringIO()) as output:
            self.assertEqual(CHECK.main(["--directory", str(self.directory)]), 1)
        self.assertIn("missing required workflow", output.getvalue())

    def test_malformed_yaml_fails_cli(self):
        (self.directory / "quality.yml").write_text("jobs: [\n", encoding="utf-8")
        with redirect_stderr(io.StringIO()) as output:
            self.assertEqual(CHECK.main(["--directory", str(self.directory)]), 1)
        self.assertIn("invalid workflow", output.getvalue())

    def test_bad_quality_triggers(self):
        for events in ({"pull_request_target": None}, {"push": {"branches": ["dev"]}, "pull_request": None},
                       {"push": {"branches": ["main"]}, "pull_request": {"paths": ["scripts/**"]}}):
            with self.subTest(events=events):
                self.quality["on"] = events
                self.assertTrue(self.check(self.quality))

    def test_write_permissions_rejected_at_both_levels(self):
        for target in (self.quality, self.quality["jobs"]["quality"]):
            target["permissions"] = {"contents": "write"}
            self.assertTrue(self.check(self.quality))
            target["permissions"] = {"contents": "read"}

    def test_release_write_is_limited_to_the_publish_job(self):
        name = "release.yml"
        original = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=CHECK.WorkflowLoader)
        self.assertEqual([], self.check(original, name))
        mutations = {
            "workflow-level write": lambda w: w.update({"permissions": {"contents": "write"}}),
            "extra scope": lambda w: w["jobs"]["publish"]["permissions"].update({"packages": "write"}),
            "second writing job": lambda w: w["jobs"].update({"other": copy.deepcopy(w["jobs"]["publish"])}),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                workflow = copy.deepcopy(original)
                mutate(workflow)
                self.assertTrue(self.check(workflow, name))
        # The same job name in another workflow gets no write access.
        self.assertTrue(self.check(copy.deepcopy(original), "desktop-windows.yml"))

    def test_missing_concurrency_and_wrong_cancellation(self):
        for concurrency in ({}, {"group": "ci", "cancel-in-progress": False}):
            self.quality["concurrency"] = concurrency
            self.assertTrue(self.check(self.quality))

    def test_timeout_boundaries(self):
        for timeout in (None, 0, 361, "20", True):
            with self.subTest(timeout=timeout):
                self.quality["jobs"]["quality"]["timeout-minutes"] = timeout
                self.assertTrue(self.check(self.quality))

    def test_mutable_short_and_unreviewed_action_pins(self):
        for pin in ("v4", "main", "11bd719", "a" * 40):
            self.quality["jobs"]["quality"]["steps"][0]["uses"] = "actions/checkout@" + pin
            self.assertTrue(self.check(self.quality))

    def test_checkout_credentials_and_artifact_policy(self):
        steps = self.quality["jobs"]["quality"]["steps"]
        for step, key, value in ((steps[0], "persist-credentials", True),
                                 (steps[-1], "if-no-files-found", "warn"), (steps[-1], "retention-days", 90)):
            original = copy.deepcopy(step["with"])
            step["with"][key] = value
            self.assertTrue(self.check(self.quality))
            step["with"] = original

    def test_echo_success_and_masked_failures_rejected(self):
        for run in ("echo success", "set -e\necho 'PASS'", "python3 scripts/check-workflows.py || true"):
            self.quality["jobs"]["quality"]["steps"].append({"run": run, "shell": "bash"})
            self.assertTrue(self.check(self.quality))
            self.quality["jobs"]["quality"]["steps"].pop()

    def test_missing_script_rejected(self):
        self.quality["jobs"]["quality"]["steps"].append({"run": "python3 scripts/absent-check.py", "shell": "bash"})
        self.assertTrue(any("referenced script missing" in error for error in self.check(self.quality)))

    def test_required_checks_cannot_be_conditional_or_continue_on_error(self):
        for key, value in (("if", "false"), ("continue-on-error", True)):
            self.quality["jobs"]["quality"]["steps"][4][key] = value
            self.assertTrue(self.check(self.quality))
            del self.quality["jobs"]["quality"]["steps"][4][key]

    def test_native_guards_are_unconditional_failures_on_hosted_runners(self):
        for name in ("desktop-macos.yml",):
            original = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=CHECK.WorkflowLoader)
            mutations = (("exit", 0), ("conditional", True), ("runner", "self-hosted"), ("trigger", "push"))
            for mutation, value in mutations:
                with self.subTest(name=name, mutation=mutation):
                    workflow = copy.deepcopy(original)
                    job = workflow["jobs"]["blocked"]
                    if mutation == "exit":
                        job["steps"][0]["run"] = job["steps"][0]["run"].replace("exit 1", f"exit {value}")
                    elif mutation == "conditional":
                        job["steps"][0]["if"] = "false"
                    elif mutation == "runner":
                        job["runs-on"] = value
                    else:
                        workflow["on"][value] = None
                    self.assertTrue(self.check(workflow, name))

    def test_windows_trial_needs_budget_verification_and_unconditional_upload(self):
        name = "desktop-windows.yml"
        original = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=CHECK.WorkflowLoader)
        self.assertEqual([], self.check(original, name))
        job = original["jobs"]["windows-trial"]

        def evidence(w):
            return next(s for s in w["jobs"]["windows-trial"]["steps"] if s.get("name") == "Upload trial evidence")

        mutations = {
            "short timeout": lambda w: w["jobs"]["windows-trial"].update({"timeout-minutes": 20}),
            "linux runner": lambda w: w["jobs"]["windows-trial"].update({"runs-on": "ubuntu-latest"}),
            "no upload": lambda w: w["jobs"]["windows-trial"]["steps"].remove(evidence(w)),
            "upload not always": lambda w: evidence(w).pop("if"),
            "installer unconditional": lambda w: [s.update({"if": "${{ always() }}"})
                                                  for s in w["jobs"]["windows-trial"]["steps"]
                                                  if s.get("name") == "Upload installer"],
            "no checksum fetch": lambda w: [s.update({"run": s["run"].replace("fetch-sources.py", "true")})
                                            for s in w["jobs"]["windows-trial"]["steps"] if "run" in s],
            "no budget": lambda w: [s.update({"run": s["run"].replace("HST_BUILD_DEADLINE", "X")})
                                    for s in w["jobs"]["windows-trial"]["steps"] if "run" in s],
            "trigger": lambda w: w["on"].update({"push": None}),
        }
        self.assertTrue(job["steps"])
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                workflow = copy.deepcopy(original)
                mutate(workflow)
                self.assertTrue(self.check(workflow, name))

    def test_linux_probe_precedes_build_and_missing_linux_script_is_allowlisted(self):
        name = "desktop-linux.yml"
        workflow = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=CHECK.WorkflowLoader)
        errors = self.check(workflow, name, root=self.directory)
        self.assertTrue(any("probe-runner.py" in error for error in errors))
        self.assertFalse(any("referenced script missing: scripts/build-linux.sh" in error for error in errors))
        steps = workflow["jobs"]["probe-and-build"]["steps"]
        steps[1], steps[2] = steps[2], steps[1]
        self.assertTrue(any("first command" in error for error in self.check(workflow, name)))

    def test_resource_floors_cannot_be_lowered(self):
        config = self.directory / "linux.conf"
        config.write_text("# min_free_gib=1\n# min_ram_gib=1\n--with-parallelism=12\n")
        limits, declared = PROBE.thresholds(config, 10)
        self.assertEqual((limits["min_free_gib"], limits["min_ram_gib"], limits["min_cpu"]), (40, 16, 12))
        self.assertEqual(declared["min_free_gib"], 1)

    def test_shell_must_preserve_pipeline_failures(self):
        self.quality["jobs"]["quality"]["steps"][4]["shell"] = "sh"
        self.assertTrue(any("explicit bash" in error for error in self.check(self.quality)))

    def test_conditional_inside_native_guard_is_rejected(self):
        name = "desktop-macos.yml"
        workflow = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=CHECK.WorkflowLoader)
        step = workflow["jobs"]["blocked"]["steps"][0]
        step["run"] = "if false; then\n" + step["run"] + "fi\n"
        self.assertTrue(any("unconditionally" in error for error in self.check(workflow, name)))

    def test_resource_config_can_raise_requirements_and_reject_nan(self):
        config = self.directory / "linux.conf"
        config.write_text("# min_free_gib=80\n# min_ram_gib=32\n")
        limits, _ = PROBE.thresholds(config, 40)
        self.assertEqual((limits["min_free_gib"], limits["min_ram_gib"]), (80, 32))
        config.write_text("# min_ram_gib=nan\n")
        with self.assertRaises(ValueError):
            PROBE.thresholds(config, 40)


if __name__ == "__main__":
    unittest.main()
