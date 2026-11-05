# Real VBA macros running in HST: coverage

Status: in progress. Updated with each committed batch. Procedures are public parameterless Subs run one at a time in a
disposable container (no network, not root, read-only copy). The harness is in `tests/runtime/vba-corpus/`.

## Coverage

| Measure | Baseline (only the IDE crash fix) | Batch 1, run on an earlier build, GitHub part unfinished |
|---|---:|---:|
| Macro files | 962 | 962 |
| Blocked by safety policy | 55 | 55 |
| Files loaded and scanned so far | 861 | 900 of 962 reached, 711 of 773 GitHub files |
| Procedures run | 2263 | 2317 |
| Pass | 874 (38.6%) | 1155 (49.8%) |
| Fail, not pass | 1389 | 1162 |

The second column comes from a build with the first 10 of the 13 patches in batch 1: it does not include hst-vba-language-3 or
the theme colour patches. Full before and after tables replace it when a complete run finishes on a batch build. The two columns
ran different subsets of procedures, so compare the rates with care.

"Pass" means the procedure ended without an error. It is not proof of a correct result. Correctness is verified only where
stated below.

## Verified

- Upstream `sw/qa` Word VBA suites: 29 of 37 assertions at baseline, 34 of 37 now. The rest: testSentences expects a
  trailing vbCr on `Last`, testWords is inconsistent upstream, testParagraphFormat is being rechecked.
- Regression cases, one per fix, in `tests/runtime/check-vba-corpus-regression.py`. Three class cases (TypeName, Set to an
  implemented interface, RaiseEvent) and three language cases (Err 9 on a missing sheet, Type members called Name) fail until
  the next batch.
- Open: FsoNames ended the office in 1 of 3 runs of its file on the batch build and passed alone twice; cause not found yet.
- Vietnamese identifiers and strings in cp1258 and cp1252 modules: 6 of 6.
- Scripting.Dictionary, FileSystemObject and RegExp through CreateObject and early binding.

## Not verified

- Formula cells against values stored by Excel: counted, not yet compared with file values.
- Forms from real files: partial run on an old build, 16 of 46 opened; to be rerun. Handlers fired by CallByName are not
  mouse clicks; real clicks are covered only by `check-vba-form-events.py`.
- Windows-only calls (Declare, Outlook, Word automation from Excel, WScript) do not run here and are counted as failures.

## Top gaps, by procedures in the latest run

| Gap | Procedures | Files | State |
|---|---:|---:|---|
| Module does not compile: `If c Then Foo 1 Else Foo 2`, `Dim step`, `Property` as a name, numbered lines, `With New`, `!field` in With, dates with blanks | 177+ | 49 | fix in the next batch |
| Object variable not set, partly from the compile failures above | 120 | 46 | under investigation |
| Invalid object reference: `New` of a class module that failed to compile | 64 | 28 | follows the compile fixes |
| Missing element raised a generic error, not Err 9 | 90 | 37 | fix in the next batch |
| Incorrect property value, generic RuntimeException | 80 | 24 | under investigation |
| Evaluate, Worksheet.Sort, FindNext, FormatConditions, FileDialog.Filters, RemoveDuplicates, TextToColumns, Tab, Application settings | about 60 | about 40 | fix in the next batch |
| Charts (ActiveChart, SeriesCollection), Shape.OnAction, AddPicture | not ranked | not ranked | open |
| Word: Tables (Rows.Add, Style, Borders), Styles("Normal"), PageSetup, Document and Selection members | few files in corpus | few | open |

## Corpus

773 GitHub files from 375 repositories (313 without a licence, fetched at test time from pinned commits and not committed),
106 from the govdocs corpus, 83 from LibreOffice's qa trees. Authoring app from metadata: Excel 801, Word 68.

It does not represent government or SME macros. It leans to Excel, to hobby and developer projects, and to English. Most
useful samples: real office templates from Vietnamese agencies and companies (payroll, reporting forms, Word mail merge and
form letters), with their macros and data removed of personal details.
