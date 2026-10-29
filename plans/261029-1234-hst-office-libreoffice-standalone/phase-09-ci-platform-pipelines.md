# Phase 09 — Honest CI and blocked desktop platform pipelines

**Status:** pending; GitHub API connectivity/account access and native builders unverified. **Depends on:** 01; quality uses 05/06, artifacts 07/08. **Parallelizable:** quality workflow authoring; source/package integration stays serial.

## Context and requirements

Quality checks should run on push to `main`. Linux full builds are proven locally first; GitHub-hosted feasibility is a **measured experiment**, not an assumption. Current [GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) advertises 14 GB SSD for standard runners; [job limits](https://docs.github.com/en/actions/reference/limits) cap hosted jobs at six hours. Measure actual available resources, repository quota and image rather than treating advertised values as free workspace. Windows >6h is an owner-reported risk, not an HST measurement; macOS disk and interactive-session limitations are explicit.

## Exact files

- Create `.github/workflows/quality.yml`, `desktop-linux.yml`, `desktop-windows.yml`, `desktop-macos.yml`.
- Create `scripts/ci-quality.sh`, `scripts/probe-runner.py`, `scripts/check-workflows.py`, `scripts/check-doc-links.py` (port the archived generic checker with provenance), `scripts/build-windows.ps1`, `scripts/build-macos.sh`, `build-config/windows-x86_64.conf`, `build-config/macos-arm64.conf`, `build-config/macos-x86_64.conf`.
- Generate `branding/windows/hst-office.ico`, `branding/macos/hst-office.icns` from the approved assets; platform-specific module icons follow the same manifest. Modify `docs/BUILD_MATRIX.md`, `docs/BLOCKERS.md`; create `docs/CI.md`. Do not add a public release workflow until release authority and tested artifact promotion are defined.

## Steps

1. Quality: pin actions to reviewed SHAs, minimum `contents: read`, bounded timeouts/concurrency/artifact retention. Run actual Python logic tests, asset regeneration, XML/OXT/template structural checks, license/source manifests, docs links and workflow lint. Full UNO/template generation requires the exact HST runtime; lightweight jobs must report which scope ran, never install distro LibreOffice and call it the HST engine. Avoid untrusted jobs on the VPS builder.
2. Linux manual workflow: probe CPU/RAM/free bytes/filesystems/tool versions/quota, compare projected peak from local measurements to the 10 GiB reserve and job limit. If safe, run measured fetch/configure/sample and then a complete cold build/package/QA before declaring full-build feasibility. Sample-build extrapolation alone is not PASS. If preflight fails, retain resource evidence and report BLOCKED without downloading a doomed source tree.
3. Use the same `build-linux.sh` and monitored source lock on a protected self-hosted VPS runner when it is available; no duplicate build system. Scope runner access to trusted main/manual execution, serialize heavy jobs and clean only job-owned data. Cache keyed source/compiler/config/patch state with capped size; measure cold/warm behavior. Do not rely on unlimited cache/artifact capacity or billing assumptions.
4. Prepare Windows/macOS config and entrypoint contracts using pinned upstream instructions. Windows inventory covers supported Visual Studio/Windows SDK/Cygwin or upstream-required shell, packaging, signing and x86_64 runtime. macOS inventories supported Xcode/SDK and arm64/x86_64 separately, .app naming/bundle IDs/icons, numeric package version, `.dmg/.pkg`, signing/notarization and GUI testing. Record exact versions and unresolved source commands; Linux syntax checks are not native validation.
5. Until machines exist, both desktop workflows are **manual-only explicit blockers**: a short hosted preflight job exits nonzero with the missing builder/toolchain/signing information; do not queue forever on nonexistent self-hosted labels or produce dummy artifacts. Guarded build entrypoints also fail with actionable requirements on the wrong platform. Replace blockers with real build/install/QA jobs only when a native machine exists. Unsigned internal tests and publicly signed releases have distinct gates.
6. Upload only artifacts actually generated and validated; configure upload failure for missing artifacts. Preserve logs/metrics even after failure without masking the exit code. Record run URL and exact SHA with status; release promotion must re-use tested hashes and corresponding-source records.

## Validation commands

After scripts/workflows exist; network-dependent commands require restored GitHub access:

```bash
bash scripts/ci-quality.sh
python3 scripts/check-workflows.py --directory .github/workflows
python3 scripts/probe-runner.py --min-free-gib 10 --output build/metrics/runner-probe.json
gh workflow run desktop-linux.yml --ref main
gh run list --workflow desktop-linux.yml --limit 5
```

Follow the actual returned run ID with `gh run watch`/`gh run view`; write the exact URL/SHA/result to `docs/CI.md`. Verify Windows/macOS blocker workflows and wrong-platform entrypoints fail nonzero; do not count the expected failure as a successful desktop build. Shell/PowerShell/YAML lint are limited to syntax/contracts and labeled accordingly.

## Risks and rollback

Free hosted runners may fail disk/time checks before compilation; that is a measured feasibility result. Keep quality CI useful while full builds use the measured VPS. Disable only the faulty workflow trigger on regression, retain failed logs, and never add `continue-on-error` to turn required build/QA failures green. No signing credentials in repository/artifacts/logs.
