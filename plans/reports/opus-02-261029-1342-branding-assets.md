# opus-02 branding assets (2026-10-29)

Status: DONE_WITH_CONCERNS (assets/checker/docs done; nothing built/applied in LO tree; see concerns)

## Pinned-source findings (read-only, /home/office/upstream/libreoffice)
- `configure.ac:3113` AC_ARG_WITH(branding); `:15570-15571` required files: `intro.png intro-highres.png logo.svg logo_inverted.svg logo-sc.svg logo-sc_inverted.svg about.svg donate1.png donate2.png`. Missing -> only AC_MSG_WARN + upstream default (`:15584-15586`). `:15573-15583` dir must exist.
- Package: `desktop/Package_branding_custom.mk:10-18` intro* -> `$(LIBO_ETC_FOLDER)`, rest -> `$(LIBO_ETC_FOLDER)/shell`. Default: `desktop/Package_branding.mk` (icon-themes/colibre/brand[_dev]; intro.png uses brand_dev unless ENABLE_RELEASE_BUILD).
- progress.conf is `source`d (`configure.ac:15608-15610`); vars PROGRESSBARCOLOR/SIZE/POSITION/FRAMECOLOR/TEXTCOLOR/TEXTBASELINE -> `config_host.mk.in:590-595` -> env `solenv/bin/modules/installer/ziplist.pm:788-796` -> `scp2/source/ooo/common_brand.scp:368-422` (keys ProgressBarColor etc. in sofficerc/bootstrap). `openoffice.lst.in:18-25` has defaults (30,145 / 385,8 / baseline 170 for 644x199); `PROGRESSPOSITIONHIGH/SIZEHIGH` are lst-only (no env override, unused by scp2). `splash.cxx:355-425` parses them; `:262-285` default only if keys absent.
- Sizes: upstream intro.png 644x199, intro-highres 990x254 (nothing in C++ reads `intro-highres` in this tree; only `static/CustomTarget_emscripten_fs_image.mk:31`), donate1 200x200 RGB (`backingwindow.cxx:274-286` hard-codes 200/150 px), donate2 150x150 RGBA. SVG loader `sfx2/source/appl/appmisc.cxx:129-160` uses SVG range/aspect only.
- Readers: About `cui/source/dialogs/about.cxx:106-107` (logo/logo_inverted by dark theme), `:117` shell/about; What's New `whatsnewtabpage.cxx:48`; Start Center `sfx2/source/dialog/backingwindow.cxx:119` (logo-sc[_inverted]); donate banner `backingwindow.cxx:210-219` gated by `Misc::ShowDonation`.
- Links to patch: `officecfg/registry/data/org/openoffice/Office/Common.xcu:354-359` ReleaseNotesURL/CreditsURL (hub.libreoffice.org); InfoURL `:36`. About strings `about.cxx:248-258` (RID_CUISTR_ABOUT_VENDOR/COPYRIGHT/BASED_ON/DERIVED).
- Desktop: `sysui/desktop/menus/*.desktop` (Name=%PRODUCTNAME Writer, Icon=writer, Exec=${UNIXBASISROOTNAME}, StartupWMClass=libreoffice-writer), `sysui/CustomTarget_share.mk:105-109` icons from `sysui/desktop/icons/{hicolor,locolor}/<size>/apps/<app>.png`, `sysui/desktop/share/brand.pl:32` productfilename "libreoffice". `instsetoo_native/CustomTarget_setup.mk:42` ProductKey.

## Created / changed
- `scripts/generate-brand-assets.py` (69 lines) + `scripts/brand/{__init__,common,legacy,app_icons,lo_branding,platform_icons,audit}.py`. Old 7 outputs byte-identical (git shows no diff).
- Generated (51 files, deterministic): `branding/libreoffice/{intro.png 644x199, intro-highres.png 1288x398, logo.svg, logo_inverted.svg, logo-sc.svg, logo-sc_inverted.svg, about.svg, donate1.png, donate2.png, progress.conf}`, `assets/brand/icons/hst-{office,writer,sheets,slides}-{16,24,32,48,64,128,256,512}.png`, `branding/windows/hst-office.ico`, `branding/macos/hst-office.icns`.
- Hand-written: `branding/linux/hst-{office,writer,sheets,slides}.desktop` (vi/en, MimeType lists, `hst-office --writer|--calc|--impress %U` placeholders), `branding/credits.html`, `branding/help/index.html`, `branding/brand-audit-allowlist.json`.
- `scripts/check-branding.py` + `scripts/brand/audit.py`; `tests/brand/test-check-branding.py` (10 tests); extended `tests/brand/test-brand-assets.py` (9 tests); `assets/brand/brand-spec.json` (appIcons, libreofficeBranding, platformIcons); `docs/BRAND.md`.
- Mark is pixel-identical in lockup SVGs (tested); intro/donate/app icons scale it (LANCZOS). 512 px icons upscale the 269 px mark ~1.9x (flat colour, looked clean visually; no vector source exists).

## Verification (run)
- `.venv/bin/python scripts/generate-brand-assets.py --check` -> up to date (51 files)
- `tests/brand/test-brand-assets.py` 9 OK; `tests/brand/test-check-branding.py` 10 OK (also with `-W error::ResourceWarning` on generator-owned code)
- `desktop-file-validate branding/linux/*.desktop` -> OK
- `scripts/check-branding.py` -> assets ok. Tree scan only unit-tested on synthetic trees (NOT run on real instdir: not built).
- Visual: rendered icons (light), intro, about, logo_inverted -> look correct. System LO 24.2 loaded logo/about/logo_inverted SVGs via UNO GraphicProvider and rendered the embedded PNG (data-URI works). Not verified in 26.8 build, splash/About/Start Center screenshots (need build).

## Integration points for coordinator
1. configure: `--with-branding=/home/office/branding/libreoffice` (all 9 required files + progress.conf present, no fallback warnings expected); `--with-product-name='HST Office' --with-vendor='HASON TECH' --enable-release-build`.
2. Start Center donate banner: set `Misc/ShowDonation=false` (officecfg Common.xcu) or leave; images already HST.
3. Common.xcu:354-359 CreditsURL/ReleaseNotesURL -> local `credits.html` / hasontech.vn; install `branding/credits.html` and `branding/help/index.html` (help links `../credits.html`, adjust if installed elsewhere).
4. About strings `about.cxx:248-258` (+ `cui/inc/strings.hrc`) for "based on LibreOffice" + HST text.
5. Desktop/icons: replace `sysui/desktop/menus/*.desktop` generation (or install `branding/linux/*.desktop`); install icons from `assets/brand/icons/hst-*-{size}.png` to `hicolor/<size>x<size>/apps/<name>.png` (CustomTarget_share.mk:105-109). Finalize Exec names and `StartupWMClass` (currently omitted on purpose; upstream uses `libreoffice-writer`).
6. `brand.pl:32` productfilename, `CustomTarget_setup.mk:42` ProductKey, `Setup.xcu` ooName/ooVendor per phase plan.
7. After build: `python3 scripts/check-branding.py --install-root upstream/libreoffice/instdir --allowlist branding/brand-audit-allowlist.json` and refine allowlist (seed is minimal: license/NOTICE/CREDITS/credits.html/help index).
8. Windows .ico/.icns for platform pipelines: written with Pillow, not tested on OS.

## Concerns / unresolved
- Splash progress coordinates assume intro.png 644x199 and default text baseline 170; check text clipping in real splash.
- Allowlist is a seed; real tree scan will show internal identifiers (e.g. registry names) needing narrow regex entries.
- `credits.html` cites engine commit `bf6ef26...` from plan.md (not re-verified in this task); HST version is not stated (shown by About). Contact data from brief §1.
- Tagline image text "by HASON TECH" is ASCII on purpose (pinned font is Bold Italic only).
- `docs/BRAND.md` was reformatted/touched by an external process once during the run (hook note); content verified after.
