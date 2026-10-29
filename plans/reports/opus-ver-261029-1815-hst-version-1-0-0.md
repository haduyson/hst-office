# opus-ver: HST Office 1.0.0 version, packaging, bundled extension (2026-10-29)

Status: DONE_WITH_CONCERNS (translations: 2186 fuzzy entries dropped by msgfmt, see Findings).

## Design
- `/home/office/VERSION` = `1.0.0` single source. `scripts/write-hst-version.py` (--header / --env / --print; validates MAJOR.MINOR.MICRO; header rewritten only on change).
- `scripts/build-linux.sh`: exports HST_VERSION_MAJOR/MINOR/MICRO into make env (as_builder), `prepare_version` before `--build` and `--package`: writes `include/hst_version.h`, regenerates `openoffice.lst` (config.status -> fill HST_VERSION placeholders -> fail if any left -> replace only on change).
- Engine 26.8.1.1 untouched (postprocess/configure not changed). Per owner update: About label "1.0.0 (X86_64)" only; "Copy version info" adds `Engine: 26.8.1.1` line; `soffice --version` = `HST Office 1.0.0 <buildid>` (no LibreOffice text).
- Packaging: openoffice.lst.in HSTOffice section (also used by HSTOffice_languagepack) -> UNIXBASISROOTNAME hst-office1.0, PRODUCTVERSION 1.0, PRODUCTEXTENSION .0, PACKAGEVERSION/UREPACKAGEVERSION 1.0.0, download names HSTOffice_1.0.0_*. sysui/productlist.mk takes HST_VERSION_* from env (`$(error)` if unset), PKGREVISION 1; CustomTarget_share/deb use PKGVERSIONSHORT/PKGREVISION.
- Bundled extension: `dictionaries/ExtensionPackage_hst-vietnamese-tools.mk` builds the .oxt via `scripts/build-extensions.py` (no binary committed; deps tracked on extensions/, data/, script), gb ExtensionPackage unpacks to `instdir/share/extensions/hst-vietnamese-tools` + `workdir/ExtensionPackage/hst-vietnamese-tools.filelist`; scp2 `common_brand.scp` file entry in gid_Module_Root_Brand (hst-office1.0 package). Bundled layer => registered for every user on first start, not removable in Extension Manager.
- Patches: `hst-packaging.patch` (lst.in), `hst-packaging-sysui.patch` (productlist/share/deb hunks) updated in place so each patch reverse-applies on the final tree; new `hst-version.patch` (about.cxx, cmdlinehelp.cxx, common_brand.scp, Module_dictionaries.mk, new ExtensionPackage mk), appended to series. `apply-patches.sh --check`: all 10 "already applied". Files touched by the series and present in the pristine tarball apply cleanly to pristine 26.8.1.1 (partial extraction test; translations/dictionaries files absent there so those two hunks were not exercised on pristine).

## Build
- `scripts/stage-branding.py` then `build-linux.sh --build` (several runs: gbuild wiring fixes: target registration, eval of userfriendly targets; then source change after owner update) and `--package`.
- l10n: incremental make does NOT rebuild vi .mo. Deleted `workdir/MoTarget/*vi.mo` + `instdir/program/resource/vi/LC_MESSAGES/*.mo`, re-ran `--build`: .mo timestamps 18:45 (sfx.mo 54818 -> 104133 B).
- Stale outputs must be deleted for repackaging after a version change: `workdir/CustomTarget/sysui/deb/hst_office*`, `.../sysui/deb.done`, `.../sysui/share/hst_office`, `.../share.done`, `workdir/ScpPreprocessTarget/scp2/source/ooo/common_brand.pre`, `workdir/ScpTarget/scp2/source/ooo/common_brand.*`, `workdir/installation/HSTOffice*`. (First repackage shipped a stale menus deb with 26.8 icon names; caught by the docker test, fixed by the deletions above.)
- Result: dist/linux 38 .deb (`hst-office1.0*`, `hst-officebasis1.0-*`, `hst_office1.0-debian-menus_1.0.0-1_all.deb`, version 1.0.0-1) + SHA256SUMS. Brand deb contains `/opt/hst-office1.0/share/extensions/hst-vietnamese-tools/` (50 entries, description.xml present).

## QA
- check-defaults.py (as nobody): 9/9 PASS. check-office-roundtrip.py: 9/9 PASS (odt/docx/pdf, ods/xlsx/pdf, odp/pptx/pdf). No test hardcoded 26.8.1.1 (nothing to relax).
- check-deb-install.sh dist/linux (docker ubuntu:24.04): PASS, 26 checks; new: `bundled-extension-files` (/opt/hst-office1.0/share/extensions/hst-vietnamese-tools/description.xml), `unopkg-list-bundled` (Identifier: vn.hasontech.hst.vietnamese-tools), `--version` = `HST Office 1.0.0 680(Build:1)`. Test now derives names from VERSION.
- ci-quality.sh: 18 commands, 0 failures.
- GUI (Xvfb :97, nobody, fresh profile tests/output/hst-gui-1.0, LANG=vi_VN.UTF-8; PNGs in tests/output/screenshots-1.0/): 02 welcome dialog shown on first start (extension auto-registered, no unopkg), 03 Start Center (new banner, Vietnamese menu bar incl. "HST"), 04/09 Help and HST menus ("Giải pháp HASON TECH..."), 05 About (Version: 1.0.0 (X86_64), HASON TECH contact), 06 tip of the day, 06b HST toolbar, 07 Writer Tabbed UI (Vietnamese tabs), 08 ND30 wizard opens. The black rectangle in 07 and the double Start Center in 04/09 are an unrelated stale soffice (pid 3482630, 16:25, profile tests/output/hst-gui) sharing :97; I did not touch it. My own soffice was stopped.

## Findings (English left on main surfaces)
Root cause: 2186 of 30537 vi msgids carry `#, fuzzy` in translations/source/vi; msgfmt drops them. E.g. startcenter|open_all/create_label etc.
- Start Center: Open File, Remote Files, Recent Documents, Templates, Create:, Text Document, Spreadsheet, Presentation, Filter/All Documents, Help, Extensions.
- Help menu: "What's This?". About: title "About HST Office", description paragraph "HST Office is a modern, easy-to-use...", Close; "Misc: HST Office build from LibreOffice 26.8.1.1" (EXTRA_BUILDID; still names LibreOffice); About "derived from OpenOffice.org" line (coordinator's separate patch).
- Writer: ribbon "Copy" button.
- A small window titled "HST Office 26.8" (engine PRODUCTVERSION) appeared at startup: another place showing the engine version.
Suggested fix (translations owner): clear fuzzy flags on reviewed entries (or build .mo with `msgfmt --use-fuzzy`), then delete workdir/MoTarget/*vi.mo and rebuild.

## Files changed
VERSION; scripts/write-hst-version.py; scripts/build-linux.sh; patches/libreoffice/{series,hst-version.patch,hst-packaging.patch,hst-packaging-sysui.patch}; tests/runtime/check-deb-install.sh; README.md; docs/BUILD_MATRIX.md; docs/RELEASE_CHECKLIST.md; this report. Upstream tree (via patches): cui/source/dialogs/about.cxx, desktop/source/app/cmdlinehelp.cxx, instsetoo_native/util/openoffice.lst(.in), sysui/{productlist,CustomTarget_share,CustomTarget_deb}.mk, scp2/source/ooo/common_brand.scp, dictionaries/Module_dictionaries.mk, dictionaries/ExtensionPackage_hst-vietnamese-tools.mk, include/hst_version.h (generated). Generated: dist/linux/*, tests/output/{ver-qa,hst-gui-1.0,screenshots-1.0,deb-install}, dist/extensions/*.oxt (ci-quality).

Unresolved: fuzzy policy; "HST Office 26.8" window title; EXTRA_BUILDID text; macOS/Windows scripts not wired to write-hst-version.py (owned by CI agent).
