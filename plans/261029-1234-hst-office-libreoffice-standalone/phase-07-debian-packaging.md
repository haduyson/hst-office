# Phase 07 — Debian packaging and clean-container lifecycle

**Status:** pending; container execution BLOCKED until Docker socket access works. **Depends on:** 02/03/05/06 and any Linux-applicable 04 fix. **Parallelizable:** metadata authoring only; staging/installation serial.

## Context and requirements

Produce a real HST Office `.deb` install set built from the pinned source. Initial supported runtime is **Ubuntu 24.04 x86_64**; Debian and older Ubuntu remain untested until their ABI/runtime matrix passes. Docker is installed here, but the planning session cannot access its daemon. Do not claim a clean-container result from a host-only check.

## Exact files

- Create `packaging/linux/package-manifest.json`, `packaging/linux/runtime-dependencies.txt`, `packaging/linux/hst-office`, `hst-writer`, `hst-sheets`, `hst-slides` (launcher scripts), `packaging/linux/container-smoke.Dockerfile`, `packaging/linux/clean-container.sh`.
- Create `scripts/check-deb.py`, `scripts/test-deb-container.sh`, `scripts/write-release-manifest.py`, `tests/packaging/test_package_manifest.py`, `tests/fixtures/packaging/sentinels.json`.
- Coordinator modifies `build-config/linux-x86_64.conf`, `scripts/build-linux.sh`, `patches/libreoffice/hst-product-branding.patch` and `LICENSES/component-inventory.json` as needed. Generated artifacts: `dist/linux/*.deb`, `SHA256SUMS`, `release-manifest.json`, and corresponding-source manifest/archive.

## Steps

1. Use the pinned upstream install-set machinery with **`--with-package-format=deb --enable-epm`**, resolving a supported installed EPM or `--with-epm=internal` and counting its footprint. Verify the actual target in `Makefile.in`/`instsetoo_native` before wiring `build-linux.sh --package`. A multi-package suite is acceptable; provide a complete offline install set and coherent dependency/install instructions, not one mislabeled partial `.deb`.
2. Set HST package identifiers, Debian-compliant version/revision (candidate `26.8.1.1-1hst1`, separate from marketing version), vendor, paths, icons, desktop metadata and MIME declarations. Patch hardcoded prefixes/download names/updater URL in `instsetoo_native/util/openoffice.lst.in`. Install under `/opt/hst-office/`, expose `/usr/bin/hst-office`, `hst-writer`, `hst-sheets`, `hst-slides`; verify 02's bootstrap patch resolves direct and launcher invocations to `~/.config/hst-office/4`. Compute actual library dependencies (including matching Python/UNO runtime); no accidental dependency on a preinstalled LibreOffice engine.
3. Stage bundled OXT through the verified native deployment path, templates, autotext, configuration, credits, generated upstream licenses and component notices. First launch as a normal user with read-only installation must discover all features. Include a manifest of every package/component and hashes; all components must have HST product identity.
4. Build a clean Ubuntu 24.04 container from a pinned image digest, install declared runtime dependencies and the complete local `.deb` set, then disable networking for runtime tests. Use a non-root desktop user, isolated home and Xvfb/DBus. The test must assert no preinstalled office engine and identify the installed HST executable/package owner.
5. Test install → launch all modules → create/save documents → upgrade/reinstall → uninstall → purge → reinstall. Create sentinel documents, personal templates, profile preferences and unrelated upstream-profile files; compare hashes before/after. Remove only package-owned files, never user homes/Documents/profiles. Verify no dangling launchers or background processes and no forced replacement of user's default file associations. Upgrade verification needs two real HST revisions built with this pipeline; record NOT RUN until available, not a fabricated version.
6. Check relocation paths, missing shared libraries, extension registration, locale resources and package ordering. Include exact HST Git SHA, upstream pin, patches/config/dependency versions, source availability and checksums with the artifacts. No automatic public release/tag is part of this planning task.

## Validation commands

Now:

```bash
docker version
docker info --format '{{.DockerRootDir}}'
```

After implementation and daemon access:

```bash
python3 -m unittest discover -s tests/packaging -p 'test_*.py'
python3 scripts/measure-job.py --min-free-gib 10 --stop-free-gib 12 --json build/metrics/linux-package.json -- bash scripts/build-linux.sh --package
python3 scripts/check-deb.py --directory dist/linux --manifest packaging/linux/package-manifest.json
lintian dist/linux/*.deb
python3 scripts/measure-job.py --min-free-gib 10 --stop-free-gib 12 --json build/metrics/container-qa.json -- bash scripts/test-deb-container.sh --packages dist/linux --output tests/output/packaging
sha256sum -c dist/linux/SHA256SUMS
```

The container runner pins the image, checks budgets, creates named task-owned resources, runs non-root tests and cleans only its container/volumes. Fail on missing packages/tests; justified lintian exceptions must be itemized. Container DNS/download failure is a blocker; no stub PASS. Keep logs, package hash, install/uninstall output, sentinel comparisons and module screenshots.

## Risks and rollback

Package staging and Docker layers can exceed the disk envelope. Count both before building; no global prune or duplicate builder daemon. Roll back to the prior tested `.deb` set without downgrading/replacing user documents; incompatible profiles use a backed-up test profile. Version/path changes require another clean install and upgrade test.
