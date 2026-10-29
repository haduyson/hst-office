# Phase 08 — Real document and GUI qualification

**Status:** pending; native Windows/macOS and Microsoft Office comparison BLOCKED. **Depends on:** 07 and Linux 04. **Parallelizable:** fixture authoring; GUI/roundtrip runs serial within resource limits.

## Context and requirements

Qualify the **installed HST package**, not a distribution LibreOffice or a mocked API. Headless conversion alone cannot establish editing, GUI defaults, extension integration or rendering fidelity. Test local files without personal data; retain compact readable evidence after CI artifacts expire.

## Exact files

- Create `tests/fixtures/manifest.json`, `tests/fixtures/writer/cases.json`, `tests/fixtures/sheets/cases.json`, `tests/fixtures/slides/cases.json`, `scripts/generate-test-fixtures.py` (generates licensed technical DOCX/XLSX/PPTX/ODF inputs into ignored output).
- Create `tests/runtime/run-qa.py`, `tests/runtime/office-session.py`, `tests/runtime/check-roundtrip.py`, `tests/runtime/check-gui.py`, `tests/runtime/check-recovery.py`; extend 03/05/06 checks through their owners. Fixture recipes include hashes, invariants and expected render references.
- Create `docs/COMPATIBILITY_MATRIX.md`; result manifest/evidence in `tests/output/qa/`, summarized by `plans/reports/qa-261029-hst-office.md` when actually run.

## Steps

1. Session runner verifies binary/package version and real path, sets isolated `-env:UserInstallation=file:///…`, uses a unique local UNO pipe (no exposed TCP listener), deterministic display `:99`, and tracks all owned PIDs. Check display/pipe owners before launch; no duplicate background process or increasing port on conflict. Cleanup on success/failure/signal and never close a user's office session.
2. Headless: create/open input DOCX/XLSX/PPTX, change identifiable text/cells/formulas/shapes through UNO, save to a new output path with the proper filter, close and reopen in a fresh process, and inspect content plus exported PDF. Confirm edits occurred. Protect originals with pre/post hashes. Require nonempty structurally valid output and text/value/style assertions; exit 0 alone is insufficient.
3. Writer covers Unicode, tables, images, sections, headers/footnotes, comments/track changes, TOC, page breaks and 30–100-page fixture; include DOC/ODT/RTF/TXT capability rows. Sheets covers listed core formulas including a measured XLOOKUP case, Unicode names, date serials, charts/CF/validation/pivot/named ranges, formulas and stored values; include XLS/ODS/CSV. Slides covers master/layouts, notes, images/tables/charts, 16:9/4:3, transitions/animation/media and PPT/ODP limitations. Do not claim unsupported Office features preserved.
4. GUI under Xvfb/GTK3: actual launchers/Start Center/About/Tabbed/classic switch, Vietnamese/English, new/open/edit/save dialogs, all wizard/converter/CSV actions including Cancel/Undo, 18 templates, spellcheck if bundled, keyboard/focus and 100/150/200% scaling. Assert visible and semantic state. Hardware IME/multi-monitor/physical print tests stay NOT RUN until a real desktop/device exists; scripted Unicode insertion is not IME evidence.
5. Exercise save collision, read-only/invalid paths, malformed inputs, AutoRecover, unsaved-close prompt and interrupted save using disposable documents. Disk-full tests use a private capped filesystem/container, never fill the host. No corruption/lost edits or unreported partial mutation. Offline/network checks from 03 run against installed packages; documents never leave the machine.
6. Rerun context-menu matrix on the final candidate and record limits of Xvfb. Matrix rows name case, OS/arch, backend, HST/upstream SHA, package hash, font/locale, expected/actual result and evidence path. PASS/FAIL/BLOCKED/NOT RUN are distinct. No P0 crash/data-loss defect may pass; P1 fidelity issues need disposition, not suppression. Microsoft Office roundtrip awaits a licensed Office machine.

## Validation commands

After implementation; container runner from 07 invokes the same commands with the installed path:

```bash
python3 scripts/generate-test-fixtures.py --manifest tests/fixtures/manifest.json --output tests/output/fixtures
python3 tests/runtime/run-qa.py --soffice /opt/hst-office/program/soffice --mode headless --fixtures tests/output/fixtures/manifest.json --output tests/output/qa/headless
python3 tests/runtime/run-qa.py --soffice /opt/hst-office/program/soffice --mode gui --display :99 --fixtures tests/output/fixtures/manifest.json --output tests/output/qa/gui
python3 tests/runtime/check-roundtrip.py --results tests/output/qa/headless/results.json --verify-originals
python3 tests/runtime/check-recovery.py --soffice /opt/hst-office/program/soffice --output tests/output/qa/recovery
```

The GUI runner itself starts/cleans Xvfb and D-Bus; do not wrap it in a second server. Fail if the installed path is absent. For host-uninstalled operation, run these inside the clean test container, not against an unrelated host binary. Test manifests must reject missing fixture coverage and silently skipped cases.

## Risks and rollback

LibreOffice opening its own output cannot prove Microsoft Office fidelity. Save native and OOXML comparisons separately; preserve source files and report limitations. Revert the responsible patch/extension/template, rebuild, and repeat affected tests plus final shared-contract smoke. Do not weaken expectations to hide output loss.
