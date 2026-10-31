# Windows ND 30 wizard: findings, fix, smoke

## Root cause
- Wizard code is NOT broken on Windows: beta.2 MSI (installed on windows-2022, run 41161395730) opens the dialog; all modules import, nd30.json loads, handlers register.
- Real Windows defect: dialog is ~1200 px wide x ~590 px high at 100% (AppFont units, Segoe UI). On a 1024x768 runner the right half (preview, Insert button) is cut off (screenshot in artifact windows-smoke-41161395730/screens/18-*). 1366 px screens at 125% scaling are also too narrow. Fix: dialogs.py measures peer vs work area; wizard_nd30._compact drops the preview column (form 610 px wide) -> fits. Verified run 41162942312 (screens/17-_134x44.png).
- Discoverability (owner finding): entry only in Writer HST menu + "Extension" ribbon tab. Now offered in HST menu in Start Center/Writer/Calc/Impress; outside Writer opens new Writer then wizard (dispatch._frame_for). ImportCsv same with Calc.
- Errors were invisible on Windows (no console): dispatch now also appends tracebacks to %TEMP%\hst-office-errors.log.

## Language rules implemented
- All HST menu/ribbon labels and dialogs Vietnamese (Addons.xcu plain + en-US + vi same text; en.json menu/nd30/undo = vi; dispatch loads vi). NĐ 30 label: "Văn bản theo NĐ 30…".
- Update check follows UI language (Addons en/vi; update_texts.py en/vi dialog+infobar). Verified on Windows en-US: dialog title "Check for Updates"; beta.2 baseline showed Vietnamese.

## Windows smoke (new): .github/workflows/windows-smoke.yml + tests/runtime/check-windows-smoke.py
- workflow_dispatch inputs: release_tag (default v1.0.0-beta.2), overlay_extension (build .oxt from commit, replace share/extensions/hst-vietnamese-tools in installed MSI). Verifies MSI sha256 vs release SHA256SUMS, msiexec /qn, bundled python.exe, screenshots, artifact (logs, pyuno.log, soffice.err, extension as installed).
- Runs: 41161151406 (first, failed at harness: wrong service name), 41161395730 (overlay, showed cut-off wizard), 41162026489 (baseline beta.2: all PASS, update dialog Vietnamese), 41162942312 (overlay HEAD: success).
- All PASS on Windows (overlay): imports x8, data load, services DispatchProvider + UpdateDispatchProvider, Nd30Wizard, ConvertEncoding (refusal box without selection), ShowSolutions (welcome), update Check (English), ImportCsv, FormatDate/Vnd/Percent, help root file exists.
- Caveat: window size reading right after creation is unreliable (reports 134x44); size evidence is the screenshot. OVERSIZE flag only fires when size is settled.

## Linux
- unit tests 121 OK; ci-quality 0 failures; check-extensions runtime on Xvfb :92 (stopped): ND30 modal dialog OK/Cancel PASS. 4 FAILs exist identically on the pre-change commit f434f8d (stale expectations: "7 commands" now 8, toolbar removed, unknown-command, calc bridge crash) - not caused by this work.
- tests/unit/test_hst_menu_visibility.py locks Addons.xcu contexts and label languages.

## Not done / concerns
- Ribbon: button on the Home tab needs core .ui patch (sw notebookbar.ui) - not touched; addon item stays on "Extension" tab. Needs your decision.
- ConvertEncoding in Calc not implemented (logic is Writer-only).
- No runtime check of ribbon/Start Center menu rendering (only static unit test + dispatch). No new screenshot / help images (nd30-wizard.png unchanged); help text updated (NĐ 30, CSV pages, labels renamed).
- Height still ~590 px at 100%; at >=125% scaling on 768-px screens may not fit.
- Update-check help page does not exist.
