# Phase 06 — Vietnamese templates and offline catalog

**Status:** pending. **Depends on:** 05 shared data; runtime 01/03. **Parallelizable:** separate template sources after shared schema is frozen.

## Context and requirements

Use native `.ott/.ots/.otp` templates, generated through the built suite's UNO APIs; export OOXML in QA. Deliver all 18, with a local catalog available from Start Center/Template Manager. Blank fields/placeholders are intentional; no real personal data, invented official identities or unauthorized national emblems.

## Exact files

- Create `templates/catalog.json`, `templates/schema.json`, `scripts/generate-templates.py`, `scripts/check-templates.py`, `tests/runtime/check-templates.py`, `tests/fixtures/templates/expected.json`.
- Writer sources `templates/writer/{cong-van,thong-bao,quyet-dinh,to-trinh,bao-cao,giay-moi,bien-ban}.json`.
- Sheets sources `templates/sheets/{cham-cong,bang-luong,du-toan,thu-chi,thong-ke,danh-sach}.json`.
- Slides sources `templates/slides/{hop-co-quan,bao-cao-don-vi,giang-day,hoi-nghi,bao-cao-doanh-nghiep}.json`.
- Create `config/hst-template-paths.xcu`, `docs/TEMPLATES.md`. Generated outputs: matching basenames under `dist/templates/writer/*.ott`, `sheets/*.ots`, `slides/*.otp`; previews and manifest under `dist/templates/`. Coordinator integrates catalog/help access without competing edits to 02/05 files.

## Steps

1. Define one schema linking catalog IDs, module, title/description vi/en, source/license, output and preview hashes. Reuse ND30 layout and number-format data; no second hand-maintained ruleset.
2. Writer: seven types with correct A4/margins/styles, header and signature structure, page-number rules, editable placeholders and no fabricated official seal. Preserve original specification's distinct công văn layout.
3. Sheets: six useful blank forms with typed columns, totals/formulas where appropriate, VND/date/percent formats, protected formula guidance, print area/repeated headings and Unicode sheet names. Payroll/attendance rules are editable examples, not claims of current tax/labor compliance.
4. Slides: five distinct reusable themes with master/layouts, title/content/section/table/chart examples, notes, readable Vietnamese fonts, suitable 16:9 defaults and 4:3 compatibility check. Use HST assets modestly; no unauthorized state insignia.
5. Generate through a pinned UNO runtime, normalize ZIP order/timestamps and volatile metadata, and verify two clean outputs under the same toolchain. Separate deterministic package hashes from rendering/font comparisons. Register local template paths/categories and open as **new untitled documents**, never edit the installed master. Personal templates remain separate.

## Validation commands

After implementation; the generator owns isolated profiles/processes and bounded output directories:

```bash
python3 scripts/generate-templates.py --soffice upstream/libreoffice/instdir/program/soffice --catalog templates/catalog.json --output dist/templates
python3 scripts/check-templates.py --catalog templates/catalog.json --directory dist/templates --rebuild-check
python3 tests/runtime/check-templates.py --soffice upstream/libreoffice/instdir/program/soffice --catalog dist/templates/manifest.json --expected tests/fixtures/templates/expected.json --output tests/output/templates
```

Pass: exactly **7/6/5**, valid ODF archives, no broken embedded references, same-toolchain normalized hashes, all catalog actions open real templates offline. For every template: create new instance, edit, save/reopen native and DOCX/XLSX/PPTX, export PDF and compare text/formulas/page or slide count plus reviewed renders. Missing TNR is recorded, not called exact ND30 rendering.

## Risks and rollback

Font substitution, overflow and UNO serialization metadata can defeat naive byte/render comparisons. Resolve through normalized build output and explicit rendered expectations. Keep previous package-owned templates available for rollback; never overwrite user-created instances or personal template directories.
