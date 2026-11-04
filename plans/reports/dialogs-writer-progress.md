# Writer dialogs: Microsoft Word parity, progress

Survey: `dialogs-msoffice-survey-261104.md`. Check: `tests/runtime/check-dialogs-writer.py`. Screenshots: `approve/dialogs-after/writer/`. Hours in scope b+c.

| Dialog | Status | Hours (actual / estimate) | Commit |
|---|---|---|---|
| Paragraph | done | ~2.5 / 20 | see git log (hst-dlg-paragraph.patch) |
| Font | done (Set As Default not done) | ~2 / 18 | see git log (hst-dlg-font.patch) |
| Word Count | done (Lines not done: no line count in SwDocStat) | ~0.5 / 4 | see git log (hst-dlg-word-count.patch) |
| Insert Hyperlink | done | ~0.5 / 2.5 | see git log (hst-dlg-hyperlink.patch) |
| Page Setup | done; Sheets scaling stays on the sheet tab (owner decision pending) | ~2.5 / 14 | see git log (hst-dlg-page-setup.patch) |
| Header/Footer | done | ~1 / 4 | see git log (hst-dlg-header-footer.patch) |
| Special Characters | done | ~1.5 / 8 | see git log (hst-dlg-special-character.patch) |
| Insert Page Number | done (document start only, no per-section Continue) | ~1 / 6 | see git log (hst-dlg-page-number.patch) |
| Slide Properties (shared page, Slides) | done: margins and paper tray hidden | ~0.5 / 2 | see git log (hst-dlg-slide-properties.patch) |
