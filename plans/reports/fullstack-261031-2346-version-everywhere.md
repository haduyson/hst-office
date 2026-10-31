# Full release id everywhere (beta.4.1)

## Release id
- data/hst/release.json now "1.0.0-beta.4.1". SemVer regex in update_logic accepts 4-part pre-release; precedence verified (beta.4 < beta.4.1 < beta.5 < beta.10 < rc < final). No need for "beta.5".
- scripts/write-hst-version.py: reads release.json (core must equal /VERSION), exports HST_RELEASE, HST_VERSION_BUILD; header gets HST_RELEASE, HST_VERSION_BUILD, HST_FILE_VERSION. Build number: beta.N[.M] = N*100+M (beta.4 = 400, beta.4.1 = 401), rc = 5000+..., final = 10000; other ids fail the build loudly.

## Names (give to the website session)
- HSTOffice_1.0.0-beta.4.1_Win_x86-64_en-US_vi.msi
- HSTOffice_1.0.0-beta.4.1_Linux_x86-64.deb
- HSTOffice_1.0.0-beta.4.1_macOS_arm64.dmg
- HSTOffice_1.0.0-beta.4.1_macOS_x86_64.dmg
- Manifest URL dir: tai/1.0.0-beta.4.1/<name>. Tag v1.0.0-beta.4.1 (release.yml tag regex accepts it).

## Per OS
| OS | Result |
|---|---|
| Windows | CI collect step renames the installer output to HSTOffice_<release>_... (regex on the leading version, asserts final name). MSI ProductVersion 1.0.0.401 (trial-build.sh makes PACKAGEVERSION 4-part; was 1.0.0.1; Programs and Features DisplayVersion = ProductVersion). default.rc (in hst-copyright.patch): FILEVERSION/PRODUCTVERSION 1,0,0,401; string FileVersion "1.0.0.401", ProductVersion "1.0.0-beta.4.1". Applies to soffice.exe and all DLLs/EXEs using default.rc. |
| Linux | File HSTOffice_1.0.0-beta.4.1_Linux_x86-64.deb. Version `1:1.0.0~beta.4.1-1`. AppStream `<release version="1.0.0-beta.4.1" type="development">`. |
| macOS | dmg named with release id. Info.plist (patched at configure, before make/sign): CFBundleShortVersionString 1.0.0, CFBundleVersion 401, CFBundleGetInfoString "HST Office 1.0.0-beta.4.1"; NSHumanReadableCopyright unchanged. do_verify now FAILs if any of the three differ. |
| About / --version | hst-version.patch: `1.0.0-beta.4.1 (<arch>)`, `soffice --version` prints the release id. |

## Linux ordering (why the epoch)
`1.0.0~beta4.1-1` is impossible: `~` sorts before the end, so it is LOWER than the published beta.4 `1.0.0-2` (dpkg --compare-versions confirmed FAIL). Only fix: epoch. Chain verified with dpkg:
1.0.0-2 < 1:1.0.0~beta.4.1-1 < 1:1.0.0~beta.5-1 < 1:1.0.0~beta.10-1 < 1:1.0.0~rc.1-1 < 1:1.0.0-1 < 1:1.0.1-1.
Epoch is permanent: final must be `1:1.0.0-1`. Revision default is now 1 (was 2). Local repack of dist/linux (38 split debs) works: 192 MiB, Version 1:1.0.0~beta.4.1-1, newer than 1.0.0-2, SHA256SUMS ok (deleted afterwards, not committed).

## macOS: what beta.4 showed
Run 41206492948 dmg-verify: CFBundleShortVersionString=1.0.0, CFBundleVersion=1.0.0 (set in trial-build.sh configure, so it was in the bundle). Finder prints just "1.0.0" when both are equal, with no beta marker; the dmg file itself has no version field at all, so Get Info on the dmg shows none. Now Finder shows "1.0.0 (401)". Note: modern Finder may not display CFBundleGetInfoString; the release id is guaranteed only in the file name, About and that key. If the owner wants "beta.4.1" literally in Get Info, CFBundleVersion would have to be "beta.4.1" (non-numeric, contradicts the monotonic-number requirement).

## Other files
- generate-update-manifest.py: parse_asset_name/asset_platform regex with embedded release; rejects a name whose release differs from the tag (legacy bare 1.0.0 names still accepted).
- collect-release-assets.sh, release.yml, desktop-linux/macos workflows, update client (update_installer name check `[A-Za-z0-9._-]+`, platform by extension), probe workflows (globs `HSTOffice_*_macOS_*`): no change needed.
- tests/runtime/check-window-title.py now expects the release id in libcuilo. Docs: README, BUILD_MATRIX (new section), CI, RELEASE_CHECKLIST, UPDATE_INSTALL, docs/website/README.
- Local tree upstream/libreoffice (hstbuild-owned) synced with the two changed patches (about.cxx, cmdlinehelp.cxx, default.rc, include/hst_version.h) so apply-patches --check stays consistent.
- The macOS trial-build.sh edit was swept into commit e326759 (other session) already on origin; origin was inconsistent (used HST_RELEASE before write-hst-version exported it) until this push.

## Verification
- Unit: new tests/unit/test_hst_version.py (build numbers, ordering, rejects, header/CLI), test_make_single_deb.py (version, final, bad id, dpkg ordering, metainfo), test_update_installer.py (name parsing, legacy, mismatch).
- check-workflows.py ok; bash -n on changed scripts ok; ci-quality: 36 commands, 0 failures.
- actionlint is not installed here and downloading a binary was blocked; the preflight scripts skip it. Not run.
- Not verified (need native builds, not dispatched): rc.exe accepting hst_version.h macros, MSI ProductVersion 1.0.0.401 result, plutil keys, Finder display.

## Unresolved
- docs/releases/v1.0.0-beta.4.1.md is required by release.yml and not written (fix list is the owner's).
- Window titles show the product name only (by design, hst-window-title.patch); "Document Recovery" etc. still show major.minor "1.0" via %PRODUCTVERSION. Not changed.
- Programs and Features name stays "HST Office 1.0.0"; DisplayVersion is numeric 1.0.0.401 (Windows Installer cannot show the string id there).
- MSI Upgrade table: old betas ProductVersion 1.0.0.1, new 1.0.0.401; OLDPRODUCTS matches <= new version so upgrade removes old; installing an older beta over new is blocked (NEWPRODUCTS). Confirm on first Windows smoke run.

Status: DONE_WITH_CONCERNS
Summary: Release id 1.0.0-beta.4.1 drives file names, Windows file/MSI versions, macOS plist, Linux deb/AppStream and About; ci-quality 0 failures; linux repack verified.
Concerns: Linux needs permanent epoch 1; native Windows/macOS results unverified until a full build (not dispatched); actionlint not run; release notes file for beta.4.1 missing.
