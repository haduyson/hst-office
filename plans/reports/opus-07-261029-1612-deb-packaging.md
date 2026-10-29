# opus-07 Debian packaging report (2026-10-29)

Status: DONE_WITH_CONCERNS (see Leftovers).

## Result
- `scripts/build-linux.sh --package` -> `/home/office/dist/linux/` : 38 `.deb` + `SHA256SUMS` (202 MiB). `sha256sum -c` all OK. Hashes: `/home/office/dist/linux/SHA256SUMS`.
- Docker (ubuntu:24.04 clean container) `tests/runtime/check-deb-install.sh dist/linux`: **PASS** end to end. Log: `tests/output/deb-install/install-lifecycle.log` (copy: `build/logs/opus07-docker.out`).
- Install root `/opt/hst-office26.8`; commands `/usr/bin/hst-office`, `/usr/bin/hst-office26.8`; 8 launchers `/usr/share/applications/hst-office26.8-*.desktop` (HST Writer / HST Sheets / HST Slides / HST Office, Name[vi] same); HST icons `hicolor/{16..512}/apps/hst-office26.8-{writer,calc,impress,draw,base,math,startcenter,main,chart}.png`; mime `/usr/share/mime/packages/hst-office26.8.xml`.

## Root causes fixed
1. Missing `hst_office-desktop-integration.tar.gz`: sysui/productlist.mk only knew libreoffice(dev). Product id `hst_office` (= lc(PRODUCTNAME), spaces->_ as scp2 module_systemint computes) added; debian package name via `DEBNAME` (underscore invalid); `-p` args quoted in CustomTarget_share.mk (space in "HST Office").
2. Installer download step failed on dir `HST Office_26.8.1.1_..._deb` (unquoted shell paths in `installer/download.pm`) -> whole run renamed `_witherror`.
3. LibreOffice naming/collisions: Globals overridden in HSTOffice section (UNIXBASISROOTNAME hst-office26.8, BASISPACKAGEPREFIX hst-officebasis, UREPACKAGEPREFIX/SOLSUREPACKAGEPREFIX hst-office, WINDOWSBASISROOTNAME HSTOffice). create_tree.sh: no `/usr/bin/libreoffice26.8` compat link, no `/opt/libreoffice26.8` link, mime file `hst-office26.8.xml` (not `libreoffice26.8.xml`), no appstream metainfo (LibreOffice component ids), HST icons instead of LO icons (scalable LO svg skipped).
4. Debian-menus postinst/prerm rewrote global `/etc/mime.types` and `/etc/mailcap` (deleting other apps' entries, excel/word etc.): reduced to mime/desktop/icon cache refresh.
5. Uninstallable set: with `--enable-python=system` scp2 never got `-DENABLE_LIBRELOGO`, so pyuno `Conflicts/Replaces` librelogo while librelogo was still packaged -> `apt install` "held broken packages". Fixed in scp2/InstallModule_python.mk.
6. No library Depends: soffice failed on clean image (`libXinerama.so.1` missing). Added 24.04 system deps to the brand package (list from `dpkg-shlibdeps` over all 176 ELF files + python3); install now launches.
7. Maintainer was "The Document Foundation" -> "HASON TECH" (packinfo vendor; copyright line deliberately kept).

## Patches (all verified: apply to pristine 26.8.1.1 files, tree is byte-identical to pristine+patches, reverse dry-run = "already applied")
`patches/libreoffice/series` appended: `hst-packaging-sysui.patch`, `hst-packaging-installer.patch`, `hst-packaging-vendor.patch`, `hst-packaging-scp2.patch`; `hst-packaging.patch` rewritten (lst.in only: HSTOffice section + Globals overrides). Note: `scripts/apply-patches.sh --check` currently stops at `hst-start-center-banner.patch` ("does not apply", edited 16:34 by another agent, not mine), so later patches are not reached by that script run; verified mine individually.
Other files: `scripts/build-linux.sh` (package step), `tests/runtime/check-deb-install.sh`, `docs/BUILD_MATRIX.md`.

## Docker proof excerpt
```
PASS no-preinstalled-office            PASS no-libreoffice-named-package
PASS no-libreoffice-named-system-file  PASS install-root-hst-only
PASS no-conflicts-with-libreoffice     INFO maintainer hst-office26.8 HASON TECH
PASS app-icons-installed (24 files)    PASS launcher 'Name=HST Writer|HST Sheets|HST Slides|HST Office'
PASS commands-on-path (/usr/bin/hst-office)   INFO writer-exec hst-office26.8 --writer %U
INFO version HST Office 26.8.1.1 680(Build:1) PASS convert (txt->odt->docx as user 'tester')
PASS coexist-no-hst-removal / coexist-official-installable (apt-get -s install libreoffice-writer)
PASS purged-no-dpkg-records  PASS user-documents-kept  PASS user-profile-kept (~/.config/hstoffice)
PASS binaries-removed  PASS no-leftover-files  PASS reinstall  PASS convert-after-reinstall
result: PASS
```
Coexistence = static (no Conflicts/Replaces/Provides naming libreoffice/libobasis in any of the 38 control files) + `apt-get -s` simulation; a real co-install of the official packages was NOT run. Profile dir name in the container: `~/.config/hstoffice`.

## Packages (bytes)
```
718 hst-office26.8-base_26.8.1.1-1_amd64.deb
718 hst-office26.8-calc_26.8.1.1-1_amd64.deb
4047236 hst-office26.8-dict-en_26.8.1.1-1_amd64.deb
938520 hst-office26.8-dict-es_26.8.1.1-1_amd64.deb
1310920 hst-office26.8-dict-fr_26.8.1.1-1_amd64.deb
13498 hst-office26.8-dict-vi_26.8.1.1-1_amd64.deb
718 hst-office26.8-draw_26.8.1.1-1_amd64.deb
5676 hst-office26.8-en-us_26.8.1.1-1_amd64.deb
722 hst-office26.8-impress_26.8.1.1-1_amd64.deb
718 hst-office26.8-math_26.8.1.1-1_amd64.deb
12917040 hst-office26.8-ure_26.8.1.1-1_amd64.deb
6122 hst-office26.8-vi_26.8.1.1-1_amd64.deb
724 hst-office26.8-writer_26.8.1.1-1_amd64.deb
510648 hst-office26.8_26.8.1.1-1_amd64.deb
1561976 hst-officebasis26.8-base_26.8.1.1-1_amd64.deb
9572258 hst-officebasis26.8-calc_26.8.1.1-1_amd64.deb
96887246 hst-officebasis26.8-core_26.8.1.1-1_amd64.deb
4684 hst-officebasis26.8-draw_26.8.1.1-1_amd64.deb
78522 hst-officebasis26.8-en-us_26.8.1.1-1_amd64.deb
3582210 hst-officebasis26.8-extension-pdf-import_26.8.1.1-1_amd64.deb
3153216 hst-officebasis26.8-firebird_26.8.1.1-1_amd64.deb
1214922 hst-officebasis26.8-gnome-integration_26.8.1.1-1_amd64.deb
1386516 hst-officebasis26.8-graphicfilter_26.8.1.1-1_amd64.deb
50945554 hst-officebasis26.8-images_26.8.1.1-1_amd64.deb
193042 hst-officebasis26.8-impress_26.8.1.1-1_amd64.deb
108420 hst-officebasis26.8-librelogo_26.8.1.1-1_amd64.deb
1808 hst-officebasis26.8-libreofficekit-data_26.8.1.1-1_amd64.deb
571144 hst-officebasis26.8-math_26.8.1.1-1_amd64.deb
139656 hst-officebasis26.8-ogltrans_26.8.1.1-1_amd64.deb
13238906 hst-officebasis26.8-ooofonts_26.8.1.1-1_amd64.deb
1266 hst-officebasis26.8-ooolinguistic_26.8.1.1-1_amd64.deb
2326720 hst-officebasis26.8-postgresql-sdbc_26.8.1.1-1_amd64.deb
11732 hst-officebasis26.8-python-script-provider_26.8.1.1-1_amd64.deb
134384 hst-officebasis26.8-pyuno_26.8.1.1-1_amd64.deb
584840 hst-officebasis26.8-vi_26.8.1.1-1_amd64.deb
4569098 hst-officebasis26.8-writer_26.8.1.1-1_amd64.deb
288410 hst-officebasis26.8-xsltfilter_26.8.1.1-1_amd64.deb
505296 hst_office26.8-debian-menus_26.8.1-1_all.deb
```
(+ `hst-officebasis26.8-vi`, `hst-office26.8-vi`, `hst-office26.8-dict-vi` = vi language pack; dict-en/es/fr from --with-myspell-dicts.)

## Leftovers / concerns
- `dpkg -I`: no Homepage field (EPM does not emit one). Description for ure is upstream-garbled "UNO Runtime Environment.1.1". `%copyright` still "2026 The Document Foundation" (intentional).
- Package `hst-officebasis26.8-libreofficekit-data` and files `/opt/hst-office26.8/share/{libreofficekit,glade/libreoffice-catalog.xml,palette/libreoffice.soc,themes/Libreoffice.theme}`, `program/liblibreofficekitgtk.so` keep "libreoffice" in names; they are under the HST root so cannot collide, but are visible branding strings (palette/theme names appear in UI).
- Mimetype icons (documents) are still the upstream LibreOffice document-type icons (only application icons are HST). `/usr/lib/menu/hst_office26.8` (Debian menu) uses the old menu title format.
- Dependencies are Ubuntu 24.04 (t64) names only; Debian/older Ubuntu untested. Dlopen-only libs not covered by ldd (e.g. gstreamer plugins, GL) not exercised; headless convert only, no GUI launch in container.
- Upgrade test NOT RUN (only one revision exists). lintian NOT RUN.
- `instdir/share/xdg/*.desktop` regenerated by `make build` (now HST names/icons names `hst-office26.8-*`); nothing else in instdir touched, no clean. Stale `sysui/deb/hst_office` workdir had to be deleted once (create_tree does not wipe).
- The `workdir/installation/*/deb/install/*_deb_download` dirs hold a ~200 MiB tar.gz each (installer download set, unused).

Unresolved: should libreofficekit/palette/theme names be renamed? Should HST doc-type mime icons be created?
