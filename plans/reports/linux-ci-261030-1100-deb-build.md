# Linux CI: HST Office .deb build on a GitHub-hosted runner

Date: 2026-10-30. Workflow: `.github/workflows/desktop-linux.yml`. Green run: **41009617263** (commit `ad7e964`).

## What changed
- `desktop-linux.yml`: single job on `ubuntu-24.04` (= ubuntu-latest), timeout 355 min, input `mode` = `full` (default) | `preflight`. Steps: free disk, `--deps`, `fetch-sources.py` (pinned + sha256), stage branding, `--extract`, `--patch`, `--configure`, `--fetch`, `--build` (budget = job start + 330 min), `--package`; summary + evidence upload `if: always()`; `.deb` upload only when the package step succeeded.
- `scripts/linux/ci-build.sh` (new): phases as in the Windows trial. Builds in `/mnt/hst`, system-only PATH, substitutes `--with-branding` and `--with-parallelism=$(nproc)` from `build-config/linux-x86_64.conf`, exports `HST_REPO_ROOT` and `HST_ICON_DIR` (tree is outside the checkout), runs apply-patches + l10n merge/overrides + `scripts/brand/apply-icon-overrides.py`. `--build` stops make and fails on budget or < 3 GiB free. `--package` refuses `*_witherror`, writes `HSTOffice_<ver>_Linux_x86-64_deb.tar.gz` (folder of .deb + inner SHA256SUMS) and outer `SHA256SUMS`.
- `scripts/linux/free-runner-disk.sh` (new), `scripts/linux/preflight-local.sh` (new; shellcheck, bash -n, CRLF, actionlint; wired into `ci-quality.sh`).
- `scripts/windows/summarize-trial.py`: optional `--title`, `--installer-glob` (Windows defaults unchanged; key `msi_found` -> `installers_found`, no consumers).
- `scripts/check-workflows.py` Linux rules replaced (single ubuntu job, timeout >= 300, pinned fetch, stage order deps..package, mode input, build only in full mode with `HST_BUILD_DEADLINE`, evidence `always()`, one `hst-office-linux-deb-*` upload gated on success); `tests/unit/test_check_workflows.py` mutation test for them. Probe/measure-job no longer in the CI workflow (their floors — 40 GiB, 16 GiB available RAM, CPU = parallelism 12 — cannot pass on a 4 vCPU/16 GiB runner); they remain for the local host.
- `docs/CI.md`: Linux table row + section "Linux (.deb)".

## Runs
| Run | Result | Cause / fix |
|---|---|---|
| local container (ubuntu:24.04) x3 | configure failed | `meson`/`ninja` missing (bundled harfbuzz) -> add `ninja-build`; `curl` missing in bare image -> add `curl ca-certificates`. Then deps..fetch OK. |
| 41005060296 | build failed after 37 min | sysui deb rule looked for icons at `$(SRCDIR)/../../assets/brand/icons` (= `/mnt/assets/...`) -> export `HST_ICON_DIR` (patch uses `?=`). |
| **41009617263** | **success**, 2 h 04 min total | — |

## Phase timings (run 41009617263, seconds)
free-disk 165, deps 82, fetch-sources 31, extract 30, patch 3, configure 19, fetch 158, **build 6912 (1 h 55 min, 17 843 build steps)**, package 5.

## Resources
- Runner: 4 vCPU, 15 GiB RAM, 2 GiB swap. `/` and `/mnt` are the same 145 GiB device: 86 GiB free before cleanup, 123 GiB after (cleanup frees ~37 GiB in 165 s).
- Build footprint ~9 GiB (free 117 -> 108 GiB min). Peak memory used ~4.4 GiB, swap 0 (30 s sampling). Time margin vs 330-min budget: ~3.3 h. ccache not needed.

## Artifact
- `hst-office-linux-deb-41009617263` (211 MB, retention 14 days): `HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz` + `SHA256SUMS` at the artifact root (matches release-collector contract).
- tar.gz sha256 `c3459b7f5faa6c1a563f586a35b4b00f5a280bd59f139d4a4b915118060b4c4b`, 211 MB; 38 .deb, 202 MiB unpacked — same 38 file names as `dist/linux`.
- Evidence: `linux-evidence-41009617263` (7 days).

## Verification
- Downloaded artifact: outer `sha256sum -c` OK, inner `sha256sum -c` OK.
- `tests/runtime/check-deb-install.sh` in `ubuntu:24.04`: all PASS (install 38 pkgs, launchers/icons, `hst-office` on PATH, `--version` = "HST Office 1.0.0 680(Build:1)", bundled extension, no LibreOffice UI strings, convert txt->odt->docx->pdf, coexist with distro LibreOffice, remove/purge/reinstall).
- Patch log shows `icon overrides: 77 targets, 77 updated, 0 upstream left`.
- `ci-quality.sh` 0 failures (clean worktree of HEAD + changes; the shared tree has other agents' uncommitted patch work that fails `apply-patches --check`), actionlint clean.

## Notes
- `.deb` dependencies follow Ubuntu 24.04 (glibc 2.39, distro libs from `build-dep`); older distros may not install them. Not addressed.
- `apply-icon-overrides.py` is called by the CI script directly; `scripts/build-linux.sh` does not call it yet (UI agent owns that).
- Per coordinator: no further full runs started; the controller triggers the final three-OS build.

## Unresolved questions
- Should the `.deb` target an older baseline (e.g. Ubuntu 22.04 runner) for wider glibc compatibility?
- Peak RAM is from 30 s samples; short link-time spikes may be higher (16 GiB runner still had wide margin).
