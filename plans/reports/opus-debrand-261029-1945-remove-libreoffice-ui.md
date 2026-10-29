# opus-debrand: LibreOffice / TDF removed from HST Office UI (2026-10-29)

Spec: docs/LICENSE_AUDIT.md section 3 (3.1 keep, 3.2 remove). Owner choices: Help -> HST page on hasontech.vn (one config value), extension site stays.

## What changed
- `patches/libreoffice/hst-debrand.patch` (new, last in series): help target, menu URL handling, tip of the day, Impress Remote link, palette name.
- `hst-about.patch` (extended, about.cxx section regenerated from pristine), `hst-defaults.patch` (Common.xcu section), `hst-start-center-banner.patch` (backingwindow.cxx section): sections regenerated so each patch still reverse-applies on the final tree. Verified forward: series applied to pristine 26.8.1.1 files (partial extraction, 17 files) == tree files. `apply-patches.sh --check`: all 11 "already applied".
- `l10n/vi-overrides.jsonl` (14 rows) + `scripts/l10n/apply-overrides.py` (uses po_io.fill_po overwrite, msgfmt --check on changed files, restores file on failure, errors on missing key, idempotent, never re-adds fuzzy). Called from `scripts/build-linux.sh --build` after version prep, before `make` (there is no overlay merge in that script; merge-vi.py is a manual step, overrides must run after it).
- `build-config/{linux,windows}-x86_64.conf`: `--with-extra-buildid` removed. Verified `build-linux.sh --build` never re-runs configure (only `--configure` copies the conf to autogen.input), so the Linux tree keeps the old value in config_buildid.h until the next clean configure; nothing reads it any more (only about.cxx did).
- Docs: LICENSE_AUDIT 3.2 "Xu ly" column, README, RELEASE_CHECKLIST, BRAND (About rule). BUILD_MATRIX unchanged (build steps same).
- Tests: `tests/runtime/check-no-libreoffice-ui.py` (new), `check-defaults.py` (+HelpRootURL, +popup off), `check-deb-install.sh` (+step no-libreoffice-ui in container).

## 1. About
Removed: "derived from" line, copyright line, Credits link, EXTRA_BUILDID in Misc, build-id row (it linked to git.libreoffice.org; the id stays in "Copy version info", Engine line kept). Added: "Phan mem nguon mo theo Mozilla Public License 2.0 ... (Tro giup -> Thong tin giay phep). Ma nguon: https://github.com/haduyson/hst-office", then vendor line and HASON TECH block. Release Notes button now opens the plain config URL (github releases). Screenshot 03-about.png.

## 2. Help
- `Office.Common/Help/HelpRootURL` (officecfg Common.xcs) is the single value: `https://hasontech.vn/?utm_source=hst-office&utm_medium=help&utm_campaign=hst-office-1-0`. `impl_showOnlineHelp` (sfxhelp.cxx) opens it as is (no Target=/version/lang). `BuiltInHelpNotInstalledPopUp` default false so F1 goes straight to the URL. Non-empty value also keeps dialog Help buttons visible.
- Measured with a fake xdg-open (tests/output/hst-gui-debrand/opened-urls.log): F1/Help menu "Tro giup HST Office" -> help URL; Options dialog Help button -> same help URL; "Huong dan su dung" and "Nhan tro giup truc tuyen" -> hasontech.vn utm_medium=menu; "Tham gia dong gop" -> https://github.com/haduyson/hst-office.
- appserv.cxx: Send Feedback / Q&A / Documentation / Get Involved / Donation / What's New / Hyphenation open the config URL untouched (previously LOversion/LOlocale/BCP47 query appended). Start Center logo click (VolunteerURL) no longer gets a language suffix. Menubar XML of Writer/Calc/Impress/Start Center and the Tabbed UI help menu all use these .uno commands, no XML change needed (donation already removed by hst-remove-donation).
- Tip of the day: 6 tips deleted (Ask portal, community, certification, portable, user-guide books, donations); help.libreoffice.org links -> HelpRootURL; wiki.documentfoundation.org / www.libreoffice.org / documentfoundation.org topic links hidden; extensions.libreoffice.org kept.
- Common.xcu: HyphenationMissing/InstallJava/Volunteer -> hasontech.vn (utm_medium=menu); QA/Documentation -> same with utm; Donation stays plain (the banner code appends its own utm).

## 3. URL inventory (grep over sfx2 cui svx desktop framework sw sc sd vcl) decision
- tipoftheday.hrc help.libreoffice.org/* (about 30): retarget to HelpRootURL at run time.
- tipoftheday.hrc www.libreoffice.org (accessibility, get-involved, donate, portable), ask.libreoffice.org, documentation.libreoffice.org, documentfoundation.org certification, wiki.documentfoundation.org (UserProfile, citation, languages, hybrid PDF): hidden or tip removed (see above).
- extensions.libreoffice.org (tips, AdditionsDialog api, ExtensionManager.xcu, hub.libreoffice.org/extensions): KEEP (owner).
- about.cxx git.libreoffice.org/core/commit: removed.
- presentationdialog.ui hub.libreoffice.org/impress-remote ("Download App"): link hidden.
- sfxhelp.cxx macOS `www.libreoffice.org` (default-browser probe, macOS only, never opened): KEEP, internal.
- vcl/unx/gtk3 salnativewidgets-gtk.cxx www.libreoffice.org: KEEP, dummy link button for theme metrics, never shown.
- dp_dependencies.cxx http://libreoffice.org/extensions/description/2011 (extension XML namespace) and unopkg_app.cxx wiki DevGuide text (CLI help): KEEP, technical.
- sw/sc/sd qa/*.cxx: tests only.
- officecfg: Update.xcs update-mar.libreoffice.org: KEEP (online update disabled in the build, never contacted); bugs.documentfoundation.org in schema comments: KEEP.
Not reachable from this tree: English UI strings that literally say "LibreOffice" (en-US fallback); changing the msgid would orphan the vi translation, so only vi was overridden. Follow-up if English UI becomes a target.

## 4. Strings (14 vi overrides)
cui: copyright/based_on/derived (About no longer uses them; neutral text), crash report check box and bug-report text (HST issues URL), `opthtmlpage|starbasic` -> "%PRODUCTNAME _Basic" (decision: it is the label of an HTML export option next to Basic code, a display label; macro container identifiers are not translated strings, so changing it is safe), uui password-protected Basic note (versions "truoc phien ban loi 5.0.3"), sd Impress Remote tooltip (link hidden), UI.po Donation label ("Quyen gop", item hidden), mediawiki help text, Windows msi/scp2 strings ("Cong dong HST Office", tooltip, capability name), desktop dependency message "yeu cau phien ban engine toi thieu %VERSION" (typo "TIen" fixed).
KEPT on purpose (allow-listed in the test): `licensedialog|label` (sfx.mo, upstream copyright and MPL terms), readlicense docs/readme credits (legal), `libreoffice-profile.zip` (real file name written by safe mode export), the .mo header lines (Report-Msgid-Bugs-To etc., not displayed).

## 5. Palette / theme
Palette `libreoffice.soc` shown as "HST Office" (PaletteManager.cxx both directions of the name mapping, so the stored selection still resolves); colour name "(LibreOffice Main Color)" -> "(Main Color)". `Libreoffice.theme` (name "LibreOffice") KEPT: ColorSets.cxx and the PPTX exporter look it up by that name; it is not a shown palette name.

## 6. Build / package
Deleted all vi .mo (workdir/MoTarget/*vi.mo, instdir/.../vi/LC_MESSAGES/*.mo) and rebuilt (`--build` twice: second after adding the crash dialog override), stale packaging outputs removed (list in opus-ver report) and `--package`: 38 .deb in dist/linux, svx.mo in the deb identical to instdir.

Finding (not a bug in the build): the Start Center and other .ui labels are translated by GTK gettext, which needs a Vietnamese system locale. Test host has only C/en_US, so `LANG=vi_VN.UTF-8` gives English .ui labels (log: "Locale not supported by C library") while menus/code strings are Vietnamese. QA used a private locale: `localedef -i vi_VN -f UTF-8 tests/output/hst-gui-debrand/locpath/vi_VN.UTF-8` + `LOCPATH`. With it the Start Center shows "Mo tap tin / Tai lieu gan day / Van ban / Bang tinh / Trinh chieu" (screenshot 02). Real users on vi_VN systems are fine; a user on a non-vi system locale with UI language set to vi would still see English .ui labels (upstream behaviour).

## 7. QA
- check-defaults.py (as nobody): 11/11 PASS (incl. HelpRootURL, popup off).
- check-office-roundtrip.py (as nobody): 9/9 PASS.
- check-no-libreoffice-ui.py: PASS (About text from about.cxx has no LibreOffice and contains github.com/haduyson/hst-office, notice compiled into installed libs; 34 vi .mo, 0 unexpected mentions). It is static for the About text; the live dialog is in screenshot 03.
- check-deb-install.sh dist/linux (docker ubuntu:24.04): PASS incl. new step no-libreoffice-ui.
- ci-quality.sh: 18 commands, 0 failures. apply-patches --check: 11/11 already applied.
- Screenshots tests/output/screenshots-debrand/: 02 Start Center (vi), 03 About, 05 Help menu, 06 after clicking help items, 07 Options dialog with Help button, 09 tip of the day. 01/04/08 are diagnostics (01 welcome dialog; 04 doc properties showing English sfx .ui labels without locale; 08 after Help click). Old coordinator soffice (pid 3482630, :97, hst-gui) killed (it was obsolete); my soffice stopped.

## Unresolved
- "HST Office 26.8" window title at startup (engine version) seen again in window list (`xdotool` name); not in any visible UI I captured; not addressed.
- English en-US strings naming LibreOffice (see 3). 
- Vietnamese wording of the new About notice/crash text is mine; native-speaker review advised. README/credits (readlicense) still name LibreOffice (legal credits, kept).
