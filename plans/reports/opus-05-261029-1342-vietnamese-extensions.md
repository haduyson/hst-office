# Phase 05 – Vietnamese extensions (opus-05)

Status: DONE_WITH_CONCERNS. One Python‑UNO extension `extensions/hst-vietnamese-tools` → `dist/extensions/hst-vietnamese-tools.oxt` (sha256 `8087e275…58e9`, build reproducible twice). Runtime verified on **system LibreOffice 24.2.7.2 only**. **26.8.1 HST verification PENDING the coordinator build.**

## What was built
- ND30 wizard (Writer): 7 types, all fields (+ parent agency), preview, validation, insert at cursor in ONE undo step, optional A4 + ND30 margins (validated ranges) and page numbers hidden on page 1. Layout/validation ported from archive `e0517d7` (provenance in module docstrings) and re-validated against `docs/VIETNAMESE_OFFICE_SPEC.md`: rule widths now follow text length (motto = line length, agency/title = 0.4 of line), symbol upper‑cased, dd/mm/yyyy accepted, control chars rejected.
- TCVN3 (ABC)/VNI → Unicode: explicit encoding required, suggestion only (syllable‑plausibility scoring), preview original/result, per‑run replacement (formatting kept), legacy font → Times New Roman/Arial, `.Vn…H` fonts upper‑case converted letters, fields/footnotes skipped and counted, refusal rules, content re‑verified before Apply, one undo.
- Calc: vi‑VN date/VND/percent formats (values/formulas untouched), CSV import (strict UTF‑8 ± BOM, `, ; Tab`, preview, all‑text default, “numbers where safe” option, limits, overwrite confirmation, protected sheet / out‑of‑sheet refusal, one undo).
- Menu "HST" + toolbar via `Addons.xcu`/`ProtocolHandler.xcu`, vi/en labels (`locales/*.json`, checked equal to the xcu by `scripts/check-extensions.py`), missing Times New Roman warning.

## Files (all under ownership)
`extensions/hst-vietnamese-tools/**` (description.xml, META-INF, Addons.xcu, ProtocolHandler.xcu, locales, description, `python/hst_office_component.py`, `python/hst_office/{__init__,data_files,nd30,nd30_layout,nd30_page,nd30_text,nd30_writer,encoding,encoding_detect,encoding_writer,sheets,csv_import,csv_calc,undo,dialogs,wizard_nd30,wizard_convert,wizard_csv,actions,dispatch,fonts}.py`); `data/vietnamese/{encoding-maps,provenance}.json`; `scripts/{build,check}-extensions.py`; `tests/unit/{test_nd30,test_encoding,test_sheet_formats,test_csv_import}.py` + `_paths.py`; `tests/runtime/check-extensions.py`; `tests/fixtures/vietnamese/{manifest,nd30-cases,encoding-vectors,csv-cases}.json`, `derive-encoding-data.py`; `docs/{ENCODING_SOURCES,EXTENSION_CONTRACT}.md`.
Deviation: runtime helper modules live in `tests/fixtures/vietnamese/runtime/` (`lo_session, recorder, scenarios_*, hst_probe_*`) because the driver alone would exceed 199 lines and `tests/runtime/` was limited to one file. The test‑only probe component (`hst_probe_*`) is built into a separate temporary .oxt and never shipped.

## Commands run and results
| Command | Result |
|---|---|
| `python3 -m unittest discover -s tests/unit -p 'test_*.py'` | 63 tests OK (includes other agents' tests; my 4 files = 35 tests; test_encoding replays all 288 golden vectors) |
| `python3 scripts/build-extensions.py --output dist/extensions --verify-reproducible` | built, 36 files, reproducible: yes |
| `python3 scripts/check-extensions.py --directory dist/extensions` / `--self-test` | PASS / 7 broken packages rejected (unsafe path, missing notices, remote URL, bad XML, missing registered file, network import, stale data) + real package accepted |
| `tests/runtime/check-extensions.py … --mode user --display :99` (system `/usr/lib/libreoffice`, unopkg add into isolated profile as `nobody`) | LibreOffice 24.2, **76 checks, 0 FAIL, 1 BLOCKED** (Calc: system install has no Calc module) |
| same with `--mode bundled --allow-modify-install` on a private copy of a 24.2 tree that has Calc (`scratchpad/o5/lo-full`, copied from opus‑04's extracted debs), extension unpacked into `share/extensions`, fresh profile | **94 checks, 0 FAIL, 0 BLOCKED** (first‑run discovery of a bundled extension proven; extension and probe removed afterwards) |
Logs: `tests/output/extensions-{user,bundled}/{run.log,results.json}` (git‑ignored), samples `nd30-sample.{odt,docx}`.

Runtime evidence in those runs: service/handler registered and dispatchable for all 6 commands, menu (6 items) + toolbar in configuration; ND30 insert of every type, text + A4/30/15/20 mm margins, one undo → empty doc, redo, second undo; selection refusal writes nothing; save .odt/.docx and reopen (text + margins; DOCX `w:pgMar` 20/20/30/15 mm read from XML); TCVN3 run with bold, italic, `.VnTimeH`, a page‑number field → text, formatting, fonts, field untouched, one undo restores everything, redo; tracked changes/no selection/auto‑encoding/tamper refused; real modal dialogs under Xvfb :99 (OK returns fields, Cancel writes nothing, convert dialog needs explicit choice); Calc formats render `05/02/2026`, `1.234.567 ₫`, `12,50%`, values/formulas identical, NullDate 1899‑12‑30; CSV literal text (`00123 =1+1 +84… -5 @x 1e3`, newline), one undo, overwrite/protected/outside‑sheet refusals, 5000 rows (~4 s).

## Facts discovered (also in docs/EXTENSION_CONTRACT.md)
1. Page‑style property writes via UNO are not undoable and wipe the whole undo stack (`unostyle.cxx`, i64460, same in 26.8 source). Fix: lock the undo manager while changing; header creation (page numbers) invalidates node positions of older undo actions → clear history first (dialog says so). A custom XUndoAction for the style **crashes Writer on Redo** (stack traced to `SfxListUndoAction::RedoWithContext`), so none is registered. Page layout is therefore *not* part of Undo; inserted content is exactly one step.
2. `setString` on a run drops bold; replacement inserts after the old run then deletes it. `XCellRangeData.setDataArray` is not undone by Calc Undo (stack shows “Insert”, data stays); per‑cell `setString` is.
3. `unopkg` has no `--bundled`; bundled extension = unpacked dir in `share/extensions` (needed by Phase 07). Root cannot `unopkg add` a user extension (harness uses `setpriv nobody`, profile under `/var/tmp`, cleaned).
4. `number-formats.json` codes are en‑US syntax; registering them directly for vi‑VN renders `1234567,000 ₫`. Use `addNewConverted(en-US → vi-VN)`. No change to the frozen file requested.
5. `description.xml` needs the `http://libreoffice.org/extensions/description/2011` namespace for `LibreOffice-minimal-version`. LO's Python loader does not add the component directory to `sys.path` (component adds it itself).
6. Headless svp does not run modal dialogs meaningfully; dialog checks need `--display` (recorded BLOCKED otherwise).

## Not done / concerns
- **26.8.1 runtime**: UNVERIFIED (no build yet). Re-run both commands against `upstream/libreoffice/instdir/program/soffice` when ready; undo/crash behaviours in item 1–2 must be re‑confirmed there.
- Encoding tables: sourced from vietunicode (runtime) cross‑checked with Wikipedia (VNI, not fully independent of vietunicode) and glibc (TCVN3). No real TCVN3/VNI user documents tested (UNVERIFIED on real files). Uppercase accented TCVN3 only through `.Vn…H` fonts; ASCII letters in H runs are not upper‑cased. Latin‑1‑only Unicode words are ambiguous (user chooses; text with Vietnamese letters above U+00FF is skipped whole).
- Vietnamese spell dictionary and autotext: not done by instruction. “HST help” page not written (no help infrastructure yet); toolbar buttons are text‑only (no icons). Accessibility: HelpText + tab order + OK/Cancel push‑button types only; no screen‑reader test.
- CSV import is per‑cell (≈0.25 ms/cell) so a 50 000 × many‑column file will take a long time on the UI thread; no progress bar/cancel mid‑write (cancel is only possible before write).
- Dialogs have no persisted size/state; modal dialog automation uses a helper thread to “press” OK (not real clicks).
- Page numbers placed in a 10 mm header (centered text at 10–15 mm from top; ND30 says centered in the top margin).
- Phase file (`phase-05-…md`) not edited (not in ownership).

## Unresolved questions
1. Accept that page layout (margins/A4/page numbers) is outside the single Undo step, and that page numbers clear the Undo history? Alternative is a template‑only approach (Phase 06) instead of editing the live page style.
2. Should `number-formats.json` be corrected to state the code syntax (en‑US) – owner is the coordinator.
3. Is per‑cell CSV writing acceptable, or should a bounded row limit lower than 50 000 be set for UI responsiveness?
4. Who adds the unpacked‑directory step (`share/extensions/hst-vietnamese-tools/`) to the staging/installer in Phase 07?

Status: DONE_WITH_CONCERNS
Summary: Bundled Python‑UNO extension (ND30 wizard, TCVN3/VNI converter, Calc formats + safe CSV import, HST menu) implemented with 35 unit tests and 94 real LibreOffice 24.2 runtime checks passing (0 failed); 26.8.1 verification pending, page‑style changes cannot be part of Undo.
