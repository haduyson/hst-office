# Linux GUI-installable single .deb (v1.0.0-beta.3)

Commit bd5b0ce (pushed to main). New file name: **HSTOffice_1.0.0_Linux_x86-64.deb** (192 MiB, package `hst-office` 1.0.0-1).

## Approach
Upstream (EPM) only emits the 38 split debs; no monolithic target. Chosen: repack with `scripts/linux/make-single-deb.py` (python + dpkg-deb only, ~50 s with multithreaded xz).
- Data trees merged (overlap = error); Depends = union of external clauses minus inter-package ones; Conflicts+Replaces = all 38 split names (+ older stdlibs/core0x); no Provides (nothing depends on the old names, Provides+Conflicts adds risk).
- Maintainer scripts: only the desktop-integration package has any (mime/desktop/icon-cache); reused, two owners = error; postrm also `rm -rf /opt/hst-office1.0` on remove/purge (leftovers dpkg cannot know).
- Added: Section/Priority/Homepage, Maintainer `HASON TECH <lienhe@hasontech.vn>` (address needed for a well-formed field), Vietnamese Description, DEP-5 copyright, changelog, AppStream metainfo (validated), lintian overrides, md5sums.
- Dropped: `usr/lib/menu` legacy Debian menu (named distro `libreoffice-*` packages); conffile mark on a /opt file (would survive `apt remove`).
- CI/local `--package` now writes only the single .deb + SHA256SUMS (split tar.gz dropped). Artifact name unchanged: `hst-office-linux-deb-<run_id>`; collect-release-assets.sh / release.yml / check-workflows.py needed no change (copy all files, glob `*.deb`).

## Tests (all PASS, Docker ubuntu:24.04)
`tests/runtime/check-deb-install.sh [deb]`, env `INSTALL_MODE` apt | pkcon | upgrade, `IMAGE`.
- apt: install ./file.deb (installs Recommends), 32 checks: launchers, icons, bundled ext, convert txt>odt>docx>pdf, mimeinfo.cache updated, coexist with distro libreoffice, remove clean (no /opt, launchers, icons, PATH, mimeinfo entries), purge, reinstall.
- pkcon: `pkcon install-local` + `pkcon remove` (PackageKit, what App Center / GNOME Software call): PASS.
- upgrade: real beta.2 split set (from the GitHub release, 38 pkgs) installed, then single deb over it: split pkgs gone, profile + documents kept, convert works, remove clean: PASS. Note 2 old packages stay in `rc` (config-files) state; harmless, purge by `dpkg --purge`.
- Unit: tests/unit/test_make_single_deb.py (4 tests). Full tests/unit 117 OK. actionlint, check-workflows OK, shellcheck clean. Script also run as non-root (hstbuild): identical perms/ownership.
- Lintian 2.117: 0 errors. Overrides (in package): dir-or-file-in-opt, embedded-library, shared-library-is-executable (suite lives in /opt with bundled libs, as upstream). Warnings left: duplicate-font-file (87), national-encoding, command-with-path/ignores-errors/useless update-menus in upstream scripts, truetype embedding, no-manual-page, shared-library-lacks-prerequisites, initial-upload-closes-no-bugs.
- ci-quality.sh: 1 failure, not mine: check-doc-links on plans/reports/codex-ux-audit-261031-shortcuts-static.md -> tests/output/codex-ux-audit/shortcuts/static-evidence.json (other agent's report points at an ignored output file).

## Findings
- **Debian 13 (and Ubuntu 26.04) not installable**: Depends libpython3.12t64 (build links Python 3.12), unavailable there. Pre-existing since beta.2 (docs wrongly claimed Debian 13). Beta.3 notes now say Ubuntu 24.04 / Mint 22 only. Fix = build on matching distro or bundle Python.
- Debian revision fixed at `-1` (env/--revision `HST_DEB_REVISION`): installing a rebuilt 1.0.0-1 over 1.0.0-1 is a no-op in apt/App Center; bump revision for hotfix rebuilds.
- Not tested: real GUI click in App Center/gdebi (needs a desktop session); PackageKit path covers its backend.
- docs/releases/v1.0.0-beta.3.md is a draft with only the Linux item under "Điểm mới"; add other beta.3 features before release.

## Files
scripts/linux/make-single-deb.py (new), scripts/linux/ci-build.sh, scripts/build-linux.sh, tests/runtime/check-deb-install.sh, tests/unit/test_make_single_deb.py (new), docs/CI.md, docs/BUILD_MATRIX.md, docs/releases/v1.0.0-beta.3.md (new).

## For the landing page (not touched)
website/office.hasontech.vn: .htaccess `/tai/linux` -> .../releases/download/v1.0.0-beta.3/HSTOffice_1.0.0_Linux_x86-64.deb ; config.js `linuxArchive`; tai/SHA256SUMS; install steps in index.html (#cai-dat-linux): download .deb > double-click > Cài đặt, or `sudo apt install ./HSTOffice_1.0.0_Linux_x86-64.deb`.

## Unresolved
- Real beta.3 CI run (desktop-linux.yml, ~2 h) not started; script verified on local split set only.
