# Phase 05 — Bundled LibreOffice-native Vietnamese tools

**Status:** pending. **Depends on:** 00; UNO runtime needs 01/03. **Parallelizable:** pure data/logic and UI after contract freeze; one integration owner.

## Context and requirements

Choose one bundled **Python-UNO `.oxt`** for ND30, conversion and spreadsheet tools; use native dialogs and dispatch. No ONLYOFFICE bridge, Node runtime, web iframe or reduced macro-security settings in the installed product. Separate pure logic from UNO adapters. Python import modules use normal underscore names; standalone scripts use kebab-case.

## Exact files

- Create `extensions/hst-vietnamese-tools/description.xml`, `META-INF/manifest.xml`, `Addons.xcu`, `ProtocolHandler.xcu`, `python/hst_office/__init__.py`, `python/hst_office/dispatch.py`, `python/hst_office/dialogs.py`, `python/hst_office/nd30.py`, `python/hst_office/encoding.py`, `python/hst_office/sheets.py`, `python/hst_office/undo.py`, `locales/vi.json`, `locales/en.json`.
- Shared data: `data/vietnamese/nd30.json`, `data/vietnamese/encoding-maps.json`, `data/vietnamese/number-formats.json`, `data/vietnamese/provenance.json`; create `scripts/build-extensions.py`, `scripts/check-extensions.py`, `tests/unit/test_nd30.py`, `test_encoding.py`, `test_sheet_formats.py`, `test_csv_import.py`, `tests/runtime/check-extensions.py`.
- Fixtures: `tests/fixtures/vietnamese/manifest.json`, `nd30-cases.json`, `encoding-vectors.json`, `csv-cases.json`. Create `docs/ENCODING_SOURCES.md`; update `docs/EXTENSION_CONTRACT.md` after the registration spike.
- Conditional dictionary files: `dictionaries/vi-VN/provenance.json`, `LICENSE`, `vi_VN.aff`, `vi_VN.dic`, `dictionaries.xcu`; acquire only a redistributable reviewed source. Autotext outputs `dist/autotext/hst-nd30.bau` use 03's manifest.

## Steps

1. Spike a real Python UNO dispatch component in a clean HST profile: build OXT, register component via the pinned Python loader/manifest format, show a native dialog, insert a paragraph, Undo, save DOCX and reopen. Verify module discovery, Python ABI, bundled extension startup and macro-security behavior. Do not code all features until the spike passes. [UNO integration guide](https://help.libreoffice.org/latest/is/text/shared/guide/integratinguno.html) supplies the service model; pinned SDK examples define exact manifest registration.
2. Port archive ND30 data/layout/validation algorithms with source SHA and headers. Revalidate against `docs/VIETNAMESE_OFFICE_SPEC.md`, not merely archive output (for example rule widths based on text length). Keep data shared with templates. Wizard covers seven document types and all user-entered fields/placeholders; creates a new document or explicitly confirmed insertion, applies A4/ND30 styles/margins, first-page numbering rules and one undo transaction. Preview and Cancel do not write. Reject protected/unsupported selections before mutation.
3. Converter uses reviewed TCVN3/VNI mapping with independent vectors for all Vietnamese letters, cases, accents, multi-character sequences, punctuation and mixed Unicode. Explicit source encoding is required; detection is only a suggestion. Preview preserves formatting runs; before Apply verify document/selection/content still match. Convert text without rewriting fields, tracked changes or unsupported multi-ranges silently. One Undo restores text and formatting, including length-changing mappings. [XUndoManagerSupplier](https://api.libreoffice.org/docs/idl/ref/interfacecom_1_1sun_1_1star_1_1document_1_1XUndoManagerSupplier.html) is the integration point, not proof every UNO setter is automatically undoable; test and add a proper undo action where needed.
4. Sheet commands apply VND, `dd/mm/yyyy` and percent using locale-aware UNO number formats; verify underlying values/formulas unchanged, decimal/grouping behavior and date serial/null-date handling. Do not rewrite formula separators. Formats come from shared data, with [XNumberFormats](https://api.libreoffice.org/docs/idl/ref/interfacecom_1_1sun_1_1star_1_1util_1_1XNumberFormats.html) for registered keys.
5. CSV import supports strict UTF-8 BOM/no-BOM, delimiter/quote/multiline/empty fields, preview, type selection and safe text default preserving leading zeros/formula-looking strings. Malformed bytes produce a choice/error, never silent replacement. Test `=`, `+`, `-`, `@`, embedded tabs/newlines, 5,000 rows, large-input bounds, selected destination, overwrite confirmation, protected cells, cancellation and single Undo. Do not evaluate formulas or fetch external links; rollback partial writes on failure and never auto-retry an uncertain mutation.
6. Add vi/en labels, keyboard/focus/accessibility, missing-font messages and HST help. Ship data, icons, license/source metadata inside OXT. Integrate into the installer-managed **bundled extension** location using the pin's deployment mechanism; validate first-run discovery as an unprivileged user with a read-only installation. Copying `.oxt` beside the executable is insufficient. Coordinate final staging with 07.
7. Audit an upstream/Hunspell Vietnamese dictionary and exact aff/dic version/license. When allowed, bundle with notices and language registration; test correct words, misspellings/suggestions and accented UTF-8. If unavailable/incompatible, record dictionary blocker and no spellcheck claim. Do not disable dictionary loading to mask context-menu delay. Generate ND30 phrase autotext without real identities.

## Validation commands

After implementation; pure tests run without a desktop, runtime checks need the source-built suite:

```bash
python3 -m unittest discover -s tests/unit -p 'test_*.py'
python3 scripts/build-extensions.py --output dist/extensions
python3 scripts/check-extensions.py --directory dist/extensions
python3 tests/runtime/check-extensions.py --soffice upstream/libreoffice/instdir/program/soffice --extension dist/extensions/hst-vietnamese-tools.oxt --fixtures tests/fixtures/vietnamese/manifest.json --output tests/output/extensions
```

Local readiness requires real insert/preview/Cancel/Undo/redo/save/reopen, numeric/formula invariants and independent golden vectors with OXT installed into an isolated build-tree test profile. This permits packaging; final clean bundled-startup acceptance belongs to 07/08. Validators reject missing files, unsafe ZIP paths, remote resources, invalid registration and absent notices. Build twice under the locked toolchain and compare normalized ZIP hashes; test malformed input and rollback against real documents, not mocked UNO calls.

## Risks and rollback

Python discovery and Undo vary by operation; the spike must expose those contracts. Unsupported selections fail before writing with an explanation, not silent partial conversion. Keep last good OXT and user profile backup for test rollback; update package-owned extension files only. Removing an extension must never delete user documents, personal templates or autotext.
