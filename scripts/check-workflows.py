#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate the repository's bounded, pinned, explicitly guarded CI contracts."""
import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under python -I, which leaves it out
from workflow_build_rules import (SIGNING_JOB, SIGNING_ENVIRONMENT, SIGNING_GATE, check_signing_job,  # noqa: E402
                                  check_macos_build, check_windows_build, check_linux_build, check_release,
                                  LINUX_SIGNING_ENVIRONMENT, check_linux_signing_job)

PINS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/setup-node": "49933ea5288caeca8642d1e84afbd3f7d6820020",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",  # v4.3.0
    "actions/cache/restore": "0057852bfaa89a56745cba8c7296529d2fc39830",  # v4.3.0
    "actions/cache/save": "0057852bfaa89a56745cba8c7296529d2fc39830",  # v4.3.0
}
REQUIRED = {"quality.yml", "desktop-linux.yml", "desktop-windows.yml", "desktop-macos.yml", "release.yml"}
RELEASE_PERMISSIONS = {"contents": "write", "actions": "read"}
# The only jobs that may read secrets: macOS and Linux signing behind a reviewable environment, in the build
# workflows and in the signing probe. Each may be skipped only by its own job condition.
SIGNING_JOBS = {("desktop-macos.yml", SIGNING_JOB): "${{ inputs.mode == 'full' }}",
                ("macos-signature-probe.yml", SIGNING_JOB): "${{ inputs.sign }}",
                ("desktop-linux.yml", SIGNING_JOB): "${{ inputs.mode == 'full' }}"}
SIGNING_ENVIRONMENTS = {"desktop-linux.yml": LINUX_SIGNING_ENVIRONMENT}
CYGWIN_SHELL = "C:/cygwin64/bin/bash.exe"
SCRIPT = re.compile(r"\bscripts/[\w./-]+\.(?:py|sh|ps1|mjs|js)\b")


class WorkflowLoader(yaml.SafeLoader):
    """Keep GitHub's `on` as text while preserving true/false booleans."""


WorkflowLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries if tag != "tag:yaml.org,2002:bool"]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(true|false)$", re.I), list("tTfF"))


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def active_lines(run):
    return [line.strip() for line in run.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def check_workflow(path, root=ROOT):
    text = path.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=WorkflowLoader)
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(f"{path.name}: {message}")

    if not isinstance(workflow, dict):
        return [f"{path.name}: workflow must be a mapping"]
    events = workflow.get("on", {})
    quality = path.name == "quality.yml"
    require(isinstance(events, dict), "triggers must be an explicit mapping")
    if isinstance(events, dict):
        expected = {"push", "pull_request"} if quality else {"workflow_dispatch"}
        require(set(events) == expected, f"triggers must be {sorted(expected)}")
        if quality:
            require(events.get("push") == {"branches": ["main"]}, "push must cover all changes on main")
            require(events.get("pull_request") in (None, {}), "pull_request must not skip paths or branches")
    require(workflow.get("permissions") == {"contents": "read"}, "permissions must be contents: read only")
    concurrency = workflow.get("concurrency", {})
    require(isinstance(concurrency, dict) and bool(concurrency.get("group")), "concurrency group is required")
    require(isinstance(concurrency, dict) and concurrency.get("cancel-in-progress") is quality,
            "concurrency cancellation must be true for quality, false for desktop")
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict) or not jobs:
        return errors + [f"{path.name}: no jobs declared"]
    all_steps = []
    for name, job in jobs.items():
        timeout = job.get("timeout-minutes")
        require(type(timeout) is int and 1 <= timeout <= 360, f"{name}: timeout must be 1..360 minutes")
        # Only the manually dispatched release jobs may write, and only releases plus reading run artifacts:
        # the public release and the draft "test-builds" release for maintainers.
        writers = {("release.yml", "publish"), ("test-build-share.yml", "share")}
        # The tab and spell probes only read a run artifact (gh run download needs actions: read).
        readers = {("macos-tab-probe.yml", "probe"), ("macos-bundle-seal-probe.yml", "probe"), ("macos-spell-probe.yml", "probe"), ("macos-app-launchers-probe.yml", "probe"), ("macos-save-replace-probe.yml", "probe"), ("windows-smoke.yml", "smoke"), ("r1-auto-windows.yml", "r1"), ("r1-auto-macos.yml", "r1"), ("r1-auto-macos.yml", "old-profile"), ("startup-timing.yml", "timing")}
        allowed = RELEASE_PERMISSIONS if (path.name, name) in writers else \
            {"contents": "read", "actions": "read"} if (path.name, name) in readers else {"contents": "read"}
        require(job.get("permissions", {"contents": "read"}) == allowed, f"{name}: permissions escalation")
        require(not job.get("continue-on-error"), f"{name}: continue-on-error masks failures")
        signing = (path.name, name) in SIGNING_JOBS
        # A signing job alone may be skipped by its declared condition; every other job always runs.
        require("if" not in job or (signing and job["if"] == SIGNING_JOBS[(path.name, name)]),
                f"{name}: required job must not be conditional")
        require("environment" not in job or (signing and job["environment"] == SIGNING_ENVIRONMENTS.get(path.name, SIGNING_ENVIRONMENT)),
                f"{name}: only a signing job may use its signing deployment environment")
        steps = job.get("steps", [])
        require(isinstance(steps, list) and bool(steps), f"{name}: executable steps required")
        for step in steps:
            all_steps.append(step)
            require(not step.get("continue-on-error"), f"{name}: continue-on-error masks failures")
            if "secrets." in yaml.safe_dump(step):
                # Secrets only in the signing job: its gate step, or steps that run after the gate passed.
                gated = step.get("id") == "gate" or SIGNING_GATE in str(step.get("if", ""))
                require(signing and gated, f"{name}: secrets only in the gated signing steps")
            if "uses" in step:
                action, _, pin = step["uses"].partition("@")
                require(bool(re.fullmatch(r"[0-9a-f]{40}", pin)), f"{name}: action must use a full SHA")
                require(action not in PINS or pin == PINS[action], f"{name}: action differs from reviewed pin")
                if action == "actions/upload-artifact":
                    options = step.get("with", {})
                    require(options.get("if-no-files-found") == "error", "missing artifacts must fail")
                    days = options.get("retention-days")
                    require(type(days) is int and 1 <= days <= 14, "artifact retention must be 1..14 days")
                if action == "actions/checkout":
                    require(step.get("with", {}).get("persist-credentials") is False, "checkout must not persist credentials")
            if "run" in step:
                require(step.get("shell") == "bash", f"{name}: use explicit bash for fail-fast pipelines")
                lines = active_lines(step["run"])
                substantive = [line for line in lines if not line.startswith("set ")]
                require(bool(substantive), f"{name}: empty run step")
                only_output = substantive and all(re.match(r"^(echo|printf|Write-Host|Write-Output)\b", line, re.I)
                                                 for line in substantive)
                require(not only_output, f"{name}: output-only step is not a check (echo success)")
                require(not re.search(r"\|\|\s*(true|exit\s+0)\b", "\n".join(lines)), f"{name}: masked command failure")
    for script in set(SCRIPT.findall(text)):
        require(script == "scripts/build-linux.sh" or (root / script).is_file(), f"referenced script missing: {script}")
    runs = [step for step in all_steps if "run" in step]
    if quality:
        require(any(step["run"].strip() == "bash scripts/ci-quality.sh" or
                    re.search(r"^\s*bash scripts/ci-quality\.sh\b", step["run"], re.M) for step in runs),
                "quality must execute scripts/ci-quality.sh")
        require(all("if" not in step for step in runs), "quality commands must not be skipped")
    elif path.name == "desktop-macos.yml":
        check_macos_build(jobs, events, require)
    elif path.name == "macos-signature-probe.yml":
        require(set(jobs) == {"probe", SIGNING_JOB}, "the probe needs exactly a probe job and a signing job")
    elif path.name == "desktop-windows.yml":
        check_windows_build(jobs, events, runs, all_steps, require)
    elif path.name == "desktop-linux.yml":
        check_linux_build(jobs, events, runs, all_steps, require)
    if path.name == "release.yml":
        check_release(events, all_steps, require)
    for (workflow_name, job_name) in SIGNING_JOBS:
        if path.name == workflow_name:
            (check_linux_signing_job if path.name == "desktop-linux.yml" else check_signing_job)(jobs.get(job_name, {}), require)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / ".github/workflows")
    args = parser.parse_args(argv)
    paths = sorted({*args.directory.glob("*.yml"), *args.directory.glob("*.yaml")})
    errors = [f"missing required workflow: {name}" for name in sorted(REQUIRED - {p.name for p in paths})]
    for path in paths:
        try:
            errors.extend(check_workflow(path))
        except (OSError, ValueError, TypeError, AttributeError, KeyError, yaml.YAMLError) as error:
            errors.append(f"{path.name}: invalid workflow: {error}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"ok: {len(paths)} workflows validated (structure only; native builds remain unverified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
