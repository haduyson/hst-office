# Phase 01 — Pin, fetch and resource-guarded Linux source build

**Status:** pending; Git/network/apt access must be checked. **Depends on:** 00. **Parallelizable:** light authoring only; one source checkout and one heavy job at a time.

## Context and requirements

The VPS has enough CPUs to overcommit its currently available RAM. Disk feasibility is unproven. Build locally from the pinned source, keep at least 10 GiB free, and measure before selecting concurrency. Do not substitute a rewrapped upstream binary.

## Exact files

- Create `build-config/linux-x86_64.conf`, `build-config/ubuntu-24.04-packages.txt`, `build-config/toolchain-lock.json`, `scripts/fetch-libreoffice.py`, `scripts/build-linux.sh`, `scripts/measure-job.py`, `tests/unit/test_measure_job.py`.
- Modify `.gitignore` for `upstream/libreoffice/`, `upstream/tarballs/`, `upstream/ccache/`; modify `docs/BUILD_MATRIX.md`. Source lock belongs to 00; consume it without concurrent edits.
- Ignored working locations: `upstream/libreoffice/` (single shallow checkout, including workdir/instdir), `upstream/tarballs/`, `upstream/ccache/`, `build/metrics/`, `dist/linux/`. No second full build tree.
- Read pinned `README.md`, `configure.ac`, `autogen.sh`, `Makefile.in`, `download.lst`, `.gitmodules`, `distro-configs/LibreOfficeLinux.conf`; verify each upstream path before selecting flags.

## Steps

1. Snapshot free bytes, memory available/cgroup limits, process/port ownership, package versions and cache size. Optional authorized cleanup is limited to **our** `upstream/cache/ode/` and `upstream/cache/onlyoffice-desktopeditors-x64.tar.xz`, after verifying no process uses them. Save hashes/provenance first; no global Docker/apt/ccache pruning or user-file deletion.
2. Use a **40 GiB additional working envelope**: dependencies 4, source+git+tarballs 7, workdir 20, install/package/container staging 6, ccache 2, logs/fixtures 1 GiB. These are caps to test, not predictions. Start around 53.5 GiB free; retain 10 GiB reserve plus about 3.5 GiB contingency. Account for `/var/lib/docker` and package downloads on the same filesystem. Stop new stages if projected peak exceeds budget.
3. Port the archived `measure-job.py` as a reference only: it currently checks disk **only at launch** and `ru_maxrss` does not measure aggregate concurrent compiler RSS. Add periodic free-space/process-tree or cgroup sampling, minimum free bytes, total CPU, wall time, aggregate RSS, stage sizes and exit/signal status. Warn at 15 GiB; terminate the owned process group at 12 GiB (earlier if measured write rate needs more reserve), ensuring the 10 GiB floor. Monitor memory headroom too; cleanup handlers stop owned children.
4. Bootstrap Ubuntu dependencies with audited distro build-dependencies plus pinned-source configure checks. Seed tools: `build-essential`, `git`, `autoconf`, `automake`, `libtool`, `pkg-config`, `python3-dev`, `python3-venv`, `perl`, `bison`, `flex`, `gperf`, `ccache`, `ninja-build`, `zip`, `unzip`, `xz-utils`, `gettext`, `fakeroot`, `dpkg-dev`; GTK3/X11/DBus, fontconfig/freetype/harfbuzz, XML/security/compression dev packages resolved from configure. QA adds `xvfb`, `xauth`, `dbus-x11`, `xdotool`, `python3-pyatspi`, `python3-gi`, `poppler-utils`, `desktop-file-utils`, `lintian`. `apt-get build-dep libreoffice` needs `deb-src`; Ubuntu's older package is a dependency seed, not authority for 26.8. Lock actual package/tool versions and resolve extra checks, never disable a required feature to bypass an error.
5. Fetch only the selected tag and required companion repositories/tarballs. Verify lock hashes before extraction; retain complete source provenance and patch set for redistribution. Do not recursively clone unused history. Start optimized, without full debug symbols/LTO; preserve Python/UNO, extension support, GTK3, all three editors and required filters/media. Include `en-US` and `vi` translations. Local HST help is handled in 02; any upstream help added must fit the budget.
6. Set explicit `--with-parallelism=4` initially and ccache at **2 GiB**. Time representative compilation then linking; increase to 8/12 only if measured aggregate memory and disk leave reserve. Never blindly use `-j32`; build controller and make concurrency must agree. Set ccache keys by source/patch/compiler/config, report hit/miss stats, avoid unsafe cache sloppiness. Builds run as a dedicated non-root build user when privileges permit.
7. Produce an upstream-reference executable first for Phase 04, using `--enable-release-build` from the outset and identical compiler/optimization/features/dependencies to HST except recorded HST changes. Capture its measurements, then apply HST patches incrementally in the same checkout. Keep source/build manifests and a compact baseline artifact only within the staging cap. Require configure success, actual compilation, a versioned runnable binary and Writer/Sheets/Slides smoke before calling the build feasible.

## Validation commands

Now:

```bash
df -B1 /home/office
free -h
nproc
du -sh upstream/cache
apt-get -s build-dep libreoffice
```

After implementing these interfaces; privileged dependency installation is a separate recorded step:

```bash
python3 -m unittest discover -s tests/unit -p 'test_measure_job.py'
python3 scripts/fetch-libreoffice.py --lock upstream/libreoffice-lock.json --verify
bash scripts/build-linux.sh --preflight
python3 scripts/measure-job.py --min-free-gib 10 --stop-free-gib 12 --json build/metrics/linux-build.json -- bash scripts/build-linux.sh --build
upstream/libreoffice/instdir/program/soffice --headless --version
CCACHE_DIR=/home/office/upstream/ccache ccache --show-stats
```

`build-linux.sh` must expose `--preflight`, `--configure`, `--build` and `--package`, log the exact upstream commands, and fail on unknown configure options. Test monitor termination with a small private capped filesystem or controlled threshold; do not fill the host disk. Pass requires non-empty measured outputs and no orphaned processes. Actual upstream build/install-set targets must come from the pinned makefiles; do not claim a wrapper exists before implementing it.

## Risks and rollback

If peak source/build/install footprint cannot fit, stop and report needed space/offload with measurements. Do not delete active objects or weaken tests/features to force completion. Keep configure/log/lock evidence; remove only reproducible outputs created by the failed job. System dependency removal needs review because packages may be shared. No build feasibility promise is made until a full local build and package stage pass.
