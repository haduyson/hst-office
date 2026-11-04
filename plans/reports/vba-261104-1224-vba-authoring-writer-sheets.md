# VBA authoring in HST Writer and HST Sheets: report

Date: 2026-11-04. Target: 1.0.0-beta.5. Owner request: "Bổ sung thêm VBA cho Writer và Sheets". Users must be able to write and edit VBA macros as in the Microsoft Office VBA editor.
Entry point name decided by the owner: **"Macro VBA"**.

## Summary

Two commits of core work: `hst-vba-authoring.patch` (first round) and `hst-vba-word.patch` (owner follow-up).

- **Sheets (Excel VBA): 35/37 idioms pass.** Only `Scripting.Dictionary`/COM objects and newly authored UserForms are missing.
- **Writer (Word VBA): 20/24 idioms pass** (12/24 at the start, 13/24 after round 1). Missing: `InlineShapes`, `Comments.Add`, `Fields.Add`, new UserForms. Upstream Word VBA suites: 4/8.
- **Round trip: 9/10.** New and edited macros survive .xlsm, .xls, .ods, .odt and .docm; .doc does not keep new macros. Vietnamese text in code survives also in projects made with a Western code page (switched to Windows-1258).
- **Events: 4/4.** `Workbook_Open`, `Worksheet_Change` (GUI), and Writer `Document_Open` in .docm and .odt saved by HST.
- **Entry points:** HST menu "Macro VBA", Tools-tab ribbon button "Macro VBA", Alt+F11 (Writer/Sheets), Alt+F8 macro dialog (Writer/Sheets). GUI check 12/12.
- **Defaults:** VBA load/executable/save on (upstream, verified); macro security **Medium** (owner approved): always asks, never runs silently.

Measured with `tests/runtime/check-vba.py` (headless, fresh profile, soffice as hstbuild) and `tests/runtime/check-vba-editor.py` (GTK3 under Xvfb, Vietnamese UI). Evidence: `tests/output/vba/evidence.json`, `tests/output/vba/matrix.md`.

## What changed

| Area | Change | Files |
|---|---|---|
| Command | `org.hst.office.vi:EditVba`. In a document without Basic code it switches on VBA mode, project `VBAProject` (Sheets) or `Project` (Writer), and VBA code page Windows-1258. It creates `Module1` with `Option VBASupport 1`, a Vietnamese guide and the example `Sub XinChao`, then opens the Basic IDE on that Sub. It reuses the existing VBA module of Excel/Word files. A document that already has LibreOffice Basic code keeps its mode, and only the new module gets VBA support. | `extensions/hst-vietnamese-tools/python/hst_office/vba.py`, `vba_template.py`, `actions.py` |
| HST menu | "Macro VBA" (m9, Writer and Sheets only), placed before "Tìm tính năng…". The last two items are unchanged (m10–m12 renumbered). | `Addons.xcu`, `locales/*.json`, `tests/unit/test_hst_menu_order.py` |
| Shortcuts | `Accelerators.xcu` in the extension. Alt+F11 opens EditVba in Writer and Calc. It replaces, in those two modules only, the global Alt+F11 = Basic Macros dialog. Alt+F8 opens `.uno:MacroDialog` in Calc and Writer. | `Accelerators.xcu`, `META-INF/manifest.xml` |
| Core patch | `hst-vba-authoring.patch`: (1) Tools-tab button "Macro VBA" (tooltip "Soạn và chạy macro VBA (Alt+F11)") in the sw/sc notebookbar; (2) MacroSecurityLevel 2→1; (3) Word `Range.InsertBefore/InsertAfter` (oovbaapi IDL + `sw/source/ui/vba/vbarange`); (4) .docm export writes the current VBA project with `VbaExport`, but keeps the original stream when it contains UserForm designer storages; (5) .xlsx/.xlsm export writes `sheetPr`/`workbookPr` `codeName`. | `patches/libreoffice/hst-vba-authoring.patch` |
| Help | New F1 page `macro-vba.html`: open the editor, first macro in Sheets and in Writer, run, save formats, security prompt and compatibility tables. It has 2 screenshots (gtk3/Xvfb) and is linked in every sidebar, the index, the page navigation and the shortcuts page. | `help/macro-vba.html`, `help/images/macro-vba-*.png`, sidebars, `phim-tat.html` |
| Tests | Runtime matrix and round trip (`check-vba.py` + `vba_cases.py`), GUI entry points (`check-vba-editor.py`), unit tests (`test_vba_authoring.py`, menu order). | `tests/runtime/`, `tests/unit/` |
| l10n | Access-key snapshot regenerated (new ribbon label). | `l10n/access-keys-snapshot.json` |

Builds run as hstbuild: oovbaapi, Library_vbaswobj, Library_msword, Library_scfilt, UIConfig sc/sw, officecfg + postprocess, ExtensionPackage. No desktop build.

## Shortcut decisions (Alt+F11 / Alt+F8 / macOS)

- **Alt+F11** was **not free**. Upstream binds it globally to `.uno:MacroDialog` (Basic Macros organizer). It is now remapped in the Writer and Calc modules only, to open the VBA editor directly, as Excel and Word do. The organizer stays reachable: Calc via Alt+F8, both via the Tools tab or menu. Impress and Draw keep the global binding.
- **Alt+F8**: `.uno:MacroDialog` (Run/Edit/Assign, like Office's "Macros" dialog) in Calc and, by owner decision, in Writer, replacing extended selection on that key (still on the status-bar selection-mode control).
- **macOS**: MOD2 = Option, so the keys are Option+F11 and Option+F8. With media keys on, F11 is volume-down and Option+volume opens Sound settings, so users need **fn+Option+F11**. This is the same as Excel for Mac and is documented on the help page. It was not run on a Mac.

## Compatibility table (final run, after hst-vba-word.patch)

| Group | Case | Result |
|---|---|---|
| config | org.openoffice.Office.Calc/Filter/Import/VBA/Load = True | PASS |
| config | org.openoffice.Office.Calc/Filter/Import/VBA/Executable = True | PASS |
| config | org.openoffice.Office.Calc/Filter/Import/VBA/Save = True | PASS |
| config | org.openoffice.Office.Calc/Filter/Import/VBA/UseExport = True | PASS |
| config | org.openoffice.Office.Writer/Filter/Import/VBA/Load = True | PASS |
| config | org.openoffice.Office.Writer/Filter/Import/VBA/Executable = True | PASS |
| config | org.openoffice.Office.Writer/Filter/Import/VBA/Save = True | PASS |
| config | org.openoffice.Office.Common/Security/Scripting/MacroSecurityLevel = 1 | PASS |
| config | org.openoffice.Office.Common/Security/Scripting/DisableMacrosExecution = False | PASS |
| config | SpreadsheetDocument Alt+F11 -> org.hst.office.vi:EditVba | PASS |
| config | TextDocument Alt+F11 -> org.hst.office.vi:EditVba | PASS |
| config | SpreadsheetDocument Alt+F8 -> .uno:MacroDialog | PASS |
| config | TextDocument Alt+F8 -> .uno:MacroDialog | PASS |
| calc | calc-range-value: Range("A1").Value | PASS |
| calc | calc-cells: Cells(hàng, cột) | PASS |
| calc | calc-worksheets: Worksheets(1), Worksheets("tên"), .Count | PASS |
| calc | calc-activesheet: ActiveSheet | PASS |
| calc | calc-selection: Range.Select, Selection | PASS |
| calc | calc-loops: For…Next, For Each cell In Range | PASS |
| calc | calc-formula: Range.Formula, FormulaLocal | PASS |
| calc | calc-worksheetfunction: WorksheetFunction.Sum/Max/CountIf/VLookup | PASS |
| calc | calc-msgbox: MsgBox (hộp thông báo) | PASS |
| calc | calc-inputbox: InputBox, Application.InputBox | PASS |
| calc | calc-font-interior: Font.Bold, Interior.Color, Font.Color | PASS |
| calc | calc-numberformat: NumberFormat, .Text | PASS |
| calc | calc-end-usedrange: End(xlDown), End(xlUp), UsedRange | PASS |
| calc | calc-worksheets-add: Worksheets.Add, .Name, .Activate | PASS |
| calc | calc-copy: Range.Copy Destination:= | PASS |
| calc | calc-array: Mảng từ Range.Value (2 chiều) | PASS |
| calc | calc-offset-resize: Offset, Resize, Address | PASS |
| calc | calc-rows-columns: Columns.ColumnWidth, Rows.RowHeight, AutoFit | PASS |
| calc | calc-clear: ClearContents, Clear | PASS |
| calc | calc-on-error: On Error Resume Next, Err.Number | PASS |
| calc | calc-on-error-goto: On Error GoTo nhãn, Err.Raise | PASS |
| calc | calc-division-by-zero: Chia cho 0 báo lỗi 11 | PASS |
| calc | calc-strings: Split, Join, UCase, Format, Collection | PASS |
| calc | calc-dictionary: CreateObject("Scripting.Dictionary") | LIMITED |
| calc | calc-application: Application.ScreenUpdating, Calculate, StatusBar | PASS |
| calc | calc-workbook: ThisWorkbook, ActiveWorkbook.Sheets | PASS |
| calc | calc-sort: Range.Sort Key1, Order1:=xlDescending | PASS |
| calc | calc-autofilter: Range.AutoFilter Field, Criteria1 | PASS |
| calc | calc-names: Names.Add, Range("tên") | PASS |
| calc | calc-find-replace: Cells.Find, Range.Replace | PASS |
| calc | calc-merge-borders: Merge, Borders.LineStyle, HorizontalAlignment | PASS |
| calc | calc-comment: Range.AddComment | PASS |
| calc | calc-run: Application.Run, Call Sub | PASS |
| calc | calc-udf: Hàm tự viết (UDF) dùng trong ô | PASS |
| calc | calc-chart: ChartObjects.Add + Chart | PASS |
| calc | calc-shapes: Shapes.AddShape | PASS |
| calc | calc-userform: UserForm1.Show (biểu mẫu mới tạo trong HST) | LIMITED |
| writer | writer-activedocument: ActiveDocument.Content.Text | PASS |
| writer | writer-range-insert: Range.InsertAfter, InsertBefore | PASS |
| writer | writer-document-range: ActiveDocument.Range(start, end).Text | PASS |
| writer | writer-selection-typetext: Selection.TypeText, TypeParagraph | PASS |
| writer | writer-selection-font: Selection.Font.Bold, Range.Font.Size | PASS |
| writer | writer-paragraphs: Paragraphs.Count, Paragraphs(n).Range.Text | PASS |
| writer | writer-paragraph-format: Paragraphs(1).Alignment, Range.ParagraphFormat.Alignment | PASS |
| writer | writer-find-replace: Find.Execute Replace:=wdReplaceAll | PASS |
| writer | writer-find: Find.Execute không thay thế (tìm, chọn chữ tìm thấy) | PASS |
| writer | writer-tables-add: Tables.Add, Rows.Count, Columns.Count | PASS |
| writer | writer-table-cell: Table.Cell(h, c).Range.Text | PASS |
| writer | writer-words-sentences: Words.Count, Sentences(1) | PASS |
| writer | writer-bookmarks: Bookmarks.Add, Bookmarks("tên").Range | PASS |
| writer | writer-styles: Paragraphs(1).Style = "Heading 1" | PASS |
| writer | writer-header-footer: Sections(1).Headers(wdHeaderFooterPrimary) | PASS |
| writer | writer-insert-break: Selection.InsertBreak wdPageBreak | PASS |
| writer | writer-msgbox: MsgBox | PASS |
| writer | writer-loop-paragraphs: For Each p In ActiveDocument.Paragraphs | PASS |
| writer | writer-inlineshapes: InlineShapes.Count, Shapes.Count | LIMITED |
| writer | writer-fields: Fields.Add (trường DATE) | LIMITED |
| writer | writer-comments: Comments.Add | LIMITED |
| writer | writer-lists: Range.ListFormat.ApplyBulletDefault | PASS |
| writer | writer-document-properties: BuiltInDocumentProperties("Title") | PASS |
| writer | writer-userform: UserForm1.Show (biểu mẫu mới tạo trong HST) | LIMITED |
| writer-upstream | testFind.docm testAll() | PASS |
| writer-upstream | testDocumentRange.docm testAll() | PASS |
| writer-upstream | testTables.docm TestAll() | PASS |
| writer-upstream | testVBA.docm testAll() | PASS |
| writer-upstream | testFontColor.docm testAll() | LIMITED |
| writer-upstream | testSentences.docm TestAll() | LIMITED |
| writer-upstream | testWords.docm TestAll() | LIMITED |
| writer-upstream | testParagraphFormat.docm TestAll() | LIMITED |
| roundtrip | new document -> .xlsm: module kept and runs | PASS |
| roundtrip | new document -> .ods: module kept and runs | PASS |
| roundtrip | new document -> .xls: module kept and runs | PASS |
| roundtrip | new document -> .docm: module kept and runs | PASS |
| roundtrip | new document -> .odt: module kept and runs | PASS |
| roundtrip | new document -> .doc: module kept and runs | LIMITED |
| roundtrip | vba-user-function.xlsm: unchanged save keeps the original VBA | PASS |
| roundtrip | vba-user-function.xlsm: edited module saved back to .xlsm | PASS |
| roundtrip | testWords.docm: unchanged save keeps the original VBA | PASS |
| roundtrip | testWords.docm: edited module saved back to .docm | PASS |
| events | Workbook_Open runs when the .xlsm opens (macros allowed) | PASS |
| events | Vietnamese text in the code of an Excel project with a Western code page | PASS |
| events | Document_Open runs when the .odt opens (macros allowed) | PASS |
| events | Document_Open runs when the .docm opens (macros allowed) | PASS |

GUI check (`check-vba-editor.py`, 12/12): Macro VBA opens the IDE with the template in Calc and Writer, and a second call reuses Module1. Alt+F11 works in both, Alt+F8 opens the macros dialog in Calc, typing into a cell fires `Worksheet_Change`, and opening an .xlsm with macros shows the security prompt.

### Before vs after (same harness)

| | Before | After |
|---|---|---|
| Writer idioms | 12/24 (no `InsertAfter`/`InsertBefore`) | 13/24 |
| new document → .docm keeps macros | FAIL (project lost) | PASS |
| edited .docm saved back | FAIL (original stream copied) | PASS |
| .xlsm events after HST save | FAIL (`codeName` dropped) | `Workbook_Open` PASS, `Worksheet_Change` PASS (GUI) |
| Macro security | High: document macros blocked without a choice | Medium: always asks |

### Harness lessons (not product gaps)

- Basic **compile errors** open an error box that aborts a headless office when the document has a view. The runner compiles each case first in a hidden document.
- A Basic local `t` clashes with the function name `T` (case-insensitive).
- `On Error Resume Next` inside a function that already has `On Error GoTo` reports `Err.Number = 0`. The cases now use their own functions; standalone use works (13, 1001, division by zero 11).
- Cell UDFs need the document's macro mode. API-created documents default to NEVER_EXECUTE, so the runner uses USE_CONFIG like File ▸ New.
- Lock files left by crashed offices blocked fixtures, so the runner now loads copies.
- `Worksheet_Change` reacts to user edits, not to UNO `setValue`, so it is checked in the GUI test.

## Follow-up after the owner's decisions (2026-11-04)

Decisions: Medium macro security approved (recorded in `docs/BACKLOG.md`, superseding "không hạ macro security"); Alt+F8 opens the Macro dialog in Writer too (extended selection stays on the status-bar control); Alt+F11 accepted; Word VBA target ≥20/24; automatic Windows-1258 code page when a project's code page cannot hold Vietnamese text.

New core patch `patches/libreoffice/hst-vba-word.patch` (after `hst-vba-authoring.patch`):

| Gap | Fix |
|---|---|
| `Paragraph.Alignment` missing; `ParagraphFormat.Alignment` always "left" | IDL `Alignment`/`Format` on Paragraph; ParaAdjust read/written as short |
| `Table.Cell` missing | `Table.Cell(Row, Column)` + `Cell.Range` |
| `Words`, `Sentences` missing | `SwVbaTextUnits` collections (word/sentence cursors) |
| Find-only `Find.Execute` returned False | search inside the range from its start; no stale replacement; Range redefined to the found text |
| `Bookmarks.Add` collapsed | bookmark absorbs the range |
| `Sections().Headers().Range` failed | switches the unused header/footer on |
| `ListFormat.ApplyBulletDefault` missing | default bullet list style, toggles |
| `Document_Open`/`AutoOpen` never ran for .docx/.docm/.odt | events for Word 2007+ and VBA-mode documents; processor starts with the VBA globals; handler exceptions no longer abort the office |
| VBA mode lost in .odt | document settings `VBACompatibilityMode`, `VBAProjectName` |
| `Range(0, 0)` at the end of the text; collapsed `.Text` returned the next character | collapsed at the position, empty text (upstream testDocumentRange still passes) |
| Vietnamese in code of a Western-code-page project saved as "?" | VbaExport switches to Windows-1258 when the stored code page would lose characters (round trip verified: "mở" survives) |

Result: **Writer 20/24** (was 13/24), **events 4/4**, Sheets 35/37, round trip 9/10, config 13/13, GUI 12/12, upstream Word suites 4/8 (testWords/testSentences/testParagraphFormat/testFontColor still use members outside this scope and end the headless office on their unhandled errors). Remaining Writer gaps: `InlineShapes`, `Comments.Add`, `Fields.Add`, new UserForms.

Risk notes: Word events now run for .docx/.docm/VBA-mode documents only after the macro security answer allows macros; reading `Sections().Headers().Range` turns an unused header on (Word always has one). The Windows-1258 switch only happens when the old code page would lose characters; Excel/Word on non-Vietnamese Windows may display those letters wrongly in their editor, but the code is no longer destroyed.

Approval screenshots (Linux GTK3, Vietnamese UI): `scratchpad/approve/vba/` (HST menu, Công cụ tab in Writer and Sheets, editor with template, macro result in Sheets, security prompt).

## Scripting.Dictionary (owner request, `hst-vba-dictionary.patch`)

`CreateObject("Scripting.Dictionary")` failed off Windows (no COM). basic now ships its own Dictionary (`basic/source/classes/sbxdictionary.cxx`): Add (error 457 on duplicates), Item get/let, `d(k)` / `d(k) = v` (adds a missing key, like VBA), Exists, Remove (32811), RemoveAll, Count, Keys/Items arrays, CompareMode (TextCompare: case-insensitive Vietnamese keys), For Each over keys, `CreateObject`, `New Scripting.Dictionary`, `New Dictionary`, nested dictionaries. New cases: 8 in Sheets (incl. word count, dedupe a column, nested, "Hà Nội"/"hà nội"), 2 in Writer — all pass. Sheets now **43/44**, Writer **22/26**.

## Word objects (`hst-vba-word-objects.patch`)

New IDL interfaces `XInlineShape(s)`, `XComment(s)` and `Document.InlineShapes`/`Comments`: InlineShapes Count/Item/For Each/AddPicture (natural size, as character), Width/Height in points, LockAspectRatio keeps proportions, Type, Range, Delete, Select; Comments Add (spanning the range, user name as author), Range (comment text), Scope, Author, Initial, Delete. Fields.Add now creates PAGE, NUMPAGES, DATE, TIME (WdFieldType or field code; like Word it replaces the target range); Fields.Update also updates tables of contents. Writer now **26/27** (only new UserForms missing).

## UserForms (`hst-vba-userform.patch` + extension save hint)

Measured first (MiscControlTests.xls with UserForm1): **.ods keeps** the form (dialog + form module); **.xlsm and .xls lose it** — the form module comes back as a document module and the dialog is gone, because `VbaExport` writes no MS-OFORMS designer storages (upstream limitation). Fixes:
- In a VBA-mode document, a new Basic dialog (Insert ▸ Hộp thoại BASIC) is named `UserForm1…` and gets its FORM module, so `UserForm1.Show`, `Load/Unload`, `.Caption` and control events work in Sheets and Writer (GUI-verified).
- Saving a workbook with UserForms as .xlsm/.xls shows a Vietnamese hint (job `VbaSaveCheckJob`, OnSaveDone/OnSaveAsDone) to keep an .ods copy. Writing the form designs into Excel files stays on the roadmap.

## Word 97 .doc (`hst-vba-doc.patch`)

.doc saving copied only the original VBA storage. Now the current VBA-mode code is written with `VbaExport` into the "Macros" storage when the project is new or edited (`IsBasicModified`); unchanged projects and originals with UserForms are copied (the existing "VBA code will not be saved" warning still covers the latter). New document → .doc → reload: module kept and runs (**round trip 10/10**).

## Range/Selection units and the upstream TODO suites (`hst-vba-word-units.patch`)

Added Range.Words, Range.Sentences, Range.Bold, Range.Italic, Selection.Words, Selection.Sentences, Selection.ClearFormatting. As implemented, punctuation stays attached to its word (Word counts it as a separate word).

Upstream TODO suites, function by function (run in a visible headless document with an error-capturing wrapper; final `testAll` results stay 4/8 overall):

| Suite | Function | Result | Why |
|---|---|---|---|
| testWords | testWordsCount | pass | |
| testWords | testWordsStyles | fail | expects Word default sizes (10.5/14); not achievable in Writer |
| testSentences | testInsertingSentences, testSentenceStyles, testSentencesCount | pass | |
| testSentences | testSentencesPosition | fail | `Sentences.First/.Last` missing |
| testParagraphFormat | CheckLeftIndent, CheckRightIndent | pass | |
| testParagraphFormat | testAlignment | fail | exception on an attribute access |
| testParagraphFormat | testFormatBorders | fail | error 420 |
| testParagraphFormat | TestAWholeLoadOfAttributes | fail | `SpaceBeforeAuto` missing |
| testFontColor | testColor | fail | ColorIndex 6 vs Color 255 mismatch |
| testFontColor | testColorIndex | returned "1" | not "True" |
| testFontColor | testDiacriticColor | fail | `DiacriticColor` missing |
| testFontColor | testAllColors, checkColorIndexColor | fail | exception on an attribute access |

testFontColor testRangeColorFind and the two testWords functions in that probe run were not reached (probe timed out; testWords numbers come from the suite's own TestAll).

## Final pass rates

Sheets **43/43**, Writer **28/28**, settings 13/13, round trip **10/10**, events 4/4, upstream Word suites 4/8. The denominators dropped by one each compared with earlier runs: the two headless `UserForm1.Show` cases (a form that did not exist) were removed; new UserForms are covered by the GUI check instead.

## Roadmap (larger gaps, not attempted)

1. Writer: `Sentences.First/.Last`, `SpaceBeforeAuto`, `DiacriticColor`, the ParagraphFormat/Font attribute exceptions (see table).
2. UserForms in Excel/Word files: write MS-OFORMS designer storages in `VbaExport` so .xlsm/.xls/.docm keep forms (today: kept in .ods/.odt, hint when saving Excel files, Word keeps the original project).
4. Verify HST-saved .xlsm/.docm in Microsoft Excel/Word (no Office on the build host); new HST projects have no ThisWorkbook/Sheet/ThisDocument document modules.

## Open questions for the owner

1. Is someone available to verify HST-saved .xlsm/.docm in Microsoft Excel/Word on Windows (code page 1258 projects, regenerated .docm)?
2. Should `Scripting.Dictionary` be the next VBA item (most requested Excel idiom still missing)?
