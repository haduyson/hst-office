# codex-06 — Vietnamese templates

**Status: DONE_WITH_CONCERNS.** All 18 template sources, deterministic ODF
generation, structural checks, runtime harness and integration instructions are
implemented. **Runtime acceptance is BLOCKED**, so Phase 06 is not certified
for release. No Git commit, push, branch change, upstream edit or shared-data
edit was made.

## Files delivered

- `templates/catalog.json`, `templates/schema.json`, seven `templates/writer/*.json`,
  six `templates/sheets/*.json`, five `templates/slides/*.json`.
- `scripts/generate-templates.py`, `scripts/check-templates.py` and eleven
  `scripts/templates/*.py` helpers for XML/ZIP, source validation, Writer,
  Sheets, Slides, package checks and runtime checks.
- `tests/unit/test_templates.py`, `tests/runtime/check-templates.py`,
  `tests/fixtures/templates/expected.json`.
- `config/hst-template-paths.xcu` and [docs/TEMPLATES.md](../../docs/TEMPLATES.md).
- Generated `dist/templates/`: 18 ODF templates, 18 SVG catalog cards and
  `manifest.json`. Cards are explicitly labeled as source-based catalog cards,
  not rendered document previews.

Writer uses the frozen ND30 dimensions, typography, header proportions and
rule widths, first-page suppression of page numbering, subsequent page fields,
distinct công văn layout, bracketed fields and signature/recipient blocks.
Sheets has typed numeric/text input, empty date-formatted cells, real SUM/IF
and arithmetic formulas, vi-VN formats, print ranges, repeated/frozen headings
and formula-protection guidance without assumed tax or payroll rules. Slides
has five distinct palettes, two masters per theme, five layouts/pages, notes,
editable tables and embedded charts with zero/placeholder starting data.

The generator follows the task's direct Python stdlib ODF requirement, which
overrides the original plan's UNO generation step. ZIP members are stored in
deterministic order with fixed timestamps; metadata uses SOURCE_DATE_EPOCH
and generator `HST Office template generator`. Sources/content carry CC BY 4.0;
new code/config carries AGPL-3.0-only. No fonts or national emblems are embedded.

## Commands and results

| Command/check | Result |
|---|---|
| `SOURCE_DATE_EPOCH=1767225600 python3 scripts/generate-templates.py --out dist/templates` | PASS: all 18 templates generated. |
| `python3 scripts/check-templates.py dist/templates` | PASS: 7/6/5 counts, ZIP/XML/MIME/manifest, hashes, NFC, placeholders, formulas, layout, safe links and no macros/fonts. |
| `python3 scripts/check-templates.py dist/templates --rebuild-check` | PASS at the reviewed intermediate revision; final revision was independently rebuilt twice below. |
| Two `generate-templates.py --out <tempdir>` runs with the fixed epoch, then SHA-256 maps compared | PASS: all 37 files byte-identical, including all 18 templates. |
| `python3 -m unittest discover -s tests/unit -p test_templates.py -v` | PASS: seven tests, including unsafe formulas/links/macros, NFC, deterministic output, date fixtures, formula preservation and shared formats. |
| Independent `jsonschema.validate` on catalog and all sources | PASS: 19 JSON documents. Runtime generation itself has no third-party dependency. |
| AST parse, SPDX/NFC check and authored Python line-count gate | PASS: 15 Python files, each at most 199 lines. |
| Local links in TEMPLATES.md and XCU XML parsing | PASS. |
| `python3 tests/runtime/check-templates.py --soffice /usr/bin/soffice --catalog dist/templates/manifest.json --expected tests/fixtures/templates/expected.json --output tests/output/templates` | **BLOCKED**, exit 2: sandbox rejects AF_UNIX bind/listen with `Operation not permitted`. |

Reproducibility evidence is `tests/output/templates-reproducibility.json`.
Final generated manifest SHA-256:
`95b46cc9b50ee09516abe9fba9e5a3bdac3e7d74afb09cc1757e5265b2569aa3`.
Runtime evidence is `tests/output/templates/run-lbqngk5d/runtime.json`, with
all 18 entries explicitly BLOCKED, exact system version, repository/source
commit information and generated template hashes.

An actual isolated `soffice --headless --convert-to pdf` probe on the generated
công văn exited 1 and produced no PDF. It also failed with a writable cache,
`GSETTINGS_BACKEND=memory` and `SAL_USE_VCLPLUGIN=svp`. A direct AF_UNIX
bind/listen probe reproduced the permission denial. `strace` was also denied
by the sandbox (`PTRACE_TRACEME: Operation not permitted`). The system reports
LibreOffice **24.2.7.2**, and `fc-match 'Times New Roman'` resolves to Liberation
Serif. No HST 26.8.1.1 execution or Microsoft Office execution is claimed.

The first structural-check run falsely matched `dc:description` as a script;
the check was corrected to compare element local names, and the final suite
passes. Review also added công văn summary spacing, explicit worksheet row
heights, Calc ViewId and rejection of external workbook formula references.
An attempt to fetch the official ODF Relax NG schema failed due DNS/network
restrictions; full Relax NG validation remains UNVERIFIED.

All office subprocesses were awaited and exited. No X display or background
server was started. Temporary profiles and reproducibility directories were
removed; test reports/artifacts remain under `tests/output/`.

## Integration and unresolved validation

1. Run the runtime command on a host that permits LibreOffice local IPC, then
   repeat with the built HST 26.8.1.1 binary. PDF/OOXML conversion, Writer OOXML
   A4/margins, Calc recalculation, edited native/OOXML reopen, notes/chart
   preservation and 4:3 export are implemented checks but **UNVERIFIED** here.
2. Install the output under `$(insturl)/share/template/hst` and merge the XCU
   through the coordinator's packaging flow. Template Manager/Start Center
   discovery and creation of untitled instances remain **UNVERIFIED**.
3. Review actual PDF/slide renders for clipping and pagination with the intended
   font environment. Times New Roman availability and exact ND30 rendering
   remain unresolved; no raster/render quality approval is claimed.
4. The shared ND30 legal-status caveat remains unchanged. Template content does
   not certify legal compliance.
