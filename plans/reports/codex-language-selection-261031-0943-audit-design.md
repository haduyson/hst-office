# HST Office language selection: audit and Phase 2 design

## Summary

Static review only. No source edits, builds, `soffice`, X server, or runtime probes were run. This report is the only file written. `date +%H%M` returned `0943` when naming it; timezone Asia/Ho_Chi_Minh, 2026-10-31. The checkout is being edited concurrently; references describe the inspected working tree, not a frozen release artifact. Git HEAD observed: `078c76d`.

Evidence prefixes below are repository-relative: **U/** = `upstream/libreoffice/`; **E/** = `extensions/hst-vietnamese-tools/`; **P/** = `patches/libreoffice/`. Line references identify inspected source, not runtime proof. Proposed changes and expected probe outcomes are explicitly prospective.

Normal Options selections use supported tokens and a conventional restart path. No critical crash or document-loss defect was established by this static review. Major issues for Phase 2 are loss of explicit English intent for alternate spellings, misleading behavior under administrator locks, incomplete English HST strings/assets, and the absence of a demonstrated document-reopening contract. References: `U/cui/source/options/optgdlg.cxx:1148`, `U/desktop/source/app/langselect.cxx:80`, `U/svtools/source/misc/langhelp.cxx:49`, `U/comphelper/source/misc/officerestartmanager.cxx:108`.

The installation registers only `en-US` and `vi`; read-only directory enumeration found only `common` and `vi` under `instdir/program/resource`. English source strings are the normal fallback, so no English catalog directory is required. Evidence: `U/config_host/config_langs.h:9`, `U/instdir/share/registry/Langpack-en-US.xcd:2`, `U/instdir/share/registry/Langpack-vi.xcd:2`, `U/unotools/source/i18n/resmgr.cxx:212`.

Acceptance: preserve Default versus explicit preference; implement the exact owner exceptions below; cover every identified forced surface; respect locks; restart safely and reopen documents for the beta.4 shortcut; leave document language/content/number formats unchanged. Core UI follows the resolved UI language. The shortcut is already accepted in `docs/BACKLOG.md:92`; glossary/placeholder rules are at `docs/L10N_GLOSSARY.md:10` and `:33`.

## Findings

| ID | Severity | Finding and consequence | Recommendation |
|---|---|---|---|
| LS-01 | info | Requested and resolved locales are different; conflating them changes Default behavior. | Use raw `Linguistic/General/UILocale` for HST policy; preserve empty. |
| LS-02 | major | `en`, `en-GB`, `EN-us` can be rejected and cleared; Options also matches raw tokens exactly. | Resolve English aliases to installed `en-US` without erasing intent; fix Options representation. |
| LS-03 | minor | Registration is trusted even when Vietnamese catalogs are missing or incomplete. | Validate packages; probe missing registration separately from missing resources. |
| LS-04 | info | Other OS languages resolve to shipped English; document locale remains separate. | Keep this sensible fallback and test RTL/CJK document rendering. |
| LS-05 | minor | Locale/resource/widget caches prevent reliable live language switching. | Define changes as restart-effective and initialize HST policy before windows. |
| LS-06 | major | English extension catalog still contains 49 Vietnamese UI strings; labels/assets/help also force Vietnamese. | Complete catalog and site inventory changes together. |
| LS-07 | major | Finalization blocks writes, but Options does not disable its UI-language selector. | Disable locked controls; reject dispatch writes before prompting for restart. |
| LS-08 | major | Restart uses save/veto handling, but automatic reopening is not established. | Add a tested native session-preserving language-restart coordinator. |
| LS-09 | minor | Existing runtime tests do not distinguish explicit English from Default and have welcome/title observation gaps. | Replace assumptions with the matrix and observations below. |
| LS-10 | minor | Beta.2 profiles may retain choices and resolved caches; no HST locale migration was found. | Preserve raw choices and unrelated profile keys; never infer choice from cache. |
| LS-11 | minor | HST message-box/picker chrome and raw error text can escape the HST language policy. | Localize controlled buttons/errors and validate picker behavior separately. |
| LS-12 | info | PIN and extension-install warnings already follow UI language; static OS metadata cannot follow a profile. | Preserve UI-following paths; resolve static artifact boundaries explicitly. |

### LS-01 — What changes, where, and when

`/org.openoffice.Office.Linguistic/General/UILocale` is a non-null string: empty means desktop default (`U/officecfg/registry/schema/org/openoffice/Office/Linguistic.xcs:139`). Options lists Default plus `InstalledLocales`, writes `""`, `"en-US"`, or `"vi"`, commits, then asks about restart (`U/cui/source/options/optgdlg.cxx:968`, `:977`, `:1148`, `:1167`). A persisted explicit selection has this logical shape in `user/registrymodifications.xcu`; XML serialization/order is not a contract:

```xml
<item oor:path="/org.openoffice.Office.Linguistic/General">
  <prop oor:name="UILocale" oor:op="fuse"><value>en-US</value></prop>
</item>
```

For Vietnamese use `vi`; for Default use `<value/>`. An absent user-profile override inherits the effective lower-layer value, which can be an administrator's nonempty choice; only absence from all overriding layers reaches the schema's empty default. Startup sets the configuration provider's locale and `/org.openoffice.Setup/L10N/ooLocale` to the resolved installed language (`U/desktop/source/app/langselect.cxx:106`). `SvtSysLocaleOptions` and `ConfigManager::getUILocale()` use this **resolved** Setup value, not the preference (`U/unotools/source/config/syslocaleoptions.cxx:112`, `U/unotools/source/config/configmgr.cxx:83`). Observe the committed configuration through UNO immediately and disk after flush/clean exit, not by assuming synchronous XML writes.

Restart Later keeps the new preference pending. Restart Now calls the restart manager asynchronously; an already pending restart suppresses duplicate dialogs (`U/svtools/source/dialogs/restartdialog.cxx:100`, `U/comphelper/source/misc/officerestartmanager.cxx:44`). Selecting the existing value does not prompt (`U/cui/source/options/optgdlg.cxx:1163`). Switching Default ↔ English must still count as a policy change even on an English OS where the resolved core language stays English.

### LS-02 — Alternate English tags lose intent

Installed-language matching first tests the raw, case-sensitive string, then `LanguageTag(locale).getFallbackStrings(false)` (`U/svtools/source/misc/langhelp.cxx:54`). The normalized original is excluded: English regional tags reduce to `en`, which is not registered here; bare `en` has no useful fallback (`U/i18nlangtag/source/languagetag/languagetag.cxx:2187`, `:2250`, `:2253`, `:2491`). Thus `en`, `en-GB`, and `EN-us` can become Default and even Vietnamese on a Vietnamese OS. This is a source-derived expectation to verify, not an executed result.

On failure, startup attempts to clear `UILocale`, then tries command-line language and system fallback (`U/desktop/source/app/langselect.cxx:82`). A finalized value prevents the clear, but the local resolved variable is already empty: it still falls back to the OS. Fix resolution, not just the failed write. By contrast, `vi-VN` can fall back to registered `vi` through its primary language.

Options represents a nonempty preference only by an exact match to installed tokens (`U/cui/source/options/optgdlg.cxx:1005`). Retaining `en-GB` or `vi-VN` without updating this code would display Default; applying another option could overwrite the original preference (`:1163`). Show the corresponding installed English/Vietnamese entry, preserve the raw value when the selector did not change, and write canonical tokens only for an actual user selection.

Empty string is valid Default. Unrecognized strings such as `de` or malformed tags enter the unsupported-language fallback; the schema validates string type, not installed membership (`U/officecfg/registry/schema/org/openoffice/Office/Linguistic.xcs:139`, `U/desktop/source/app/langselect.cxx:80`). No unsafe document write is visible in that path. Do not extrapolate this into proof that every malformed tag or corrupt catalog cannot crash; probes must capture process exit and diagnostics.

### LS-03 — Missing registration differs from missing translations

The chain is explicit preference → command-line language → system UI language → installed `en-US` → first registered locale; no locale returns startup failure (`U/desktop/source/app/langselect.cxx:80`, `:96`, `:103`; `U/svtools/source/misc/langhelp.cxx:106`, `:160`). Unsupported explicit `de` is cleared when writable. It does **not** necessarily become English: on a Vietnamese OS, system fallback can select Vietnamese.

Deleting `resource/vi` alone leaves `vi` registered, so startup can still report `ooLocale=vi` while missing gettext messages fall back to English source (`U/svtools/source/misc/langhelp.cxx:49`, `U/unotools/source/i18n/resmgr.cxx:212`). Missing localized configuration has its own fallback, including normalized variants, then `en-US`, `en`, empty, or another value (`U/configmgr/source/access.cxx:1463`, `:1479`, `:1515`). Partial packs therefore produce mixed domains/widgets rather than a single trustworthy language indication. Validate catalogs and registry resources as one package contract; do not repair this by overwriting users' preferences.

### LS-04 — OS language, layout, and fonts

With the observed two-language installation, Default on `fr_FR`, `ja_JP`, `zh_CN`, `ar_*`, or `he_IL` falls back to English core UI; HST forced content remains Vietnamese today. Default on Vietnamese selects `vi`. This is sensible given the shipped languages, although it cannot satisfy a French/Japanese/Arabic UI request (`U/svtools/source/misc/langhelp.cxx:106`, `:160`; `E/python/hst_office/dispatch.py:62`). The PackageKit branch is conditional on build languages, vendor, and policy, not a guarantee of downloading arbitrary OS languages (`U/svtools/source/misc/langhelp.cxx:113`).

Linux LocaleBackend uses `LC_ALL`, then `LC_MESSAGES` for UI or `LC_CTYPE` for user locale, then `LANG`; its selection path does not inspect `LANGUAGE` (`U/shell/source/backends/localebe/localebackend.cxx:163`, `:250`, `:261`). Desktop backends/native widgets still need environment-specific observation. Clear inherited `LANGUAGE` for the baseline, then deliberately test it separately.

Automatic RTL uses the resolved UI language; with English/Vietnamese it is LTR. `SAL_RTL_ENABLED` presence or explicit `Common/I18N/CTL/UIMirroring` can override this (`U/vcl/source/app/settings.cxx:2633`). CJK/CTL text support is distinct from shipping translated UI; this source keeps those font capabilities enabled (`U/svl/source/config/cjkoptions.cxx:34`, `U/svl/source/config/ctloptions.cxx:422`). Document language is derived separately from system settings (`U/desktop/source/app/langselect.cxx:124`). Font substitution depends on available fonts and language (`U/vcl/source/outdev/font.cxx:449`, `:529`); it does not guarantee glyph coverage. Verify Arabic/Hebrew shaping, Japanese/Chinese glyphs, cursor behavior, and unchanged document styles.

### LS-05 — Cache and live-change boundaries

The requested `comphelper/translatehelper` path does not exist in this checkout; the relevant API is `U/include/unotools/resmgr.hxx:77`, implemented in `U/unotools/source/i18n/resmgr.cxx:112`.

| Layer/module | Evidence and consequence |
|---|---|
| Translation domains | `Translate::Create` caches by locale plus domain (`U/unotools/source/i18n/resmgr.cxx:114`). It can create another locale, but existing widgets are not rebuilt. |
| VCL, extension manager | VCL caches its resource locale (`U/vcl/source/app/svdata.cxx:296`); `DpResId` has a static locale (`U/desktop/source/deployment/misc/dp_misc.cxx:513`). |
| Writer/Sheets/Slides | `SwResId`, `ScResId`, `SdResId` call module resource lookup (`U/sw/source/uibase/app/swmodule.cxx:173`, `U/sc/source/ui/app/scdll.cxx:94`, `U/sd/source/ui/app/sdmod.cxx:88`). `SfxModule::GetResLocale` delegates to `Translate::Create`, rather than keeping a separate module locale (`U/sfx2/source/appl/module.cxx:100`). Writer also stores translated strings in `ShellResource`; Calc caches language-specific function names (`U/sw/source/uibase/utlui/initui.cxx:108`, `U/sc/source/core/data/global.cxx:643`). |
| Menus/ribbon | Addons configuration is cached; notifications reload data asynchronously, with no menu-rebuild operation in that callback (`U/framework/source/fwe/classes/addonsoptions.cxx:446`, `:479`, `:1946`). Notebookbar copies labels into widgets (`U/vcl/source/window/NotebookBarAddonsMerger.cxx:99`). |
| Python HST | `load_locale` opens JSON each call; there is no gettext or locale-selection cache there (`E/python/hst_office/data_files.py:32`). Dispatch currently hardcodes vi; each Host/dialog retains its selected strings (`E/python/hst_office/dispatch.py:62`, `E/python/hst_office/actions.py:15`, `E/python/hst_office/dialogs.py:45`). |
| Update check | Reads resolved `ooLocale` per selection (`E/python/hst_office/update_ui.py:43`), independent of HST forced-language policy. |

Configuration reads can reflect a committed change immediately, and document locale/format settings have live notification paths. That does not make UI-language switching live: the source explicitly says it cannot switch UILocale at runtime (`U/unotools/source/config/syslocaleoptions.cxx:400`, `:417`). Phase 2 should freeze active HST policy at startup and apply the pending choice on restart.

### LS-06 / LS-11 — Catalog, assets, controls, and errors

Both JSON catalogs have 134 leaf strings and matching keys. Static comparison found 49 Vietnamese leaves in `en.json`: seven menu labels, all 41 ND30 strings, and the ND30 undo title (`E/locales/en.json:4`, `:48`, `:162`). Merely changing dispatch to `load_locale("en")` is insufficient. The inventory below also identifies baked text, help, and template labels.

Common message boxes use system button enums; the CSV picker sets only its title and filters (`E/python/hst_office/dialogs.py:125`, `E/python/hst_office/actions.py:99`). Thus Vietnamese HST body text can coexist with English core/backend buttons on Default+English OS. Unknown blocker codes, OS errors, and exception text are exposed directly (`E/python/hst_office/actions.py:25`, `E/python/hst_office/wizard_csv.py:42`, `:65`, `E/python/hst_office/dispatch.py:66`). Provide localized common error summaries while retaining diagnostic details in logs. Do not translate user paths or document content.

For HST-owned message boxes, reuse the extension's explicit-label dialog controls (`E/python/hst_office/dialogs.py:74`). For CSV, use the existing `com.sun.star.ui.dialogs.OfficeFilePicker` service (`U/fpicker/source/office/OfficeFilePicker.cxx:974`) with a proposed optional HST per-instance locale argument through its NamedValue initialization path (`:894`). Route that argument into this instance's labels, navigation help and errors; ordinary pickers keep their current locale. Set supported labels via `XFilePickerControlAccess`, but do not claim that alone covers native navigation chrome: unsupported labels may be ignored (`U/offapi/com/sun/star/ui/dialogs/XFilePickerControlAccess.idl:81`). The added office-picker locale path must never change the application's global locale. This is an implementation/QA item, not an invented third owner exception.

### LS-07 — Administrator lock

`build-update-policy-oxt.py` currently finalizes **AutoCheck only**, not UILocale (`scripts/release/build-update-policy-oxt.py:35`). Its shared-OXT packaging pattern can be reused for locale policy. Finalized properties expose READONLY, reject UNO writes, and suppress later overrides (`U/configmgr/source/access.cxx:2225`, `U/configmgr/source/xcuparser.cxx:665`). `oor:mandatory` protects removal of set members, not arbitrary property edits; it is not a replacement for `oor:finalized` (`U/configmgr/source/xcuparser.cxx:818`, `:936`).

The current UI-language combobox has no corresponding read-only guard; failed writes are caught/logged with no meaningful user feedback (`U/cui/source/options/optgdlg.cxx:977`, `:1167`, `:1183`). Patch both Options and the shortcut. Do not lock/write derived `Setup/L10N/ooLocale` as a substitute for the preference.

### LS-08 — Restart, unsaved documents, recovery

The restart manager calls desktop termination; frame suspension reaches `PrepareClose`, which handles Save/Discard/Cancel and failed saves (`U/comphelper/source/misc/officerestartmanager.cxx:108`, `U/framework/source/services/desktop.cxx:1675`, `U/sfx2/source/view/sfxbasecontroller.cxx:595`, `U/sfx2/source/doc/objxtor.cxx:596`). HST stops the frame loop on save-query cancellation (`U/framework/source/services/desktop.cxx:1682`). Earlier frames may already have closed; cancellation is not an atomic rollback of every window. The restart request resets on failure, while the committed language remains pending (`U/comphelper/source/misc/officerestartmanager.cxx:119`, `U/cui/source/options/optgdlg.cxx:1167`).

No automatic-reopen promise follows from `requestRestart()` alone. Native session save/restore exists, but ordinary restart does not invoke it here (`U/framework/source/services/autorecovery.cxx:3825`, `:3890`). Recovery/session handling is disabled by headless or `--norestore` (`U/desktop/source/app/app.cxx:2061`). The existing harness always adds `--norestore` (`tests/runtime/hst_gui.py:74`), so it cannot validate recovery or the proposed native session restart without an operator-owned launcher adaptation.

Do not implement reopening by killing/relaunching the process or saving only file URLs: unnamed documents, unsaved changes, hidden tabs, multiple views, passwords, save failures, and close vetoes need native lifecycle handling. Ordinary language selection itself does not write document contents in the inspected path; Phase 2's restart integration is the main data-safety gate.

### LS-09 / LS-10 / LS-12 — Verification and profile boundaries

`check-vi-intro.py` varies OS language, never raw UILocale, and accepts either About title for both runs (`tests/runtime/check-vi-intro.py:80`, `:107`, `:135`). Its `welcome=True` leaves a dialog open but the harness still seeds `Shown=true`; explicitly override to false when probing first start (`tests/runtime/hst_gui.py:50`, `:88`). Its unconditional-Vietnamese assertions need updating, not wholesale removal (`tests/runtime/check-vi-intro.py:35`).

For a beta.2 profile, inspect raw UILocale, resolved `ooLocale`, `ooSetupSystemLocale`, welcome `Shown`, and update settings. The extension stores `Shown` and `AutoCheck/LastCheck/SkippedVersion`, not a locale (`E/welcome.xcs:9`, `E/update.xcs:10`). No HST locale migration was found in the 25-patch series or extension; normal core migration is invoked for a newly created installation profile (`U/desktop/source/app/app.cxx:1549`). A real beta.2 artifact/profile is still required to prove historical behavior. Never migrate cached `ooLocale=en-US` into explicit English. Preserve user custom menus; no HST-generated Title overrides currently exist in the inspected dispatch/startup code (`E/python/hst_office/dispatch.py:56`, `E/python/hst_office/welcome_job.py:30`, `E/Jobs.xcu:13`).

The PIN prompt already uses the active UI locale, and the extension-install warning branches on active UI language, so neither needs conversion to the new forced-HST policy (`U/uui/source/iahndl-authentication.cxx:523`, `U/uui/source/passworddlg.cxx:135`, `U/desktop/source/deployment/gui/dp_gui_dialog2.cxx:156`). Static Explorer/Finder copyright and shared LICENSE files cannot vary with a per-profile runtime preference; their treatment is identified under Unresolved questions.

## Runtime probe plan

**Operator only.** Use a frozen installation copy and disposable profiles/artifacts outside source. Record executable version/hash, installation path, profile, PID, X display, UNO port, backend, environment, installed-language nodes, and catalog files before each run. Inspect the chosen port/display before starting; reuse only an operator-owned X server, otherwise choose one fixed free pair for this audit. Track/stop every process started. Do not touch the live installation to simulate damage.

The existing harness supplies UNO setup, fresh-profile initialization, configuration seeding, PID-filtered windows, screenshots, dispatch, and cleanup (`tests/runtime/hst_gui.py:26`, `:65`, `:117`, `:189`, `:202`, `:223`, `:244`). Use `start(fresh=False)` to retain a seeded profile; `fresh=True` deletes it. Avoid blanket cleanup/forced kills during a save-veto probe. The snippets below are for an operator to run, not files created by this audit.

Minimal seed for an already initialized, stopped profile (merge these items into its existing XML; replace an existing property rather than creating duplicates):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
  <item oor:path="/org.openoffice.Office.Linguistic/General">
    <prop oor:name="UILocale" oor:op="fuse"><value>en-US</value></prop>
  </item>
  <item oor:path="/org.hasontech.hstoffice.Welcome">
    <prop oor:name="Shown" oor:op="fuse"><value>true</value></prop>
  </item>
  <item oor:path="/org.openoffice.Office.Common/Misc">
    <prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop>
  </item>
</oor:items>
```

Read-only UNO observation helper, after `hst_gui.setup_uno(instdir)` and `office.start()`:

```python
from com.sun.star.beans import PropertyValue

def config(node, name):
    p = PropertyValue()
    p.Name, p.Value = "nodepath", node
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    access = provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationAccess", (p,))
    return access.getPropertyValue(name)

requested = config("/org.openoffice.Office.Linguistic/General", "UILocale")
resolved = config("/org.openoffice.Setup/L10N", "ooLocale")
system_ui = config("/org.openoffice.System/L10N", "UILocale")
system_locale = config("/org.openoffice.System/L10N", "SystemLocale")
provider = office.ctx.getValueByName(
    "/singletons/com.sun.star.configuration.theDefaultProvider")
provider_locale = provider.getLocale()  # XLocalizable, active config locale
```

These System properties expose the locale backend; its C++ `getSystemLocale()` is reached through property access, not an assumed method on Desktop (`U/shell/source/backends/localebe/localebackend.cxx:292`, `U/officecfg/registry/schema/org/openoffice/System.xcs:29`). Read InstalledLocales with configuration `XNameAccess.getElementNames()`. Read UILocale READONLY through `getPropertySetInfo().getPropertyByName("UILocale").Attributes` and `PropertyAttribute.READONLY`.

1. **Nine baseline combinations.** For each `LANG=LC_ALL=en_US.UTF-8`, `vi_VN.UTF-8`, `fr_FR.UTF-8`, run raw `UILocale=""`, `en-US`, `vi`. Set `LANGUAGE=""` explicitly, remove `SAL_RTL_ENABLED`, leave UIMirroring unset, generate/verify necessary OS locales with `localedef`/LOCPATH. Use `Office(..., config=[("/org.openoffice.Office.Linguistic/General", "UILocale", raw)], env={"LANGUAGE": ""}, nodefault=False)`. Current expected core: Default=en/vi/en respectively; explicit values override OS. Current forced surfaces remain vi. Phase 2 expected forced surfaces: English only for explicit English; welcome always vi; update follows core. Capture actual menubar and notebookbar labels in all three document modules, About body/title, Start Center hint/banner/tooltips, license, and HST dialogs. Use screenshots plus accessibility names/text; a translated window title alone is insufficient.

2. **Actual Options round trips.** From each starting choice, switch to each other choice via the visible UI and test Apply/OK, Restart Later, Restart Now, Cancel-before-Apply, and unchanged selection. Observe raw config immediately; inspect XML after clean exit and relaunch the same profile. Expect canonical `""`/`en-US`/`vi`, no change before Apply, and restart prompt only on a changed preference. Include Default↔English on English OS: core language remains English but Phase 2 HST policy changes after restart. Record pre-restart stale menus/dialogs rather than requiring live translation.

3. **Beta.2 carry-over.** Copy a real beta.2 profile with its matching provenance. Test absent UILocale, empty UILocale plus cached `ooLocale=en-US`, explicit en-US, explicit vi, and vi-VN. Preserve `Shown`, update settings, documents, and customized menu configuration. Expected: no migration of resolved cache into intent; no repeated welcome when Shown was true; explicit choices survive upgrade. Open Options and Apply an unrelated setting to detect alias-to-Default reset. Synthetic profiles supplement, not replace, the real profile.

4. **Alternate and malformed strings.** Seed `en`, `en-GB`, `EN-us`, `en-US`, `vi-VN`, `vi`, `de`, `fr-FR`, `enough`, `eng`, `en_US`, `-`, and whitespace; repeat on English and Vietnamese OS. Current expectation: exact installed values work; English aliases can be cleared; vi-VN resolves vi; unsupported values fall back through OS. Save before/after preference, resolved language, exit status and logs. Phase 2: recognized English prefixes remain stored and resolve built-in en-US, with English HST text. No crash, loop, or document mutation is acceptable. Include empty and missing values separately.

5. **Pack integrity failures.** In separate disposable installation copies: (a) rename `program/resource/vi`, keeping registration; (b) remove one vi `.mo` domain; (c) omit vi registry localization; (d) omit `Langpack-vi.xcd` registration; (e) omit both locale registrations. Run raw vi and Default on Vietnamese/English OS. Expect (a–c) potentially mixed English source/config fallbacks while vi remains selected, (d) preference clearing plus the remaining English fallback, and (e) controlled startup failure, not a document crash. Retain original files for repair; do not edit a symlink target in the real installation. Forced Windows text that relies on vi catalogs must also be checked on Windows.

6. **OS language and environment precedence.** Run Default with `fr_FR`, `ja_JP`, `zh_CN`, `ar_EG`, `he_IL`. Expect English core, Vietnamese HST, LTR absent overrides. Repeat `LANG=vi_VN`, `LC_ALL=en_US`, `LANGUAGE=vi`; then unset LC_ALL and set `LC_MESSAGES=vi_VN` with English LANG. Observe System/UI/provider values and GTK/native labels independently; do not infer them from environment alone. Test `--language=vi` with empty preference versus explicit en-US; it changes core fallback selection, not explicit-English intent.

7. **RTL/CJK document safety.** Under Arabic/Hebrew/Japanese/Chinese OS settings, open fixtures containing real scripts, edit/save/reopen, and compare text/codepoints, styles, numbers, and document hashes where unchanged. Record installed fonts and screenshots for missing glyphs/shaping. Test explicit mirroring separately; `SAL_RTL_ENABLED=0` still sets a present variable, so unset it for baseline. HST dialogs should remain usable under mirroring without changing the document language.

8. **Extension catalog/dispatch coverage.** Dispatch each `org.hst.office.vi:` command through its real frame provider, not a macro that supplies a catalog directly. Inspect ND30 dropdowns, labels, help text, validations and undo label; converter controls/status; CSV delimiter/mode/error/overwrite flows; date/VND/percent messages; and welcome entry. Expected after Phase 2: English controls in explicit English, Vietnamese otherwise, with identical Vietnamese ND30 preview/output and unchanged CSV text/numeric values. Probe empty selection, protected content, stale conversion selection, missing CSV, malformed UTF-8, and overwrite rejection. Inspect message-box buttons and picker chrome separately.

9. **Welcome and update exceptions.** Set `Shown=false`, run startup in a thread because the modal welcome can block UNO, observe Vietnamese content, close it, restart and verify it does not reappear. Open `ShowSolutions` from HST: English menu/ribbon entry in explicit English, Vietnamese dialog. Use `config=[(...,"Shown","false")]` to override harness defaults. Run existing controlled update-test infrastructure and inspect menu/help/ribbon labels and notification/result dialogs; Default+English OS must produce English update UI. Do not depend on the public update endpoint for assertions (`E/python/hst_office/update_ui.py:43`; `tests/runtime/check-update-notify.py:201`).

10. **Admin policy.** Create/install a test shared OXT using the policy fragment below, separately finalizing empty, en-US, vi, and en-GB. Launch profiles with conflicting user values. Expect the effective finalized value to win; direct UNO writes must fail; after Phase 2 both Options and shortcut are disabled and no restart is offered after rejection. Also test a finalized ancestor, a mandatory-only set-member control, policy removal, and a fresh/reset profile. The current update-policy OXT alone must not lock language. Inspect effective READONLY, not only XML presence.

11. **Unsaved documents and veto.** Open saved modified Writer/Sheets/Slides files, an unnamed modified document, a read-only file, hidden document tabs, and two views of one model. Change language and request restart. Test Save, Discard, Cancel, canceled Save As, unwritable save target, active modal dialog and a close veto. Record which frames close before cancellation, pending UILocale, restart-request state, file content and recoverability. Current expected safety: failed/canceled save prevents successful restart; no unconsented loss. Phase 2's session path must additionally restore all intended documents/views, including unnamed changes, without changing originals unless the user saved them.

12. **Real recovery and session reopening.** Adapt an operator-owned copy of the harness launcher to omit `--norestore` and `--headless` for the GUI lifecycle; do not modify the shared test file during concurrent work. Verify the planned restart checkpoint with saved, dirty, unnamed, encrypted and remote documents; simulate a save/checkpoint failure. In an isolated disposable fixture run, crash only the operator-owned process after recovery data is known to exist, then relaunch and recover content. Record expected versus observed document count/URLs/views/content. Ordinary restart, session restore and crash recovery are separate outcomes.

13. **Menu lifecycle and artifacts.** Test first frame after changing via Options, first frame after shortcut restart, a new module opened later, extension disable/re-enable/uninstall, profile reset, and a preexisting user-customized Title. Expected chosen design: correct labels at initial construction, no generated user Title overrides, no orphan override after uninstall, update labels untouched. Validate English/vi banner assets, ten tip images, help links/screenshots and three HST template categories. The dispatch provider can report availability, but its no-op status listener currently supplies no label; observe rendered accessibility labels (`E/python/hst_office/dispatch.py:89`).

14. **Native platform checks.** Windows: trigger default-file-association startup notice with real association state, inspect title/body/checkbox/tooltip/OK/Cancel under Default, explicit English and vi; inspect PIN title/body/error using a test token without logging PINs. Windows MSI, Linux package description and macOS DMG remain Vietnamese in all cases. macOS/Windows require their native environments; Linux/Xvfb cannot establish those results. Preserve normal UI language for PIN and extension installation warnings.

## Design

### Explicit-English definition

**Authoritative owner refinement, verbatim:**

> on an explicit English choice, everything normally forced to Vietnamese switches to English EXCEPT two things that ALWAYS stay Vietnamese: (1) installer windows (Windows MSI, Linux package description, macOS dmg window); (2) the welcome dialog (hộp chào mừng, shown on first start and from the HST menu).
>
> Parts that switch to English on explicit English: About; Start Center intro/banner text; licence notice; HST menu and its dialogs including NĐ 30 (and CSV import, encoding conversion, etc.); the Windows file-association notice; the USB-token PIN prompt wording (if it is forced to vi).

The existing beta.4 shortcut retains its separately specified invariant labels: `Ngôn ngữ giao diện`, `Tiếng Việt`, `English`, `Theo máy` (`docs/BACKLOG.md:92`). Proper names, addresses, document content, and legal license text are not UI translations.

Define one predicate over the **effective configured preference**, not configuration-layer provenance:

```text
explicitEnglish(raw) = raw is a nonempty string
                       and its first '-' separated subtag equals ASCII 'en', ignoring case
hstLanguage(raw) = 'en' if explicitEnglish(raw) else 'vi'
```

Equivalently, `raw == "en"` or `raw` begins `"en-"`, ignoring ASCII case. No whitespace trimming, underscore conversion, or generic `startswith("en")`: `eng`, `enough`, and `en_US` are false. This is a BCP47 **primary-prefix classifier**, not a complete tag validator; even a malformed `en-...` suffix remains classified English and is resolved safely to the shipped en-US UI. The UI itself writes only `en-US`, `vi`, or empty. This makes malformed-input behavior explicit without adding another language parser.

`en-GB`, `en-AU`, `EN-us`, and bare `en` use shipped American English; no extra pack is requested. A finalized en-US/en-GB preference also counts as explicit English: runtime cannot infer whether a human or administrator authored the setting. Default remains false even when OS, `--language`, fallback, or cached `ooLocale` says English. Missing/config-read failure defaults HST policy to vi with a diagnostic, never a rewrite of the preference. Explicit vi yields Vietnamese throughout the shipped UI; document content semantics remain unchanged.

**C++ placement:** add a small pure prefix predicate and active-policy accessor to the existing unotools configuration surface (`U/include/unotools/configmgr.hxx`, `U/unotools/source/config/configmgr.cxx`). A pure inline predicate is feasible; keep the shared process snapshot in the existing `utl` library, not a separate function-static cache in each DLL. Read `officecfg::Office::Linguistic::General::UILocale::get()` during `prepareLocale`, before any clearing branch; initialize once before windows. Existing consumers already depend on utl; examples are `U/cui/Library_cui.mk:64`, `U/framework/Library_fwk.mk:60`, `U/vcl/Library_vcl.mk:78`; utl already consumes officecfg and i18nlangtag (`U/unotools/Library_utl.mk:19`, `:43`). Do not use or change the semantics of `ConfigManager::getUILocale()`.

**Required resolver change:** before existing installed-locale matching at `U/desktop/source/app/langselect.cxx:82`, recognized English preference maps to registered en-US, leaving the raw value untouched, including when locked. Fix Options alias display and write-on-actual-selection behavior described in LS-02. Unsupported non-English tags retain the ordinary fallback policy. A damaged installation with no registered English must report its packaging failure; do not invent a language registration.

**Python equivalent:** a pure `is_explicit_english(raw)` in a small `python/hst_office/ui_language.py`, plus configuration read and process-active selector. Initialize the snapshot through an `OnStartApp` job before visible UI; the existing job executor supports real document events and startup sends OnStartApp before backing-component creation (`U/framework/source/jobs/jobexecutor.cxx:276`, `U/desktop/source/app/app.cxx:1558`). Use the same predicate, initialize once, and test early initialization. Dispatch passes only `en` or `vi` to the JSON loader. Keep a separate fresh read for pending choice and lock state. Require restart when enabling the extension mid-session; do not lazily capture a changed pending choice as though it were startup state. No persisted second HST language preference.

### Site inventory

Each row specifies current mechanism and proposed change. Existing English sources can be reused only where they still express HST wording and links.

| Site | Evidence: patch → applied source, or extension owner | Change / English source |
|---|---|---|
| About description | `P/hst-about.patch:127` → `U/cui/uiconfig/ui/aboutdialog.ui:100` | Fixed Vietnamese, nontranslatable. Set bilingual HST description in constructor using active policy; English baseline in patch deletion at `:126` needs HST wording. |
| About publisher/open-source/contact | `P/hst-about.patch:104`, `:111`, `:114` → `U/cui/source/dialogs/about.cxx:242`, `:249`, `:252` | Replace fixed text with selected strings. Existing English vendor resource: `U/cui/inc/strings.hrc:361`; add English HST open-source/contact labels. Keep actual names/phone/address facts. |
| Start Center empty-state intro | `P/hst-start-center-banner.patch:581` → `U/sfx2/source/control/recentdocsview.cxx:66` | Select vi or existing English `STR_WELCOME_LINE1`/`STR_WELCOME_LINE2` resources at `U/include/sfx2/strings.hrc:194`. This is not the exempt welcome dialog. |
| Start Center six solution tooltips and more-link | `P/hst-start-center-banner.patch:101`, `:147`, `:530` → `U/sfx2/source/dialog/backingwindow.cxx:258`, `:300`; `U/sfx2/uiconfig/ui/startcenter.ui:791` | Add English descriptive text and more-link; keep product names. Keep C++/UI fallbacks consistent. Bilingual data source needed at `data/hst/solutions.json:27`; welcome must still select vi. |
| Banner pixels | `P/hst-start-center-banner.patch:155` → `U/sfx2/source/dialog/backingwindow.cxx:307`; `assets/brand/brand-spec.json:185`, `scripts/brand/start_center_banner.py:33`, `scripts/stage-branding.py:75` | Always uses `donate1.png` with Vietnamese headline. Ship English and vi artwork and select by policy, or move all translated text into real labels. No string-only fix. |
| License source-offer notice | `P/hst-debrand.patch:170` → `U/sfx2/source/appl/appserv.cxx:314` | Currently concatenates vi and English. Select the HST paragraph by policy; English already exists. Preserve source URL, offer and attribution. |
| License summary/copyright | `P/hst-ux-fixes.patch:57` → `U/sfx2/source/appl/appserv.cxx:325` | Fixed vi. Add equivalent English HST summary. Do not restore upstream URL or removed rights wording from `U/sfx2/uiconfig/ui/licensedialog.ui:68`. |
| Full LICENSE HST preface | `P/hst-debrand.patch:339` → `U/readlicense_oo/license/license.xml:11`; opened at `U/sfx2/source/appl/appserv.cxx:339` | Static bilingual preface. For runtime presentation, select a localized HST preface/view while keeping every substantive license intact; static distributed artifact boundary below. |
| HST menubar entries m1–m7 | `E/Addons.xcu:19` | Fixed vi in default/en-US/vi variants. Supply real English from `locales/en.json`; select via policy-aware configuration read described below. Root HST stays HST. |
| HST notebookbar entries m1–m7 | `E/Addons.xcu:114` | Same change, including tooltips and accessible names; must not fix only menubar. |
| HST solutions/welcome command entry | `E/Addons.xcu:79`, `:182`; `E/python/hst_office/dispatch.py:81` | Menu/ribbon title becomes English on explicit English. The dialog opened remains entirely Vietnamese. |
| HST command dispatch/error wrapper | `E/python/hst_office/dispatch.py:62`, `:66` | Replace both hardcoded vi catalog loads with active HST selector; localize error summary without hiding diagnostics. |
| ND30 wizard and messages | `E/python/hst_office/wizard_nd30.py:28`, `:39`, `:94`; `actions.py:49`; `E/locales/en.json:48` | Translate all 41 English-catalog UI leaves, type labels, explanations, validation labels, actions, status and accessibility help. Translate undo label at `E/locales/en.json:162`. Preserve generated Vietnamese document/preview content. |
| Encoding conversion | `E/python/hst_office/wizard_convert.py:14`, `:40`; `actions.py:67`, `:72`, `:75` | Existing English catalog usable; cover suggestion, preview headings, result/error/blocker text and undo. Encoding identifiers remain unchanged. |
| CSV import/picker | `E/python/hst_office/wizard_csv.py:14`, `:42`, `:62`; `actions.py:99`, `:124`, `:126`, `:132` | Existing English catalog largely usable; select all labels, validation/overwrite/results and undo. Localize controlled picker labels; close native chrome gap per LS-11. |
| Date/VND/percent and shared messages | `E/python/hst_office/actions.py:21`, `:25`, `:85`; `E/python/hst_office/dialogs.py:125` | Catalog-select notices, blockers and common buttons. Preserve data, formulas and vi-VN number-format semantics (`E/python/hst_office/sheets.py:40`). |
| Welcome dialog — exception | `E/python/hst_office/welcome_job.py:43`, `E/python/hst_office/welcome_dialog.py:96`, `:151` | Keep `load_locale("vi")`, content, controls, tooltips and error summaries vi on first start and menu invocation. Do not select existing welcome English catalog. |
| Update check — existing UI rule | `E/Addons.xcu:89`, `:102`, `:193`; `E/python/hst_office/update_ui.py:43`, `:123`, `:192` | Preserve resolved-UI language, including Default English. Exclude update URLs from HST menu override. |
| Windows file-association notice | `P/hst-windows-fileassoc-vi.patch:16`, `:44` → `U/vcl/win/app/fileregistration.cxx:168`, `U/cui/source/dialogs/fileextcheckdlg.cxx:40` | Replace forced vi-VN locale with active HST en-US/vi locale for title/body/checkbox/tooltip/Cancel. English resources already exist at `U/vcl/inc/strings.hrc:114`. Include currently normal-locale OK button (`U/cui/uiconfig/ui/fileextcheckdialog.ui:64`). |
| PIN prompt/error — already UI-following | `P/hst-digital-signature.patch:192`, `:205`, `:223` → `U/uui/inc/strings.hrc:32`, `U/uui/source/iahndl-authentication.cxx:523`, `U/uui/source/passworddlg.cxx:135` | No vi override exists. Preserve `Translate::Create("uui")` and English source strings; verify runtime rather than changing global UUI locale. |
| Extension installation warning — already UI-following | `P/hst-extensions.patch:125`, `P/hst-ux-fixes.patch:35` → `U/desktop/source/deployment/gui/dp_gui_dialog2.cxx:156` | Already has English/vi HST wording selected by active UI language. Keep core-feature behavior. |
| Offline guide/F1 and tip Help link | `P/hst-offline-help.patch:29`, `:50`, `:80` → `U/cui/source/dialogs/tipofthedaydlg.cxx:231`, `U/officecfg/registry/schema/org/openoffice/Office/Common.xcs:3106`, `U/sfx2/source/appl/sfxhelp.cxx:658` | Fixed `help/index.html`; all 19 HTML pages are vi (`E/help/index.html:2`). Add English guide, navigation, accessibility labels and language-correct screenshots. Select English only for the bundled default path; preserve custom/empty HelpRootURL. |
| Tip-of-day images | `scripts/l10n/apply-overrides.py:95`, `scripts/l10n/build-tip-images.py:29` → `U/extras/source/tipoftheday/`, consumed at `U/cui/source/dialogs/tipofthedaydlg.cxx:262` | Global vi image replacement. Keep two language variants for the ten mapped images and select by policy; preserve debranding in English artwork. Core tip text still follows UI. |
| HST template category display names | `scripts/build-extensions.py:39`, `:85`; `E/Paths.xcu:8`; `U/sfx2/source/doc/doctemplates.cxx:1183`, `U/sfx2/source/doc/doctemplateslocal.cxx:162` | Three fixed vi `default-ui-name` attributes, not ordinary xml:lang strings. Supply bilingual category labels and select at runtime only for bundled HST directory/group IDs; preserve user renames and template files. Verify template cache refresh after restart. |
| Installer windows — exception | `scripts/windows/msi-vietnamese-base.py:10`, `:116`; `P/hst-packaging-vi-descriptions.patch:8`; `scripts/linux/make-single-deb.py:44`, `:104`; `scripts/macos/make-dmg-background.py:28` | Keep Windows MSI, Linux package descriptions and DMG instructions vi, independent of Office profile. Installer patches map to `U/scp2/source/ooo/packinfo_*.txt` and `U/sysui/desktop/debian/control:1`; no runtime helper there. |
| Static OS application copyright | `P/hst-copyright.patch:29`, `:874` → `U/include/default.rc:56`, `U/sysui/desktop/macosx/Info.plist.in:1976` | Fixed PE/Finder strings cannot read per-profile UILocale. Keep in inventory; needs artifact-level decision, not a fake runtime fix. |

The remaining XCU registrations contain no visible language literals: `E/Jobs.xcu:4`, `E/ProtocolHandler.xcu:5`, `E/Paths.xcu:8`. Extension-manager descriptions already have English/vi variants (`E/description.xml:10`). New beta.4 USB-token-setup dialogs, when implemented, must use the same HST selector; only the separate existing PIN UI stays on its current core rule (`docs/BACKLOG.md:91`).

Do not translate ND30 output: the national heading/motto/placeholders and layout are document semantics (`data/vietnamese/nd30.json:69`, `:96`, `:136`; `E/python/hst_office/nd30_layout.py:66`, `:89`). The wizard preview uses the insertion layout (`E/python/hst_office/wizard_nd30.py:109`, `E/python/hst_office/actions.py:44`). Do not change number-format locales, user CSV/encoding content, ordinary menu resources, or core resource-manager defaults to implement the HST policy.

### Addons title approach

**Choose option 4: real vi/en-US Title variants plus a narrowly scoped, read-only lookup in AddonsOptions.** Static XML alone cannot distinguish Default+English OS from explicit English because both have an English configuration-provider locale (`U/desktop/source/app/langselect.cxx:106`; localized Title schema: `U/officecfg/registry/schema/org/openoffice/Office/Addons.xcs:34`).

| Option | Assessment |
|---|---|
| 1. Dispatch/status labels | Menubar supports a string `FeatureStateEvent.State` and updates text (`U/framework/source/uielement/menubarmanager.cxx:308`, `:337`). Current handler is empty (`E/python/hst_office/dispatch.py:89`). Plausible for leaf items, but does not by itself guarantee correct initial labels, popup titles, ribbon text and tooltips. Notebookbar copies configured labels (`U/vcl/source/window/NotebookBarAddonsMerger.cxx:99`, `:112`). More lifecycle work than a shared read path. |
| 2. User-layer Title overrides | `onFirstVisibleTask` occurs after window-show notification (`U/framework/source/services/frame.cxx:2594`, `:2620`). OnStartApp is earlier, but Addons data reload is asynchronous and is not proof existing widgets rebuild (`U/framework/source/fwe/classes/addonsoptions.cxx:479`, `:1946`). Needs startup/Options/shortcut synchronization, administrative-write handling and cleanup that cannot run after uninstall. Reject persistent derived state. |
| 3. Duplicate commands/menus with visibility | Menubar accepts visibility status (`U/framework/source/uielement/menubarmanager.cxx:343`), but duplicates command IDs, contextual registration and ribbon maintenance. Adds more failure modes for no product benefit. |
| 4. Policy-aware localized read | Both menubar and ribbon already read Title centrally (`U/framework/source/fwe/classes/addonsoptions.cxx:1273`, `:1346`, `:1461`). Select the appropriate stored language there before widget construction. No startup menu mutation or profile cleanup. Preferred. |

Implementation: store genuine `xml:lang="vi"` and `xml:lang="en-US"` variants, retain a nonempty default fallback, and read the selected Title only for the bundled HST namespace and `org.hst.office.vi:` commands. Use the property path before synthetic submenu URLs are generated; retain root HST and the invariant language-selector subtree. Exclude `org.hst.office.update:*` explicitly even inside the HST subtree. Cover `ReadMenuItem`, `ReadPopupMenu`, and `ReadNotebookBarItem`; do not globally localize the whole Addons tree to Vietnamese.

Use a read-only configuration access with locale `"*"` and the existing localized selector path, e.g. `.../Title/['*en-US']` or `.../Title/['*vi']`. This mechanism is implemented at `U/comphelper/source/misc/configuration.cxx:51` and exercised by `U/configmgr/qa/unit/test.cxx:322`; it preserves configuration layering without generating user entries. Keep normal lookup for unrelated add-ons. Missing HST title/catalog is a package-validation failure; retain a visible default label and diagnostics if encountered at runtime.

Menus/ribbon are correct on the **first** construction after restart because lookup occurs before insertion, with startup policy already initialized. Restart Later keeps the old active policy; new windows in that process should also use it. Uninstall/disable removes the extension registration without leaving this feature's user Title overrides; profile reset returns to Default. Existing user-customized labels remain user data and must not be deleted by a broad cleanup. Locale lock does not prevent read-only Title lookup; explicit administrator Title customizations still follow normal configuration precedence. Re-enable takes effect on a fresh process.

### Restart semantics

The shortcut is `HST > Ngôn ngữ giao diện > Tiếng Việt / English / Theo máy`, permanently labeled as specified. It writes exactly `vi`, `en-US`, or empty through ConfigurationUpdateAccess, never by editing live registry XML. Verify commit success before presenting `Khởi động lại ngay?`; on failure show a localized explanation and do not restart. Mark the pending selection and explain that it applies on restart. No write or prompt for an unchanged choice. Use the same predicate, pack availability checks, and lock rules as Options (`docs/BACKLOG.md:92`; current write seam `U/cui/source/options/optgdlg.cxx:1167`).

Use a shared native language-restart coordinator for Options and the shortcut, retaining the existing restart manager for process relaunch. Add a verified session checkpoint/reopen path rather than an extension subprocess or a URL-only reopen list. The native recovery service already tracks documents/views and snapshots (`U/framework/source/services/autorecovery.cxx:3829`, `:3832`, `:3848`), while startup restores sessions (`U/desktop/source/app/app.cxx:2139`).

Required transaction: collect all open models/views, including parked tabs; obtain normal user save decisions without destroying other documents; complete and verify necessary recovery snapshots; abort on cancellation, write failure, unavailable secure storage or veto; only then mark a restart session and terminate. After successful relaunch, restore intended documents/views once and clear the restart marker. Keep unnamed changes recoverable; preserve saved originals unless the user chose Save; do not persist credentials. Failed/canceled restart leaves the language preference pending and keeps surviving documents usable. Preserve native crash recovery independently.

Do **not** blindly call `doSessionQuietQuit`: it resets modified flags and closes documents (`U/framework/source/services/autorecovery.cxx:3875`). Its SessionData flag is set only in that distinct path (`:3883`); simply calling SessionSave then ordinary termination is not a proven integration either. Phase 2 must add completion/error checks and cancellation cleanup around the native session lifecycle and prove probe 12. This is a concrete required implementation boundary, not a claim that existing restart already meets the backlog requirement.

### Admin lock

Use a shared policy OXT with the same manifest/media type as `scripts/release/build-update-policy-oxt.py:30`, but a separate policy payload targeting the core preference:

```xml
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry"
                    oor:name="Linguistic" oor:package="org.openoffice.Office">
  <node oor:name="General">
    <prop oor:name="UILocale" oor:op="fuse" oor:finalized="true">
      <value>en-US</value>
    </prop>
  </node>
</oor:component-data>
```

Core Linguistic schema already exists; the update extension's schema-order caveat does not automatically apply here. Test effective layer ordering with conflicting profiles. A policy of empty means locked Default, not locked English. A policy of en-GB means explicit English after the resolver fix. Use C++ generated `UILocale::isReadOnly()` or UNO property READONLY on the actual preference, including ancestor finalization. Disable selector choices in both UIs, expose “managed by your administrator” help text, and recheck at dispatch/commit time to handle a policy change while a dialog is open. Catch a write failure, reread the effective setting, and preserve documents. Mandatory-only metadata is not an edit lock; use finalization.

## Tests

Proposed files only; none were added by this audit.

- **Pure predicate and snapshot tests:** `tests/unit/test_ui_language.py` plus a small unotools CppUnit target patterned after `U/unotools/CppunitTest_unotools_configpaths.mk:10`. Share cases for absent/empty, en/en-US/en-GB/EN-us, vi/vi-VN, eng/enough/en_US, whitespace and malformed suffixes; verify C++/Python parity, locked values, failed reads, startup capture and pending-choice isolation. Test the actual raw-config adapter and English-to-en-US resolver, not just two copied predicates.
- **Catalog/package tests:** recursively compare key and placeholder sets; verify the 49 translated leaves; map URL→Title separately for menubar/ribbon/help rather than collecting all text into sets (`scripts/check-extensions.py:128`). Validate full bilingual asset/help inventory, unchanged welcome vi path, correct custom HelpRootURL behavior, and no generated Title overrides. Extend guide traversal if an English subdirectory is introduced (`tests/unit/test_user_guide.py:16`).
- **C++ integration tests:** English-alias resolution without preference clearing, missing pack/registration, Options alias display with unchanged Apply, property/ancestor finalization, and scoped Addons localized reads including the update exception. Test another unrelated add-on and a user-customized Title to prevent a global locale override regression.
- **Runtime:** add `tests/runtime/check-language-selection.py` implementing probes 1–14. Keep exact title/body/control/menu/ribbon assertions and evidence JSON; do not use direct catalog injection as dispatch proof. Revise `check-vi-intro.py` to retain welcome/installer exceptions and assert both new-language states, rather than dropping conflicting tests.
- **Data/lifecycle regression:** compare ND30 output and Undo, CSV types/formulas/leading zeros, conversion formatting, open-document count/views/content after restart, Cancel/veto behavior and recovery. Native Windows/macOS checks remain separate required evidence, not Linux substitutes.
- **Documentation on implementation:** update the smallest owning surfaces: `docs/EXTENSION_CONTRACT.md:12`, `:30`, `docs/BACKLOG.md:92`, and relevant runtime-test usage. No evergreen docs were changed in this audit. Preserve glossary placeholders/access keys (`docs/L10N_GLOSSARY.md:33`).

## Phase 2 effort

Engineering estimate, not a measured schedule. Assumes builders, operator and native test hosts are available; elapsed full builds, copy approval and hardware waits are additional.

| Work | Person-days |
|---|---:|
| Shared policy, startup snapshot, alias resolver, Options lock/display fixes, unit tests | 1.5–2.5 |
| C++ forced-text sites, scoped Addons reads, Windows notice | 1.5–2.5 |
| Python selector, 49 catalog translations, common messages/picker handling, shortcut UI/lock | 1.5–3 |
| Safe restart/checkpoint/reopen integration and failure/recovery tests | 2.5–4 |
| Bilingual banner/tip assets, 19-page guide/screenshots, template category routing | 2–4 |
| Matrix automation, Linux execution, native Windows/macOS checks and final review | 2–3 |
| **Total** | **11–19 person-days** |

The range includes the entire requested language shortcut and document reopening, not only text replacement. Existing native session machinery reduces reinvention but requires an early integration check before estimating closer to the lower bound. USB-token auto-detection itself is the separate beta.4 feature at `docs/BACKLOG.md:91`; only its future language-selection contract is included here. Static artifact policy decisions below can alter packaging effort.

## Unresolved questions

1. **Static application metadata:** PE `LegalCopyright` and Finder `NSHumanReadableCopyright` cannot follow two users' different Office profiles (`U/include/default.rc:56`, `U/sysui/desktop/macosx/Info.plist.in:1976`). Owner must choose bilingual static metadata, OS-language resources, or explicitly limit this rule to runtime UI. They are not silently classified as installer exceptions.
2. **Distributed full LICENSE artifact:** should its existing bilingual HST preface remain bilingual outside the application, while the runtime notice/view selects one language, or must packaging produce two full artifacts? Evidence: `U/readlicense_oo/license/license.xml:11`, `U/sfx2/source/appl/appserv.cxx:339`. Do not translate or remove substantive third-party license text.
3. **Runtime evidence pending:** real beta.2 profile provenance, first-render Addons behavior, native picker chrome, checkpoint failure/reopen coverage, Windows association state/token UI, and macOS installer behavior remain operator checks. Static review establishes the implementation seams, not PASS for those scenarios.

## Runtime evidence (operator, after Codex static pass)

Run by the coordinating agent, not Codex. Snapshot: hard-linked copy of `upstream/libreoffice/instdir` (libmergedlo 09:22) at `tests/output/codex-lang/instdir-snap`; own Xvfb `:91` (stopped at end); soffice as `hstbuild` via `tests/runtime/hst_gui.py`; probe script `tests/output/codex-lang/lang_probe.py`; raw results `tests/output/codex-lang/probe-results.jsonl`. Observations: raw `Linguistic/General/UILocale` after start, resolved `Setup/L10N/ooLocale`, config label `.uno:Open` (Writer), new Writer doc title (sfx2 resource string), HST `m1` Addons Title as read through the localized provider, process alive. Profile seeded as fresh `registrymodifications.xcu` items; LANGUAGE unset.

| Probe | Seed UILocale | OS LANG | UILocale after start | ooLocale | Core UI | HST m1 title | Alive |
|---|---|---|---|---|---|---|---|
| matrix | Default / en-US / vi | en_US | "" / en-US / vi | en-US / en-US / vi | en / en / vi | vi (all) | yes |
| matrix | Default / en-US / vi | vi_VN | "" / en-US / vi | vi / en-US / vi | vi / en / vi | vi | yes |
| matrix | Default / en-US / vi | fr_FR, ja_JP | "" / en-US / vi | en-US / en-US / vi | en / en / vi | vi | yes |
| aliases | `en`, `en-GB`, `EN-us` | en_US | **"" (cleared)** | en-US | en | vi | yes |
| aliases | `en-GB`, `EN-us` | vi_VN | **"" (cleared)** | **vi** | **vi** | vi | yes |
| aliases | `vi-VN` | en_US | `vi-VN` kept | vi | vi | vi | yes |
| unsupported | `fr`, `xx-garbage` | en_US | "" (cleared) | en-US | en | vi | yes |
| profile carry | Default; OS vi → OS en, same profile | | "" | vi → en-US | follows OS each start (no stale ooLocale) | vi | yes |
| live switch | set en-US via UNO while running (OS vi) | | en-US | vi (unchanged) | vi until restart; after restart en | vi | yes |
| reset to Default | "" via UNO, restart (OS vi) | | "" | vi | vi | vi | yes |
| partial pack: `program/resource/vi` removed, Langpack-vi.xcd kept | Default/vi | vi_VN, en_US | ""/vi | vi | **mixed**: config labels vi (`~Mở...`), resource strings en (`Untitled 1`) | vi | yes |
| pack gone: resource/vi + Langpack-vi + registry_vi + fcfg_langpack_vi removed | vi | en_US, vi_VN | **"" (cleared, choice lost)** | en-US | en | vi | yes |
| admin lock: `share/registry/zz-hst-lock-test.xcd` finalized UILocale=en-US, user profile vi | vi | vi_VN | en-US | en-US | en | vi | yes; UNO write → IllegalArgumentException |

Runtime confirms LS-02 (aliases cleared; on a vi OS an `en-GB` hand-edit ends up fully Vietnamese), LS-03 (mixed UI, no crash; registration-missing clears the user's vi choice permanently), LS-04 (fr/ja Default → en-US core, HST still vi), LS-05 (no live switch; restart required), LS-07 (finalized value wins and rejects writes). No crash, hang or document mutation in 30 starts. Not run here: Options-dialog GUI round trips with restart prompt, unsaved-document restart, real beta.2 profile, Windows/macOS natives, RTL/CJK document rendering (probes 2, 3, 7, 11, 12, 14).

## Coordinator verification notes

- Verified against source: `langselect.cxx:80-117` (clear-on-mismatch, fallback chain), `langhelp.cxx:106-160` (PackageKit request only for build langs `en-US vi`, so fr/ja never trigger an install prompt; fallback en-US), `hst-windows-fileassoc-vi.patch:17,45` (forced `vi-VN` `Translate::Create`), `hst-digital-signature.patch:223-226` (PIN uses UI `rResLocale`, not forced → no change needed), `update_ui.py:43` (reads resolved ooLocale), `dispatch.py:62,66` (hardcoded `load_locale("vi")`), `comphelper/configuration.cxx:51` (`['*<locale>']` localized-path selector exists), `addonsoptions.cxx:1273` (`ReadMenuItem` central Title read).
- `locales/en.json`: my count is 46 Vietnamese leaves (menu, nd30, undo), Codex says 49; same categories, count differs by regex. The `Addons.xcu` header requires labels to equal both catalogs' `menu` (checked by `scripts/check-extensions.py`), which is why en.json carries vi menu text today; that check must change with Phase 2.
- Scope beyond the owner list: Codex's inventory adds the offline guide (19 vi HTML pages + screenshots), tip-of-the-day images, HST template category names and static PE/Finder copyright. These are not in the owner's switch list (About, Start Center intro/banner, licence notice, HST menu + dialogs incl. NĐ 30, file-association notice, PIN). Treat them as owner decisions, not Phase 2 defaults. Core Phase 2 without them: ~7–11 person-days (Codex total 11–19 includes them plus a heavyweight checkpoint/reopen coordinator).
