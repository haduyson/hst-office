**Feature UX audit — 2026-10-31.** Five findings: one major, three minor, one cosmetic. Static analysis only; no Office process, display connection, socket listener, or build was started. The supplied install's updater is stamped **beta.2**, although the source release is beta.3 (FEA-05).

Read `README.md`, `docs/BACKLOG.md`, `docs/L10N_GLOSSARY.md`, `docs/TEMPLATES.md`, and the complete `tests/runtime/hst_gui.py`. Preserved the owner's decisions and existing workspace changes.

Evidence: static extraction and reproduction output (`tests/output/codex-ux-audit/features/static-evidence.log`), 43 passing focused unit tests (`tests/output/codex-ux-audit/features/static-unit-tests.log`), coordinator probe (`tests/output/codex-ux-audit/features/probe.py`). Source paths below are relative to `/home/office`; installed paths use `upstream/libreoffice/instdir/`.

**FEA-05 — Installed updater has the previous release identity**

- Area: Update checking / built artifact consistency.
- Severity: **major**. Confidence: **confirmed-static**.
- Reproduce: Compare `data/hst/release.json` with the installed extension's `data/release.json`; import the installed `hst_office.update_fetch` and call `release_info()`. Then use the update-check menu with a valid release manifest.
- Expected: This beta.3 build supplies `1.0.0-beta.3` to update comparison, current-version text, and its request User-Agent.
- Actual: Source is beta.3; the installed extension returns `{'release': '1.0.0-beta.2', 'channel': 'beta', 'test_mode': False}`. The updater therefore evaluates the wrong installed version. A future beta.3 manifest would be treated as newer; that network/UI consequence has not been exercised. The checked-in manifest is still beta.2, and local selection returns `None`.
- Evidence: `data/hst/release.json:3`; `upstream/libreoffice/instdir/share/extensions/hst-vietnamese-tools/data/release.json:2`; `extensions/hst-vietnamese-tools/python/hst_office/update_fetch.py:33`; `extensions/hst-vietnamese-tools/python/hst_office/update_job.py:35`; `extensions/hst-vietnamese-tools/python/hst_office/update_logic.py:134`. Command output: `static-evidence.log:54` records the source stamp, installed `release_info()`, and local manifest selection.
- Suspected fix: Rebuild/restage the bundled extension using `scripts/build-extensions.py:60` and its existing packaging path; verify `data/release.json` in the final install. Source `data/hst/release.json` already has the requested version.

**FEA-01 — Update menu labels remain Vietnamese in English UI**

- Area: HST menu, Help menu, notebookbar update action.
- Severity: **minor**. Confidence: **confirmed-static**.
- Reproduce: Start with `en_US.UTF-8`, open Writer, and inspect the HST and Help update entries.
- Expected: English menu labels, consistent with the owner's OS-language menu policy.
- Actual: The `en-US` values are `Kiểm tra cập nhật…` and `Kiểm tra cập nhật HST Office…`; the notebookbar also has the Vietnamese label. Other HST actions have English values. This finding concerns menu labels, not the language of update-result dialogs.
- Evidence: `extensions/hst-vietnamese-tools/Addons.xcu:93`, `:107`, `:197`; the installed Addons.xcu is byte-identical. Parsed installed XML output: `static-evidence.log:15` through `:17`.
- Suspected fix: English `Title` values in `extensions/hst-vietnamese-tools/Addons.xcu`, then rebuild/restage the extension.

**FEA-02 — English extension-install confirmation omits the HST notice**

- Area: User-selected `.oxt` installation / legal confirmation.
- Severity: **minor**. Confidence: **confirmed-static**; rendered dialog still needs runtime capture.
- Reproduce: Start with `en_US.UTF-8`; choose a local `.oxt` in Extension Manager and inspect its confirmation before continuing.
- Expected: The Vietnamese installation/third-party notice and Vietnamese confirmation controls in both UI languages, as requested for this audit.
- Actual: The body/title use the current UI locale. English falls back to the generic “You are about to install the extension…” text, which lacks the HST data-access and responsibility notice. Buttons explicitly choose Vietnamese only when the UI language is `vi`; English uses OK/Cancel. Default Cancel and the confirmation itself remain implemented.
- Evidence: `upstream/libreoffice/desktop/source/deployment/gui/dp_gui_dialog2.cxx:152`; `upstream/libreoffice/desktop/source/deployment/misc/dp_misc.cxx:513` uses `Translate::Create("dkt")`; English source string at `upstream/libreoffice/desktop/inc/strings.hrc:80`. `gettext.GNUTranslations` extraction from installed `program/resource/vi/LC_MESSAGES/dkt.mo` confirms the HST notice exists only in that translation (`static-evidence.log:36` and `:37`).
- Suspected fix: `patches/libreoffice/hst-extensions.patch`, in `DialogHelper::installExtensionWarn`; select the required Vietnamese legal resources explicitly for this dialog. Preserve file-only installation and default Cancel.

**FEA-03 — Malformed CSV error exposes English parser details**

- Area: HST Sheets → HST → Import CSV → preview/error feedback.
- Severity: **minor**. Confidence: **confirmed-static**.
- Reproduce: In Vietnamese UI, choose a UTF-8 CSV containing `a,b` followed by an unterminated quoted field (`"unterminated`).
- Expected: A Vietnamese explanation of the invalid quoting, optionally with a localized row number.
- Actual: The preview is `Tệp CSV bị lỗi định dạng. row 2: unexpected end of data`. The localized prefix is followed by Python's untranslated parser message. Import is correctly refused; no data-loss claim is made.
- Evidence: `extensions/hst-vietnamese-tools/python/hst_office/csv_import.py:78`; `extensions/hst-vietnamese-tools/python/hst_office/wizard_csv.py:54`. Running the installed pure parser and assembling its UI string produces the exact output at `static-evidence.log:52`.
- Suspected fix: Those two Python files and `extensions/hst-vietnamese-tools/locales/vi.json` / `en.json`; expose a localized error code/row to the user and retain raw parser diagnostics in logs.

**FEA-04 — NĐ 30 inserts an English Undo label in Vietnamese UI**

- Area: Writer → NĐ 30 wizard → Edit/Undo action text.
- Severity: **cosmetic**. Confidence: **confirmed-static**; final menu rendering needs runtime capture.
- Reproduce: In Vietnamese UI, insert an NĐ 30 document and inspect the next Undo action.
- Expected: The action description follows the Vietnamese editing UI.
- Actual: The extension unconditionally names the undo context `Insert ND30 document`. The action title is supplied directly to the undo manager, so the localized Undo prefix receives an English description.
- Evidence: `extensions/hst-vietnamese-tools/python/hst_office/nd30_writer.py:80`; `extensions/hst-vietnamese-tools/python/hst_office/undo.py:21`; `upstream/libreoffice/sfx2/source/view/viewfrm.cxx:1082`. Installed-source extraction: `static-evidence.log:53`.
- Suspected fix: Pass a localized undo title from `actions.py` through `nd30_writer.py`, with strings in the extension locale files.

**Requested configuration evidence**

These are recorded defaults, not additional findings. Parsed installed registry: Writer `writer8`, Sheets `calc8`, Slides `impress8`; `WarnAlienFormat=true`; `Office.Recovery/AutoSave/Enabled=true`, `TimeIntervall=10` minutes, `UserAutoSaveEnabled=false`; `DocumentTabs=true`. Recovery snapshots and saving back to the user's original file are distinct. The probe records these defaults before shortening the recovery interval in its disposable profile.

Installed `HelpRootURL` is `vnd.sun.star.expand:$BUNDLED_EXTENSIONS/hst-vietnamese-tools/help/index.html`. `Paths.xcu` and `template/groupuinames.xml` register the three HST groups; all 18 installed archives have the expected titles and MIME types. The ten localized tip PNGs are byte-identical to the installed images; `cui.mo` contains 224 translated tip entries. These checks establish packaging/configuration, not GUI execution.

`Addons.xcu`, `ProtocolHandler.xcu`, `Jobs.xcu`, the Python entry point, dispatchers, and relevant action/error paths were inspected. The startup jobs and top-level dispatch paths catch exceptions. No reproducible unhandled exception is asserted. Thirty-nine source extension Python/configuration/locale files match their installed counterparts; the separately generated release stamp is the mismatch described above.

**Probe execution and interpretation**

Run outside the sandbox, as root, with Xvfb already on `:94`:

```bash
python3 -B /home/office/tests/output/codex-ux-audit/features/probe.py
```

The script uses `hst_gui.setup_uno` and one `hst_gui.Office` at a time on **22943**. It refuses an occupied port, uses unique profiles below `features/work/`, and always calls `office.stop()` in `finally`. Every scenario has a timeout; blocked UNO work invalidates that session before the next language starts. No helper or installed source is edited. An 800-second work alarm leaves time for bounded cleanup. `results.json`, `probe.log`, browser-call logs, documents, and numbered `shots/*.png` stay under the requested output directory.

Coverage includes visible New/Open/Save/Save As in all three modules, ODF/OOXML reopen checks, Vietnamese text, leading-zero text, numeric/formula values, slide counts, PDF text and font embedding via `pdftotext`/`pdffonts`, native Open/Save As dialog capture, GUI OOXML Save warning capture, print-preview enter/exit, all 18 templates in both locales, Template Manager, NĐ 30 insertion, F1 handoff, update-menu wiring/offline failure, tips, `.oxt` cancellation/confirmation/installation, and tabs on/off/on. The extension fixture contains a real existing template and configuration only; it is installed solely in the disposable profile.

Crash recovery runs in Vietnamese. It first verifies the real defaults, sets the interval to one minute, waits for a real snapshot containing unsaved text, checks the exact process executable/profile, kills only that owned `soffice.bin` PID, and restarts the same profile. The helper always injects `--norestore`; a launcher written under that profile's work directory removes it on the recovery restart. If no valid snapshot appears within 90 seconds, the crash is skipped and recorded as blocked.

The offline update check uses an invalid proxy address; no test server or second UNO port is opened. A logging `xdg-open` stub verifies F1 receives the expanded existing file URL, but does not test browser rendering. Screenshots of translations, hidden online links, and preview transitions that cannot be established from controller identity are marked `ok: null` for review. A format warning is captured for review, not automatically called a defect. UNO storage tests alone do not establish GUI warning behavior.

The probe is intended to confirm exactly these reported findings:

| Finding | Probe evidence |
|---|---|
| FEA-01 | Actual merged HST/Help menu labels in both locales (`FEA-01-vi`, `FEA-01-en`). |
| FEA-02 | Installation confirmation title/body screenshots in both locales, plus Cancel/Continue behavior (`FEA-02-*`, `FEA-R-*-OXT`). |
| FEA-03 | Malformed CSV preview screenshots in both locales (`FEA-03-*`). Human review is required. |
| FEA-04 | Actual undo-manager action title after wizard insertion (`FEA-04-*`), with wizard/document screenshots. |
| FEA-05 | Re-read the installed updater stamp at execution (`FEA-05`). This is an artifact check, not a live-server update test. |

Validation performed here: 43 existing focused unit tests passed; the probe's Python syntax and generated `.oxt` XML/ZIP structure were checked without running Office (validation log (`tests/output/codex-ux-audit/features/probe-validation.log`)). Exit status is 1 for failed checks, 2 for review/blocked checks without failures, and 0 only when every check passes. GUI execution, runtime timing, rendering, and recovery remain unverified until the coordinator runs the probe. No blocker, crash, content-loss, or PDF-export defect is inferred from the absence of runtime evidence.

Unresolved question: should the coordinator restage the beta.3 extension before running acceptance tests, or retain this exact beta.2-stamped install to capture FEA-05? The probe can inspect either and records the stamp it actually sees.
