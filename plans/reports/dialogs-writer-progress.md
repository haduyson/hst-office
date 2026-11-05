# Writer dialogs: Microsoft Word parity, progress

Survey: `dialogs-msoffice-survey-261104.md`. Check: `tests/runtime/check-dialogs-writer.py`. Screenshots: `approve/dialogs-after/writer/`. Hours in scope b+c. Actual hours are rough estimates of engineering effort, not measured; waiting for the shared build lock is excluded.

| Dialog | Status | Hours (actual / estimate) | Commit |
|---|---|---|---|
| Paragraph | done | ~2.5 / 20 | 20c3ea3 |
| Font | done (Set As Default not done) | ~2 / 18 | 7d46c59 |
| Word Count | done (Lines not done: no line count in SwDocStat) | ~0.5 / 4 | 6a50473 |
| Insert Hyperlink | done | ~0.5 / 2.5 | 0d8a566 |
| Page Setup | done; Sheets scaling stays on the sheet tab (owner decision pending) | ~2.5 / 14 | 73c4d88 |
| Header/Footer | done | ~1 / 4 | 41504f5 |
| Special Characters | done | ~1.5 / 8 | 5af19d3 |
| Insert Page Number | done (document start only, no per-section Continue) | ~1 / 6 | f10050d, f795098 |
| Slide Properties (shared page, Slides) | done: margins and paper tray hidden | ~0.5 / 2 | b656f5d |
| Borders and Shading | not started | - / 13 | |
| Insert Table (AutoFit) | not started | - / 6 | |
| Table Properties (Row, Column, Cell, Alt Text; Previous/Next Row, Text Wrapping) | done; Text Wrapping asks first because moving a table to or from a frame clears the undo history (core limit) | ~8 / 30.5 + 20 | COMMIT_TABLE |
| Picture properties and Word wrap styles | not started | - / 18 | |
| Tabs (standalone command, default tab stop) | not started | - / 4 | |
| Find and Replace tabs | not started (survey: optional) | - / 16 | |
| Bullets and Numbering, Columns, Print, Export PDF | class (a) only in the survey: no b/c work | - / 0 | |
