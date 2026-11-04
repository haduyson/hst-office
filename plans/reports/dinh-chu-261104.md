# Dính chữ (words glued) on old Word files: investigation, 2026-11-04

## Result
- HST (Linux instdir, 26.8.1.1) does NOT glue words for any file-level candidate tried, except where the file itself carries the glue (condensed spacing, U+200B spaces, hidden spaces): there HST draws what Word draws.
- No patch written: nothing reproduced that is not already faithful to Word. Regression test added: tests/runtime/check-word-spacing.py (61 measurements, passes).
- Real owner sample needed to confirm which of the faithful cases the owner sees.

## Known causes (sources, Vietnamese/English)
Vietnamese how-to sites (phucanh.vn, mytour.vn, mso.vn, thuthuatoffice.net, hoanghamobile.com, vnreview.vn): version conflict old .doc vs new Word, "Condensed" character spacing, Proofing options, Smart cut and paste "Adjust sentence and word spacing", copy from PDF/web, missing font substituted. Fix they give: Font > Advanced > Spacing Normal; save as .doc. English: itwriting.com / CBS (Word 2010 -> 2007 lost spaces, printer-driver line breaking, fixed by 2008 patch); LibreOffice bug 70032 (U+200B invisible). None names a compat flag. Proofing / smart-paste are Word UI behaviours, not file rendering.

## Method
Corpus: 27 public STEM docs (tests/corpus/stem/manifest.json; 14 .docx, 13 .doc; .VnTime/VNI-Times only inside equation WMF previews, body Unicode) rendered to PDF; per file PDF word count vs soffice text export, long-token scan, pdftotext -bbox. Public old .doc downloads: vbpl.vn link returned HTML, vbpl.moj.gov.vn unresolvable; no extra files obtained.
Synthetic: 61 docx + 8 rtf authored by us (generator in tests/runtime/check-word-spacing.py); each also saved as .doc and reloaded. Metric: gap between adjacent word boxes / box height (control 0.226), word count vs source.

## Per candidate (HST)
| candidate | HST glues? | evidence |
|---|---|---|
| legacy font .VnTime/VNI-Times/.VnArial/UVN missing, Unicode text | no | gap 0.19, 24/24 words |
| legacy fonts with TCVN3/VNI BYTES in body | no glue, text garbled ("Häc ®i") | pdftotext: "Cã c«ng mµi"; separate "lỗi font", not gluing; same in Word w/o fonts. Not fixed (body decode would be a new feature) |
| NBSP, U+2002, U+3000 | no | gaps 0.226/0.45/0.90 |
| U+200B as the only space | yes, faithful | text itself has no space; glued in Word too |
| condensed w:spacing -1pt / -2pt | -1pt tight (0.087), -2pt glued (-0.05) | faithful; looks exactly like "Cócôngmàisắt" (sheet-faithful-glued.png). Word shows same; Word fix = Spacing Normal |
| w:w 80%, fitText, kern | no | 0.18 / 0.226 / 0.209 |
| compat flags: all of doNotExpandShiftReturn, ulTrailSpace, balanceSingleByteDoubleByteWidth, spaceForUL, useFELayout, usePrinterMetrics, wpJustification, wpSpaceWidth, ... ; compatibilityMode 11/12/14/15 | no | justified gaps 0.209-0.325; mode 15 shrinks spaces to 0.167 (Word 2013+ behaviour) |
| characterSpacingControl compress, autoSpace off | no | 0.209 |
| jc distribute / thaiDistribute / both | no | 0.33 / 0.226 / 0.325 |
| eastAsia font (MS Mincho, SimSun, Batang, missing) with/without hint=eastAsia | no | space drawn in the EA font (script scanner applies hint to weak chars incl. space) gap 0.201-0.230; a real EA font with 0-width space would be needed to glue |
| docGrid lines/linesAndChars/snapToChars charSpace -2000 | no | 0.209 |
| space run in Symbol / Wingdings / MS Gothic | no | 0.452 / 0.233 / ok |
| space run w:sz=1pt, w:w=1%, w:spacing -20pt, w:vanish | yes, faithful | the file hides the spaces |
| .doc (sprmCDxaSpace etc.) | same as docx | 60/61 identical; only compat-15 (not a .doc concept) differs |
| RTF cp1258 fcharset163 / cp1252 / \u / \expnd | no | decoded correctly, gaps 0.19-0.226 |
| corpus 27 docs | no | no token longer than source; no ratio <1 |

## Side finding (open defect, not gluing)
Decomposed (NFD "Unicode tổ hợp") Vietnamese with w:hint="eastAsia": combining marks are drawn in the East Asian/Unifont fallback and drift off their letters (words 43/24 in bbox). Cause: i18nutil/source/utility/scriptchangescanner.cxx applies ScriptHintType::Asian to every WEAK char, including NON_SPACING_MARK. Fix idea: keep marks on the previous script. Not patched (not the reported symptom; touches shared i18nutil/merged lib). Recorded as KNOWN_OPEN in the test. Image: sheet-open-defect-nfd-hint.png.

## Decision needed (not done)
Only reproduction of the owner's picture is condensed spacing in the file. Word shows it glued as well. HST could be better than Word by never condensing a SPACE below ~50% of its natural width (letters stay condensed). Writer applies kerning in ~10 places (sw/source/core/txtnode/fntcache.cxx DrawText/GetTextSize/GetTextBreak/GetCursorOfst, fntcap.cxx, swfont.cxx, txtfly.cxx), so it needs a layout change + sw rebuild, and breaks line-break parity with Word for such files. Not started without the owner's sample and OK.

## Images
/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/approve/dinh-chu/: sheet-hst-renders.png (HST correct renders), sheet-compat-space-runs.png, sheet-faithful-glued.png (cases glued in file, same in Word), sheet-open-defect-nfd-hint.png, corpus-s035-doc-page1.png. No before/after: no code changed.

## Limits
Linux only (Liberation/Noto substitutes); Windows/macOS real fonts (MS Mincho space width, legacy fonts installed) untested. Word itself not available, so "Word shows the same" rests on the file semantics (w:spacing applies to spaces), not a Word render.

## Unresolved
- Owner sample file (a .doc/.docx that glues in Word, ideally with the Word version): then check w:spacing / w:w / fonts in its XML.
- OK to diverge from Word (clamp space condensing)?
- Fix the NFD+hint mark drift?
