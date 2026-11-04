# Heavy Math/Physics/Chemistry Word documents: corpus, measurements, fixes

Backlog item (beta.5): "Tệp nặng nhiều công thức/hình (Toán, Lý, Hóa): mở chậm, công thức/hình không hiện hoặc hiện sai".
Build: Linux instdir, LibreOffice 26.8.1.1 + HST patches, 2026-11-04.

## Corpus (27 public documents)

Manifest with URL, sha256, features: [tests/corpus/stem/manifest.json](../../tests/corpus/stem/manifest.json).
No document has a licence that allows redistribution (exam papers and teaching material from schools, Sở GD&ĐT, teachers), so the files are not in the repository. Sources: hoclieuxanh.com (Sở/school exam files), Google Drive files linked from mathvn.com and thuvienhoclieu, news.vsis.net, cdn.thuvienphapluat.vn, storage-edu.vnpt.vn. Each file was downloaded into its own directory and opened read-only with macros disabled, as hstbuild only.

Coverage:

| Feature | Documents |
|---|---|
| MathType OLE `Equation.DSMT4` with WMF previews | 23 docs, 3 379 objects (s037: 1 032 in 50 pages; s039: 420; s040: 390; s038: 321) |
| Legacy Equation 3.0 (`Equation.3`, converted to LibreOffice Math on import) | 8 docs, 364 objects (s031: 193) |
| Word OMML equations | s008 (63), s015 (143), s023 (65), s013 (7) |
| Chemistry OLE: ChemDraw 6, ChemWindow, ACD/ChemSketch (EMF previews) | s015, s012, s016 |
| Shapes / groups / text boxes (physics drawings, geometry) | s033 (667 shapes, 77 groups, 390 text boxes), s008, s013, s015 |
| `.doc` vs `.docx` | 13 `.doc`, 14 `.docx` |
| Text in legacy Vietnamese fonts inside the equation previews | `.VnTime` (TCVN3): s012, s033; `VNI-Times`: s008, s011, s012, s037 |
| Controls without formulas | s001, s004, s005, s009 |

Not found in the public corpus: Word drawing canvas (`wpc`), physics circuit drawn as EMF. No Word-made reference PDF was published next to any `.docx`, so the visual check is a sanity check (missing/blank objects, wrong glyphs, misplaced shapes), not a pixel diff against Word.

## Measurements (before the fixes)

Headless (svp): load = `loadComponentFromURL`, then layout to the last page, then PDF export; best of 2 runs.
GUI: gtk3 under Xvfb, window visible; load, then every page shown in turn with `processEventsToIdle` ("scroll").
Totals: PDF export of the 27 documents took **216.8 s before, 31.2 s after**. Load and screen painting were not the bottleneck: headless load 0.1–3.9 s, GUI load 1.8–5.7 s (1.8 s for a document without formulas), showing every page 0.25–3.3 s.

| ID | Format | Pages | OLE (MathType/Eq3/other) | OMML | Fonts in previews | Load headless (s) | GUI load / all pages (s) | PDF export before → after (s) |
|---|---|---|---|---|---|---|---|---|
| s001 | docx | 5 | 0/0/0 | 0 | – | 0.839 | 1.813 / 0.545 | 0.098 → 0.121 |
| s002 | docx | 12 | 146/0/0 | 1 | Euclid Extra, MT Extra, Symbol, Times New Roman | 0.88 | 2.416 / 1.216 | 3.201 → 0.658 |
| s004 | docx | 21 | 0/0/0 | 0 | – | 0.137 | – | 1.533 → 1.538 |
| s005 | docx | 7 | 0/0/0 | 0 | – | 0.148 | – | 0.857 → 1.41 |
| s008 | docx | 21 | 1/0/0 | 63 | VNI-Times | 1.493 | 3.418 / 1.378 | 0.417 → 0.371 |
| s009 | doc | 16 | 0/0/0 | 0 | – | 0.443 | – | 0.662 → 0.7 |
| s011 | docx | 34 | 107/0/1 | 0 | MT Extra, Symbol, Times New Roman, VNI-Times | 1.956 | 3.461 / 2.299 | 13.748 → 1.918 |
| s012 | docx | 8 | 69/0/3 | 0 | .VnTime, MT Extra, Symbol, Times New Roman, VNI-Times | 0.853 | 2.211 / 0.254 | 11.468 → 0.429 |
| s013 | docx | 9 | 10/0/0 | 7 | MT Extra, Symbol, Times New Roman | 0.374 | – | 1.678 → 1.38 |
| s014 | doc | 9 | 45/15/0 | 0 | – | 0.906 | 2.254 / 0.478 | 5.72 → 0.372 |
| s015 | docx | 15 | 7/10/30 | 143 | Arial, Symbol, Times New Roman | 2.082 | 3.732 / 0.758 | 9.608 → 0.871 |
| s016 | docx | 9 | 48/0/7 | 0 | Arial, Symbol, Times New Roman | 0.395 | – | 3.059 → 0.306 |
| s021 | doc | 29 | 50/24/0 | 0 | – | 1.196 | – | 3.624 → 1.063 |
| s022 | doc | 3 | 7/0/0 | 0 | – | 0.08 | – | 0.31 → 0.115 |
| s023 | docx | 7 | 1/5/0 | 65 | Symbol, Times New Roman | 1.137 | 2.864 / 0.333 | 0.236 → 0.2 |
| s030 | doc | 5 | 14/12/0 | 0 | – | 0.362 | – | 0.815 → 0.295 |
| s031 | doc | 14 | 10/193/0 | 0 | – | 2.118 | – | 2.386 → 0.793 |
| s032 | docx | 10 | 14/0/0 | 0 | Symbol, Times New Roman | 0.369 | – | 0.539 → 0.344 |
| s033 | docx | 38 | 131/68/0 | 0 | .VnTime, MT Extra, Symbol, Times New Roman | 3.275 | 5.44 / 3.253 | 7.469 → 2.757 |
| s034 | doc | 12 | 49/0/0 | 0 | – | 1.041 | – | 4.196 → 1.16 |
| s035 | doc | 19 | 73/37/1 | 0 | – | 1.002 | – | 5.139 → 0.859 |
| s036 | doc | 24 | 126/0/0 | 0 | – | 0.754 | 2.753 / 1.258 | 8.004 → 1.707 |
| s037 | docx | 50 | 1032/0/0 | 0 | MT Extra, Symbol, Times New Roman, VNI-Times | 3.882 | 5.662 / 2.68 | 38.207 → 3.78 |
| s038 | doc | 30 | 321/0/0 | 0 | – | 1.643 | – | 17.414 → 2.247 |
| s039 | doc | 32 | 420/0/0 | 0 | – | 1.876 | 3.163 / 2.485 | 23.67 → 2.526 |
| s040 | doc | 33 | 390/0/10 | 0 | – | 1.709 | – | 27.894 → 1.767 |
| s041 | doc | 33 | 308/0/15 | 0 | – | 1.599 | – | 24.826 → 1.487 |

Preview fonts were read from the WMF/EMF text records of the `.docx` media. The `.doc` previews sit compressed in the Data stream and were not scanned. s004/s005/s009 have no formulas (the formulas are pictures). The s005 change is noise: it has no OLE objects.

Test-environment note: GUI loads took 18–40 s until the session D-Bus was disabled. With no session bus, GTK waits on `atspi_get_a11y_bus` and on `g_bus_get_sync` (dbus-launch) for each new frame. That is an artefact of Xvfb without a session bus, not of the documents. The measurements above set `NO_AT_BRIDGE=1` and a dead `DBUS_SESSION_BUS_ADDRESS`.

## Root causes found

1. **OLE previews are rasterised when printing or exporting PDF.** This is the main cause of slowness, and it also hurts PDF quality.
   - Where: `SwNoTextFrame::ImplPaintPictureBitmap` calls `Graphic::Draw`. For a vector graphic (the WMF preview as `VectorGraphicData`), that path goes through `ImpGraphic::updateBitmapFromVectorGraphic`, which renders a bitmap at the device resolution. The PDF writer then convolution-scales and deflates one bitmap per equation.
   - Evidence: gdb stack samples of the s012 export (`VectorGraphicData::getBitmap`, `CairoPixelProcessor2D::extractBitmap`, `BitmapScaleConvolutionFilter`, `PDFWriterImpl::implWriteBitmapEx`), and about 50 ms per object.
   - Effect: s037 had 2 182 images in a 6.5 MB PDF. Formulas were not searchable and looked blurry when zoomed.
   - Upstream: tdf#129244 / tdf#135999 / tdf#142970 fixed blurry previews on screen (Mike Kaganski, c2eb8d81e01f, in 24.8.0.2, already in 26.8). Nothing upstream changes the print/PDF path.
2. **Text in legacy Vietnamese fonts inside equation previews.** MathType text styles set to `.VnTime` (TCVN3) or `VNI-Times` keep 8-bit bytes in the WMF. emfio decodes them with the system/default code page (cp1252, or cp1258 under a vi locale) and draws them with a substitute font.
   - Effect: "(rắn)" shows as "(r¾n)", "(đặc)" as "(®Æc)", "(vôi sữa)" as "(v«i s÷a)" (s012 page 1, before/after renders below). The PDF text is garbage too.
   - Scope: 5 of the 14 `.docx` files. It happens on Linux always, and on Windows/macOS whenever the legacy fonts are not installed. Under a Vietnamese locale (cp1258), positions such as 0xEC/0xD2/0xDE/0xF2 decode to combining marks, so it is wrong even with the font present.
3. **Long reaction arrows built from Symbol glyphs show gaps on Linux** ("– –→" instead of "⎯⎯→"). MathType builds them from Symbol 0xBE (arrowhorizex) plus 0xAE. Without the Symbol font, VCL substitutes OpenSymbol and recodes 0xBE to U+2500 (`unotools/source/misc/fontcvt.cxx`). That OpenSymbol glyph has 221/223 of 1628 units of side bearing and sits lower than OpenSymbol's arrow shaft, so the parts placed with the WMF dx array do not join. Windows and macOS have the Symbol font, so this is Linux only. **Not fixed** (see Remaining).
4. **OMML → LibreOffice Math.** s023, s008, s015: formulas are complete but are set with wider operator spacing and a smaller size than Word ("x - 5 / x - 1"). This is cosmetic: nothing missing or wrong was found in the sampled pages.
5. **Equation 3.0 → LibreOffice Math conversion.** Most objects become Math objects (s031: 193/193). In s033 only 56 of 68 did; the rest stay as OLE with a WMF preview, which still displays. Not investigated, and not compared against Word glyph by glyph.
6. **Fonts substituted by OpenSymbol through the existing recode tables.** MT Extra and Symbol (both cs1 and cs2) are recoded correctly apart from item 3. "Euclid Extra" (1 character in s002) has no recode table. Rare.
7. **Shapes, groups and text boxes** (s033: 667 shapes, 390 text boxes): no misplaced or missing shapes were seen in the sampled pages. Layout of s033 took 1.5 s headless.

## Fixes (patches appended to `patches/libreoffice/series`)

1. `hst-sw-ole-vector-preview-pdf.patch` (sw/source/core/doc/notxtfrm.cxx)
   - What: when printing, exporting PDF or recording a metafile, an OLE replacement graphic that is a vector graphic is painted through `paintGraphicUsingPrimitivesHelper`, the same path pictures use. Screen painting is unchanged.
   - Result: PDF export total for the corpus went from 216.8 s to 31.2 s. s037 went from 38.2 s to 3.8 s, from 2 182 to 118 images, and from 6.5 MB to 1.7 MB. Formulas are vector text in the PDF.
2. `hst-emfio-legacy-vn-fonts.patch` (emfio/source/reader/wmfreader.cxx plus a new `hstlegacyvn.hxx`)
   - What: WMF `TEXTOUT`/`EXTTEXTOUT` in a `.Vn*` font (TCVN3; `…H` means uppercase) or a `VNI-*` font is decoded to Unicode and drawn with Times New Roman (Arial for `.VnArial`). A VNI letter plus tone-mark pair keeps the dx of both bytes.
   - Tables: from `data/vietnamese/encoding-maps.json`, the same verified data the HST TCVN3/VNI converter uses, generated by `scripts/patches/generate-legacy-vn-font-table.py`. `--check` and the unit test keep the patch in sync with the data.
   - Result: s012 now shows "NaCl (rắn) + H2SO4 (đặc)", "(vôi sữa)", and pdftotext finds those words.

Regression tests:
- cppunit `WmfTest::testLegacyVietnameseFontsWmf` (emfio/qa/cppunit/wmf). It builds the WMF in memory (TCVN3, VNI, .VnTimeH, Times New Roman control) and checks the decoded texts, that no legacy font is left, and the dx merge. emfio_wmf: OK (21); emfio_emf: OK.
- Runtime `tests/runtime/check-stem-equation-previews.py`. It builds a .docx itself: 60 `Equation.DSMT4` objects whose WMF previews have Times, `.VnTime` and `VNI-Times` text. It exports PDF and checks the text layer and that there are no raster previews.
  - Before (fixes reverted, same tree): FAIL ×4, 120 images, export 11.57 s.
  - After: PASS ×5, 0 images, export 0.07 s.
- `tests/unit/test_legacy_vn_font_table.py`: the generated table matches the data and the patch, and known letters map correctly.

Evidence (scratch, not committed): `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/stem-corpus/run/`
- `base-headless/`, `after-headless/`: results.json and PDFs for every document.
- `base-gui/`: GUI results.
- `p012-1.png` / `a012-1.png`: s012 page 1 before/after.
- `prof012b/bt*.txt`: stack samples.
- `rt-before/`, `rt-after/`: runtime test evidence.json.

Tools are in `…/stem-corpus/tools/` (`measure.py`, `inventory.py`, `wmfscan.py`, `profile.py`).

## Remaining

- **Symbol arrow gaps on Linux** (cause 3). Options:
  - (a) Change the Symbol→OpenSymbol recode of 0xBE and add a full-width extender glyph at the arrow-shaft height to OpenSymbol (upstream-worthy, needs font work).
  - (b) Prefer the metric-compatible URW "Standard Symbols PS" (fonts-urw-base35, usually present on Ubuntu) for Symbol in WMF on Linux.
  - Needs a decision and Linux GUI check.
- `.doc` preview fonts were not scanned. The emfio fix covers `.doc` too, because the same WMF reader is used, but the corpus has no measured `.doc` with `.VnTime` text.
- EMF previews with legacy VN fonts (`EXTTEXTOUTA/W`) are not handled; none were seen in the corpus. "Euclid" fonts (old MathType) have no recode table.
- OMML spacing differs from Word (cosmetic). Equation 3.0 conversion was not compared with Word glyph by glyph.
- **Needs Windows/macOS testing:**
  - PDF export/print speed and vector output with the native GDI/Quartz backends.
  - `.VnTime`/`VNI-Times` previews on a Windows machine that has the legacy fonts installed: now drawn with Times New Roman, so check that the look is acceptable.
  - Symbol/MT Extra rendering with the system Symbol font.
  - GUI open/scroll timing on typical teacher laptops (these Linux numbers come from a 32-core server).
- No Word-made reference PDFs: a pixel comparison needs Word on Windows to print the corpus to PDF.
