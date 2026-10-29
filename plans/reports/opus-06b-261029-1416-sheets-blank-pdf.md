# Sheets templates: blank PDF after ods round trip (opus-06b)

## Root cause
Generated page layout had fit-to-width (`style:scale-to-X=1`) but no `style:header-style`/`style:footer-style` geometry.
LibreOffice (24.2 full copy) saves such a layout with EMPTY `<style:header-style/><style:footer-style/>` plus empty `<style:header/><style:footer/>` in the master page.
Reloading that saved .ods with scale-to-X active prints a blank page (PDF has fonts, pdftotext empty, PNG all 255).

## Evidence (A/B on identical content.xml + settings.xml)
- Saved .ods from original: blank. Same file with only `scale-to-X` removed from styles.xml: text printed (81 chars vs 1).
- Scale variants Y=0/1/99, scale-to-pages=1 all blank; `scale-to="100%"` works. Not cause: header-rows, print-ranges, merged cells, wrap, margins, centering, cell-protect, formulas, settings.xml (all removed individually, still blank).
- Saved .ods styles.xml minus the empty `<style:header/>..<style:footer-first/>` block of master "Default": text printed (31 chars) -> empty header/footer + fit-to-width is the trigger.
- Generator variants, template -> ods -> pdf: no change = 1 char; empty header/footer elements only = blank; footer text only (no header-footer-properties) = blank; `header-footer-properties` min-height in page layout (with or without header/footer elements, even 0cm) = 516 chars OK.
=> a non-empty `header-footer-properties` in header-style/footer-style prevents the broken state.

## Fix (generator)
- scripts/templates/sheet_styles.py: page layout now carries `style:header-style`/`style:footer-style` with `style:header-footer-properties` (min-height 5mm, margin 2mm). Fit-to-width kept.

## Two further latent defects the runtime check exposed once PDF stage passed
(sheets never got past the PDF step before; codex run was BLOCKED)
1. XLSX stage: "frozen heading lost". Not a generator bug: headless `--convert-to` has no view shell; per-sheet view settings (even ShowGrid=false) are ignored on load and `xestream.cxx` writes `<pane>` only from live ScViewData. Same on system 24.2. scripts/templates/runtime_checks.py: pane is optional, but if written must be frozen with ySplit=4. The ODF freeze itself (VerticalSplitMode=2, position=4) is now asserted on settings.xml in unit test. GUI verification of the pane is UNVERIFIED (UNO load returned None in this sandbox).
2. "Recalculated G5: expected 3.5, got 0": generator stored `office:value="0"` on formula cells; LO does not recalc ODF cells holding a stored value, so inputs never propagated. Fix in scripts/templates/sheets.py: formula cells have no cached value/paragraph (LO computes on load; blank files still compute 0).

## Tests
- tests/unit/test_templates.py: new `test_sheet_fit_width_layout_keeps_header_footer_geometry` (scale-to-X=1 present, header/footer geometry present, freeze settings, no stored formula result).

## Results
- Regenerated twice into separate dirs + dist/templates: sha256 listing IDENTICAL.
- `python3 scripts/check-templates.py dist/templates`: PASS 18.
- `python3 -m unittest tests/unit/test_templates.py`: 8 tests OK.
- `python3 tests/runtime/check-templates.py --soffice <lo-full>`: PASS 18/18 (run dir tests/output/opus-06b/rt3/run-219usxud/runtime.json). Covers template->pdf, template->ods->pdf, template->xlsx->pdf.
- No soffice left running (only a defunct zombie entry).

## Unresolved
- Frozen pane in xlsx output cannot be verified headless; needs GUI/Xvfb run.
- Did not file the LO upstream bug (empty header/footer + fit-to-width blank on reload); worth reporting/checking on 26.8.1.1 build.
- Formula cells now lack cached values: non-recalculating viewers show them empty until opened in LO.
