# SPDX-License-Identifier: AGPL-3.0-only
"""Contracts of the native build, signing and release workflows, for scripts/check-workflows.py.

Each rule takes the workflow's jobs, its steps and `require(condition, message)`, which records a failure."""
import re

SIGNING_JOB, SIGNING_ENVIRONMENT = "sign", "macos-signing"
LINUX_SIGNING_ENVIRONMENT = "linux-signing"
SIGNING_GATE = "steps.gate.outputs.enabled == 'true'"
MACOS_STAGES = ["probe", "free-disk", "tools", "extract", "patch", "configure", "fetch", "build", "collect", "verify"]


def dispatch_inputs(events):
    """The workflow_dispatch inputs of a workflow's triggers ({} when there are none)."""
    return events.get("workflow_dispatch", {}).get("inputs", {}) if isinstance(events, dict) else {}


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


def check_macos_build(jobs, events, require):
    """desktop-macos.yml: native arm64 and x86_64 builds in fixed stages, then the signing job."""
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
    modes = dispatch_inputs(events).get("mode", {})
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
    require('title=Signing skipped::' in text_runs and 'refs/heads/main' in text_runs,
            "off main the build must leave a 'Signing skipped' notice (signing runs on main only)")


def check_windows_build(jobs, events, runs, all_steps, require):
    """desktop-windows.yml: one hosted Windows job that fetches, patches and builds within a time budget."""
    require(len(jobs) == 1, "Windows trial must be a single job on one runner")
    job = next(iter(jobs.values()))
    require(str(job.get("runs-on", "")).startswith("windows-"), "Windows trial must run on a hosted windows runner")
    require(type(job.get("timeout-minutes")) is int and job["timeout-minutes"] >= 300,
            "Windows trial needs a long timeout to measure the build")
    text_runs = "\n".join(step["run"] for step in runs)
    require("fetch-sources.py" in text_runs, "trial must download and verify pinned tarballs")
    require(all(re.search(rf'trial-build\.sh"? --{stage}\b', text_runs) for stage in ("extract", "patch", "configure", "build")),
            "trial must extract, patch, configure and build")
    modes = dispatch_inputs(events).get("mode", {})
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


def check_linux_signing_job(job, require):
    """desktop-linux.yml sign job: optional GPG signing of the .rpm/AppImage behind the linux-signing environment."""
    require(job.get("environment") == LINUX_SIGNING_ENVIRONMENT, "Linux signing must run behind the linux-signing environment")
    steps = job.get("steps", [])
    gate = [step for step in steps if step.get("id") == "gate"]
    require(len(gate) == 1 and "sign-linux-packages.sh --enabled" in gate[0].get("run", "") and "if" not in gate[0],
            "Linux signing needs one unconditional gate that skips cleanly without secrets")
    require(len(gate) == 1 and "vars.HST_LINUX_GPG_FINGERPRINT" in str(gate[0].get("env", {}).get("HST_LINUX_GPG_FINGERPRINT", "")),
            "the Linux signing gate must see HST_LINUX_GPG_FINGERPRINT, so a configured key without its secret fails")
    uploads = [step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
    require(len(uploads) == 1 and SIGNING_GATE in str(uploads[0].get("if", "")) and "success()" in str(uploads[0].get("if", ""))
            and str(uploads[0].get("with", {}).get("name", "")).startswith("hst-office-linux-deb-signed-"),
            "signed Linux packages must be uploaded once, after the gate and success")


def check_linux_build(jobs, events, runs, all_steps, require):
    """desktop-linux.yml: one hosted Ubuntu job through the ci-build.sh stages to .deb/.rpm/.AppImage, then signing."""
    require(set(jobs) == {"linux-deb", SIGNING_JOB}, "Linux needs exactly the build job linux-deb and the signing job")
    job = jobs.get("linux-deb", {})
    runs = [step for step in job.get("steps", []) if "run" in step]
    all_steps = job.get("steps", [])
    require(str(job.get("runs-on", "")).startswith("ubuntu-"), "Linux deb build must run on a hosted ubuntu runner")
    require(type(job.get("timeout-minutes")) is int and job["timeout-minutes"] >= 300,
            "Linux deb build needs a long timeout to finish the build")
    text_runs = "\n".join(step["run"] for step in runs)
    require("fetch-sources.py" in text_runs, "Linux build must download and verify pinned tarballs")
    order = re.findall(r"ci-build\.sh --([\w-]+)", text_runs)
    require(order == ["deps", "extract", "patch", "configure", "fetch", "build", "check-translations", "package",
                      "rpm-appimage"],
            "Linux build stages must follow deps/extract/patch/configure/fetch/build/check-translations/package/"
            "rpm-appimage order")
    modes = dispatch_inputs(events).get("mode", {})
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
            "the .deb/.rpm/.AppImage artifact must be uploaded once, only after a successful build")


def check_release(events, all_steps, require):
    """release.yml: a later macOS commit reaches the release only through the collector's path rule."""
    # The collector runs scripts/release/macos-commit-paths.sh against the release commit.
    inputs = dispatch_inputs(events)
    collect = [step for step in all_steps if "collect-release-assets.sh" in step.get("run", "")]
    require("macos_commit" in inputs and len(collect) == 1
            and collect[0].get("env", {}).get("MACOS_COMMIT") == "${{ inputs.macos_commit }}",
            "release must pass macos_commit to collect-release-assets.sh, which enforces the macOS-only rule")
