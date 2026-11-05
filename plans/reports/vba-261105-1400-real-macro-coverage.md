# Real VBA macros running in HST: coverage

Status: in progress. Updated with each committed batch. Procedures are public parameterless Subs run one at a time in a
disposable container (no network, not root, read-only copy). The harness is in `tests/runtime/vba-corpus/`.

## Coverage

| Measure | Baseline (only the IDE crash fix) | Batch 3 build |
|---|---:|---:|
| Macro files | 962 | 962 |
| Blocked by safety policy | 55 | 55 |
| Files reached | 861 | 907 |
| Procedures run | 2263 | 2418 |
| Pass | 874 (38.6%) | 1289 (53.3%) |
| Ended without returning (mostly compile errors) | n/a | 153 |
| Timeout | 46 | 55 |

More procedures run now because more modules compile; compare the rates with care.

"Pass" means the procedure ended without an error. It is not proof of a correct result. Correctness is verified only where
stated below.

## Batches

1. Crash fix, Scripting objects, VBA names, language gaps, ListObjects, Word Find and Range, theme colours.
2. Compile fixes (`If c Then Foo 1 Else Foo 2`, `Dim step`, `Property` as a name, numbered lines, `With New`, `!field` in With,
   dates with blanks, Enum defaults); class TypeName and `Set` to an interface; Err 9; Type members Name and Parent; Evaluate,
   Sort, FindNext, FormatConditions, RemoveDuplicates, TextToColumns, Tab, Application settings, Filters; Word Range and
   Selection moves, clipboard, contents, Word tables, notes, hyperlinks, Document members; Shape OnAction and cells, AddPicture,
   chart series. A regression in this batch made `d("a") = 1` on `Dim d As Object` fail with Err 91 for two builds; the fix is
   in this batch.
3. Class events with arguments, ReDim of members, Null and Office-constant defaults, New as an argument, continued calls,
   qualified types (`As Scripting.Dictionary`), Word text and paragraph marks, Style by name, FileDialog in Word, Find.Found,
   Workbook properties and RefreshAll, sheet hyperlinks, Sleep and GetTickCount, form control members.

## Verified

- Upstream `sw/qa` Word VBA suites: 29 of 37 assertions at baseline, 34 of 37 now. The rest: testSentences expects a
  trailing vbCr on `Last`, testWords is inconsistent upstream, testParagraphFormat is being rechecked.
- Regression cases, one per fix, in `tests/runtime/check-vba-corpus-regression.py`: 113 of 116 pass on the batch 3 build,
  class events included. Open: Range.ComputeStatistics word count, Document members (an interface attribute throws),
  Series.Name from a cell address.
- Open: the office ended in 1 of 3 full regression runs, at a different case each time (FsoNames, ParagraphsOfRangeAndSelection, static_private); cause not found yet.
- Vietnamese identifiers and strings in cp1258 and cp1252 modules: 6 of 6.
- Scripting.Dictionary, FileSystemObject and RegExp through CreateObject and early binding.

## Not verified

- Formula cells against values stored by Excel: counted, not yet compared with file values.
- Forms from real files: partial run on an old build, 16 of 46 opened; to be rerun. Handlers fired by CallByName are not
  mouse clicks; real clicks are covered only by `check-vba-form-events.py`.
- Windows-only calls (Declare, Outlook, Word automation from Excel, WScript) do not run here and are counted as failures.

## Top gaps on the batch 3 build

| Gap | Procedures | Files |
|---|---:|---:|
| Ended without returning, mostly modules that still do not compile | 153 | 51 |
| Err 9: sheet or element missing; mostly sheets the file lacks, not checked one by one | 137 | 58 |
| Object variable not set | 132 | 69 |
| Invalid object reference: `New` of Windows-only classes or of a class that did not compile | 78 | 33 |
| Timeout | 55 | 39 |
| Generic RuntimeException | 45 | 24 |
| Windows API calls (Declare) other than Sleep and GetTickCount | 28 | 4 |
| Control.BackColor not found | 24 | 7 |
| Charts beyond SeriesCollection, PivotCaches, QueryTables, SlicerCaches | not ranked | 15 to 35 each |

## Corpus

773 GitHub files from 375 repositories (313 without a licence, fetched at test time from pinned commits and not committed),
106 from the govdocs corpus, 83 from LibreOffice's qa trees. Authoring app from metadata: Excel 801, Word 68.

It does not represent government or SME macros. It leans to Excel, to hobby and developer projects, and to English. Most
useful samples: real office templates from Vietnamese agencies and companies (payroll, reporting forms, Word mail merge and
form letters), with their macros and data removed of personal details.
