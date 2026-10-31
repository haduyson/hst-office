#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate the repository's bounded, pinned, explicitly guarded CI contracts."""
import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
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
# The only jobs that may read secrets: macOS signing behind a reviewable environment, in the build
# workflow and in the signing probe. Each may be skipped only by its own job condition.
SIGNING_JOB, SIGNING_ENVIRONMENT = "sign", "macos-signing"
SIGNING_JOBS = {("desktop-macos.yml", SIGNING_JOB): "${{ inputs.mode == 'full' }}",
                ("macos-signature-probe.yml", SIGNING_JOB): "${{ inputs.sign }}"}
SIGNING_GATE = "steps.gate.outputs.enabled == 'true'"
MACOS_STAGES = ["probe", "free-disk", "tools", "extract", "patch", "configure", "fetch", "build", "collect", "verify"]
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


def check_signing_job(job, require):
    """Rules shared by every job that may read the macOS signing secrets."""
    require(job.get("environment") == SIGNING_ENVIRONMENT, "signing must run behind the macos-signing environment")
    steps = job.get("steps", [])
    gate = [step for step in steps if step.get("id") == "gate"]
    require(len(gate) == 1 and "sign-notarize.sh --enabled" in gate[0].get("run", "") and "if" not in gate[0],
            "signing needs one unconditional gate that skips cleanly without secrets")
    cleanup = [step for step in steps if "sign-notarize.sh --cleanup" in step.get("run", "")]
    require(len(cleanup) == 1 and "always()" in str(cleanup[0].get("if", "")),
            "the temporary keychain must be deleted even when signing fails")
    uploads = [step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
    require(all(SIGNING_GATE in str(step.get("if", "")) and "success()" in str(step.get("if", "")) for step in uploads),
            "signed dmg upload must depend on the gate and success")


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
        # The tab probe only reads a run artifact (gh run download needs actions: read).
        readers = {("macos-tab-probe.yml", "probe")}
        allowed = RELEASE_PERMISSIONS if (path.name, name) in writers else \
            {"contents": "read", "actions": "read"} if (path.name, name) in readers else {"contents": "read"}
        require(job.get("permissions", {"contents": "read"}) == allowed, f"{name}: permissions escalation")
        require(not job.get("continue-on-error"), f"{name}: continue-on-error masks failures")
        signing = (path.name, name) in SIGNING_JOBS
        # A signing job alone may be skipped by its declared condition; every other job always runs.
        require("if" not in job or (signing and job["if"] == SIGNING_JOBS[(path.name, name)]),
                f"{name}: required job must not be conditional")
        require("environment" not in job or (signing and job["environment"] == SIGNING_ENVIRONMENT),
                f"{name}: only the macOS signing job may use a deployment environment")
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
        require(set(jobs) == {"build", SIGNING_JOB}, "macOS needs exactly a build job and a signing job")
        build_job, sign_job = jobs.get("build", {}), jobs.get(SIGNING_JOB, {})
        matrix = build_job.get("strategy", {}).get("matrix", {}).get("include", [])
        require(sorted(entry.get("arch", "") for entry in matrix) == ["arm64", "x86_64"]
                and all(str(entry.get("runner", "")).startswith("macos-") for entry in matrix)
                and build_job.get("runs-on") == "${{ matrix.runner }}",
                "macOS build must run natively on hosted macos-* runners for arm64 and x86_64")
        require(type(build_job.get("timeout-minutes")) is int and build_job["timeout-minutes"] >= 300,
                "macOS build needs a long timeout to finish the build")
        build_steps = build_job.get("steps", [])
        text_runs = "\n".join(step["run"] for step in build_steps if "run" in step)
        require("fetch-sources.py" in text_runs, "macOS build must download and verify pinned tarballs")
        require(re.findall(r"trial-build\.sh --([\w-]+)", text_runs) == MACOS_STAGES,
                "macOS build stages must follow " + "/".join(MACOS_STAGES))
        modes = events.get("workflow_dispatch", {}).get("inputs", {}).get("mode", {}) if isinstance(events, dict) else {}
        require(modes.get("options") == ["preflight", "full"] and modes.get("default") == "preflight",
                "mode input must offer preflight (default) and full")
        build = [step for step in build_steps if "trial-build.sh --build" in step.get("run", "")]
        require(len(build) == 1 and "full" in str(build[0].get("if", "")) and "HST_BUILD_DEADLINE" in build[0]["run"],
                "build step must run only in full mode with a time budget")
        uploads = [step for step in build_steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
        evidence = [step for step in uploads if "artifacts" in str(step.get("with", {}).get("path", ""))]
        require(len(evidence) == 1 and "always()" in str(evidence[0].get("if", "")),
                "macOS build must upload evidence even when earlier steps fail")
        dmgs = [step for step in uploads if step not in evidence]
        require(len(dmgs) == 1 and "success()" in str(dmgs[0].get("if", ""))
                and str(dmgs[0].get("with", {}).get("name", "")).startswith("hst-office-macos-${{ matrix.arch }}-dmg-"),
                "the unsigned dmg must be uploaded once, only after a successful build")
        require(sign_job.get("needs") == "build", "signing must follow the build")
    elif path.name == "macos-signature-probe.yml":
        require(set(jobs) == {"probe", SIGNING_JOB}, "the probe needs exactly a probe job and a signing job")
    elif path.name == "desktop-windows.yml":
        require(len(jobs) == 1, "Windows trial must be a single job on one runner")
        job = next(iter(jobs.values()))
        require(str(job.get("runs-on", "")).startswith("windows-"), "Windows trial must run on a hosted windows runner")
        require(type(job.get("timeout-minutes")) is int and job["timeout-minutes"] >= 300,
                "Windows trial needs a long timeout to measure the build")
        text_runs = "\n".join(step["run"] for step in runs)
        require("fetch-sources.py" in text_runs, "trial must download and verify pinned tarballs")
        require(all(re.search(rf'trial-build\.sh"? --{stage}\b', text_runs) for stage in ("extract", "patch", "configure", "build")),
                "trial must extract, patch, configure and build")
        modes = events.get("workflow_dispatch", {}).get("inputs", {}).get("mode", {}) if isinstance(events, dict) else {}
        require(modes.get("options") == ["preflight", "full"] and modes.get("default") == "preflight",
                "mode input must offer preflight (default) and full")
        build = [step for step in all_steps if "trial-build.sh" in step.get("run", "") and "--build" in step["run"]]
        require(len(build) == 1 and "full" in str(build[0].get("if", "")), "build step must run only in full mode")
        require("HST_BUILD_DEADLINE" in text_runs, "build step must carry a time budget")
        uploads = [step for step in all_steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
        evidence = [step for step in uploads if "artifacts" in str(step.get("with", {}).get("path", ""))]
        require(len(evidence) == 1 and "always()" in str(evidence[0].get("if", "")),
                "trial must upload artifacts even when earlier steps fail")
        # Other uploads (the built installer) only publish output of a successful build.
        require(all("success" in str(step.get("if", "")) for step in uploads if step not in evidence),
                "installer upload must depend on a successful build")
    elif path.name == "desktop-linux.yml":
        require(len(jobs) == 1, "Linux deb build must be a single job on one runner")
        job = next(iter(jobs.values()))
        require(str(job.get("runs-on", "")).startswith("ubuntu-"), "Linux deb build must run on a hosted ubuntu runner")
        require(type(job.get("timeout-minutes")) is int and job["timeout-minutes"] >= 300,
                "Linux deb build needs a long timeout to finish the build")
        text_runs = "\n".join(step["run"] for step in runs)
        require("fetch-sources.py" in text_runs, "Linux build must download and verify pinned tarballs")
        order = re.findall(r"ci-build\.sh --(\w+)", text_runs)
        require(order == ["deps", "extract", "patch", "configure", "fetch", "build", "package"],
                "Linux build stages must follow deps/extract/patch/configure/fetch/build/package order")
        modes = events.get("workflow_dispatch", {}).get("inputs", {}).get("mode", {}) if isinstance(events, dict) else {}
        require(sorted(modes.get("options") or []) == ["full", "preflight"], "mode input must offer full and preflight")
        build = [step for step in runs if "ci-build.sh --build" in step["run"]]
        require(len(build) == 1 and "full" in str(build[0].get("if", "")), "build step must run only in full mode")
        require(len(build) == 1 and "HST_BUILD_DEADLINE" in build[0]["run"], "build step must carry a time budget")
        uploads = [step for step in all_steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
        evidence = [step for step in uploads if "artifacts" in str(step.get("with", {}).get("path", ""))]
        require(len(evidence) == 1 and "always()" in str(evidence[0].get("if", "")),
                "Linux build must upload evidence even when earlier steps fail")
        debs = [step for step in uploads if step not in evidence]
        require(len(debs) == 1 and "success" in str(debs[0].get("if", ""))
                and str(debs[0].get("with", {}).get("name", "")).startswith("hst-office-linux-deb-"),
                "the .deb artifact must be uploaded once, only after a successful build")
    if path.name == "release.yml":
        # A later macOS commit is allowed only through the collector, which runs the path rule
        # (scripts/release/macos-commit-paths.sh) against the release commit.
        inputs = events.get("workflow_dispatch", {}).get("inputs", {}) if isinstance(events, dict) else {}
        collect = [step for step in all_steps if "collect-release-assets.sh" in step.get("run", "")]
        require("macos_commit" in inputs and len(collect) == 1
                and collect[0].get("env", {}).get("MACOS_COMMIT") == "${{ inputs.macos_commit }}",
                "release must pass macos_commit to collect-release-assets.sh, which enforces the macOS-only rule")
    for (workflow_name, job_name) in SIGNING_JOBS:
        if path.name == workflow_name:
            check_signing_job(jobs.get(job_name, {}), require)
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
