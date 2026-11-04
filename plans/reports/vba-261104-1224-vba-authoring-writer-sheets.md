# VBA authoring in HST Writer and HST Sheets: report

Date: 2026-11-04. Target: 1.0.0-beta.5. Owner request: "Bổ sung thêm VBA cho Writer và Sheets". Users must be able to write and edit VBA macros as in the Microsoft Office VBA editor.
Entry point name decided by the owner: **"Macro VBA"**.

## Summary

- **Sheets (Excel VBA): 35/37 idioms pass.** Only `Scripting.Dictionary`/COM objects and newly authored UserForms are missing.
- **Writer (Word VBA): 13/24 idioms pass.** The baseline was 12/24 with the harness fixed: `Range.InsertAfter`/`InsertBefore` were missing and are now patched. Upstream Word VBA suites: 4/8 pass. The other 4 are upstream "TODO" suites.
- **Round trip: 9/10.** New and edited macros now survive .xlsm, .xls, .ods, .odt **and .docm**. Before this work, .docm lost every new or edited macro. .doc does not keep new macros.
- **Events:** `Workbook_Open` and `Worksheet_Change` now run after an HST save of .xlsm. Before, the code names were dropped and the modules came back orphaned. Writer `Document_Open`/`AutoOpen` do not run after an HST save (roadmap).
- **Entry points:** HST menu "Macro VBA", a Tools-tab ribbon button "Macro VBA", Alt+F11 (Writer/Sheets) and Alt+F8 (Sheets only). The GUI check passes 11/11.
- **Defaults:** VBA load/executable/save were already on upstream (verified). Macro security changed from High to **Medium**, so the user is always asked and nothing runs silently.

Measured with `tests/runtime/check-vba.py` (headless, fresh profile, soffice as hstbuild) and `tests/runtime/check-vba-editor.py` (GTK3 under Xvfb, Vietnamese UI). Evidence: `tests/output/vba/evidence.json`, `tests/output/vba/matrix.md`.

## What changed

| Area | Change | Files |
|---|---|---|
| Command | `org.hst.office.vi:EditVba`. In a document without Basic code it switches on VBA mode, project `VBAProject` (Sheets) or `Project` (Writer), and VBA code page Windows-1258. It creates `Module1` with `Option VBASupport 1`, a Vietnamese guide and the example `Sub XinChao`, then opens the Basic IDE on that Sub. It reuses the existing VBA module of Excel/Word files. A document that already has LibreOffice Basic code keeps its mode, and only the new module gets VBA support. | `extensions/hst-vietnamese-tools/python/hst_office/vba.py`, `vba_template.py`, `actions.py` |
| HST menu | "Macro VBA" (m9, Writer and Sheets only), placed before "Tìm tính năng…". The last two items are unchanged (m10–m12 renumbered). | `Addons.xcu`, `locales/*.json`, `tests/unit/test_hst_menu_order.py` |
| Shortcuts | `Accelerators.xcu` in the extension. Alt+F11 opens EditVba in Writer and Calc. It replaces, in those two modules only, the global Alt+F11 = Basic Macros dialog. Alt+F8 opens `.uno:MacroDialog` in Calc only. | `Accelerators.xcu`, `META-INF/manifest.xml` |
| Core patch | `hst-vba-authoring.patch`: (1) Tools-tab button "Macro VBA" (tooltip "Soạn và chạy macro VBA (Alt+F11)") in the sw/sc notebookbar; (2) MacroSecurityLevel 2→1; (3) Word `Range.InsertBefore/InsertAfter` (oovbaapi IDL + `sw/source/ui/vba/vbarange`); (4) .docm export writes the current VBA project with `VbaExport`, but keeps the original stream when it contains UserForm designer storages; (5) .xlsx/.xlsm export writes `sheetPr`/`workbookPr` `codeName`. | `patches/libreoffice/hst-vba-authoring.patch` |
| Help | New F1 page `macro-vba.html`: open the editor, first macro in Sheets and in Writer, run, save formats, security prompt and compatibility tables. It has 2 screenshots (gtk3/Xvfb) and is linked in every sidebar, the index, the page navigation and the shortcuts page. | `help/macro-vba.html`, `help/images/macro-vba-*.png`, sidebars, `phim-tat.html` |
| Tests | Runtime matrix and round trip (`check-vba.py` + `vba_cases.py`), GUI entry points (`check-vba-editor.py`), unit tests (`test_vba_authoring.py`, menu order). | `tests/runtime/`, `tests/unit/` |
| l10n | Access-key snapshot regenerated (new ribbon label). | `l10n/access-keys-snapshot.json` |

Builds run as hstbuild: oovbaapi, Library_vbaswobj, Library_msword, Library_scfilt, UIConfig sc/sw, officecfg + postprocess, ExtensionPackage. No desktop build.

## Shortcut decisions (Alt+F11 / Alt+F8 / macOS)

- **Alt+F11** was **not free**. Upstream binds it globally to `.uno:MacroDialog` (Basic Macros organizer). It is now remapped in the Writer and Calc modules only, to open the VBA editor directly, as Excel and Word do. The organizer stays reachable: Calc via Alt+F8, both via the Tools tab or menu. Impress and Draw keep the global binding.
- **Alt+F8**: free in Calc, so it is mapped to `.uno:MacroDialog`, the Run/Edit/Assign dialog that matches Office's "Macros" dialog. In **Writer it is taken** by `.uno:SetExtSelection` (extended selection). Following the "if free" rule it is not remapped there; this is an open question for the owner.
- **macOS**: MOD2 = Option, so the keys are Option+F11 and Option+F8. With media keys on, F11 is volume-down and Option+volume opens Sound settings, so users need **fn+Option+F11**. This is the same as Excel for Mac and is documented on the help page. It was not run on a Mac.

## Compatibility table (final run)

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
| writer | writer-paragraph-format: Paragraphs(1).Alignment | LIMITED |
| writer | writer-find-replace: Find.Execute Replace:=wdReplaceAll | PASS |
| writer | writer-find: Find.Execute không thay thế (tìm, chọn chữ tìm thấy) | LIMITED |
| writer | writer-tables-add: Tables.Add, Rows.Count, Columns.Count | PASS |
| writer | writer-table-cell: Table.Cell(h, c).Range.Text | LIMITED |
| writer | writer-words-sentences: Words.Count, Sentences(1) | LIMITED |
| writer | writer-bookmarks: Bookmarks.Add, Bookmarks("tên").Range | LIMITED |
| writer | writer-styles: Paragraphs(1).Style = "Heading 1" | PASS |
| writer | writer-header-footer: Sections(1).Headers(wdHeaderFooterPrimary) | LIMITED |
| writer | writer-insert-break: Selection.InsertBreak wdPageBreak | PASS |
| writer | writer-msgbox: MsgBox | PASS |
| writer | writer-loop-paragraphs: For Each p In ActiveDocument.Paragraphs | PASS |
| writer | writer-inlineshapes: InlineShapes.Count, Shapes.Count | LIMITED |
| writer | writer-fields: Fields.Add (trường DATE) | LIMITED |
| writer | writer-comments: Comments.Add | LIMITED |
| writer | writer-lists: Range.ListFormat.ApplyBulletDefault | LIMITED |
| writer | writer-document-properties: BuiltInDocumentProperties("Title") | PASS |
| writer | writer-userform: UserForm1.Show (biểu mẫu mới tạo trong HST) | LIMITED |
| writer-upstream | testFind.docm testAll() | PASS |
| writer-upstream | testDocumentRange.docm testAll() | PASS |
| writer-upstream | testFontColor.docm testAll() | LIMITED |
| writer-upstream | testSentences.docm TestAll() | LIMITED |
| writer-upstream | testWords.docm TestAll() | LIMITED |
| writer-upstream | testParagraphFormat.docm TestAll() | LIMITED |
| writer-upstream | testTables.docm TestAll() | PASS |
| writer-upstream | testVBA.docm testAll() | PASS |
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
| events | Vietnamese text in the code of an Excel project with a Western code page | LIMITED |
| events | Document_Open runs when the .odt opens (macros allowed) | LIMITED |
| events | Document_Open runs when the .docm opens (macros allowed) | LIMITED |

GUI check (`check-vba-editor.py`, 11/11): Macro VBA opens the IDE with the template in Calc and Writer, and a second call reuses Module1. Alt+F11 works in both, Alt+F8 opens the macros dialog in Calc, typing into a cell fires `Worksheet_Change`, and opening an .xlsm with macros shows the security prompt.

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

## Roadmap (larger gaps, not attempted)

1. **Writer object model**: `Table.Cell`/`Rows(i).Cells`, `Words`, `Sentences`, `InlineShapes`, `Comments`, `Fields.Add`, `Paragraph.Alignment`/`Format`, `Sections().Headers` when no header exists, `ListFormat.ApplyBulletDefault`, `Find.Execute` without replace (returns False), `Bookmarks().Range` (returns 1 character). Each is an IDL + `sw/source/ui/vba` addition similar to InsertAfter. Upstream has failing suites for Words, Sentences, ParagraphFormat and FontColor.
2. **Writer document events after an HST save**: `Document_Open`/`AutoOpen` do not fire in .docm regenerated by VbaExport, while the original Word file works. In .odt the VBA mode is not stored (`VBACompatibilityMode` False after reload). Needs investigation in the sw VBA import and in ODF VBA-mode persistence.
3. **UserForms**: no Excel-style form designer for new forms (Basic dialogs only). VbaExport writes no designer storages, so an .xlsm with UserForms saved by HST may lose them. This is upstream Calc behaviour and was not measured; Writer now keeps such projects unchanged.
4. **Code page of existing projects**: Excel/Word projects created with a Western code page (1252) cannot store Vietnamese letters, which become "?" on save. Option: offer to switch `VBATextEncoding` to 1258 for the project, but check how Excel then reads it.
5. **`Scripting.Dictionary`** (very common in Excel code): a Basic-side implementation via `ooo.vba` or a built-in class.
6. **Excel opening HST-made .xlsm/.docm**: not verified, because no Microsoft Office on the build host. New HST projects contain no ThisWorkbook/Sheet document modules; Excel normally recreates them.
7. **.doc** (Word 97) does not export new VBA projects.

## Open questions for the owner

1. **Alt+F8 in HST Writer** is extended-selection mode upstream. Should it open the Macro dialog as in Word, with extended selection left on F8 cycling / the status-bar control?
2. **Alt+F11** now opens the VBA editor instead of the Basic Macros organizer in Writer and Sheets. Please confirm.
3. **Macro security Medium** (always ask) replaces High. The backlog item LO-EXT-01 said "không hạ macro security", but that was about the extension spike. Please confirm Medium is the intended policy for beta.5.
4. Do you want HST to **switch existing Western-code-page VBA projects to Windows-1258** so Vietnamese text in code survives (roadmap 4)?
5. Is someone available to **verify HST-saved .xlsm/.docm in Microsoft Excel/Word** on Windows?
