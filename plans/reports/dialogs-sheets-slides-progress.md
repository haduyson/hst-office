# Sheets and Slides dialogs: Microsoft Office parity progress

Scope: class (b) and (c) items of `plans/reports/dialogs-msoffice-survey-261104.md` for Sheets and Slides.
Check: `tests/runtime/check-dialogs-sheets.py`, `tests/runtime/check-dialogs-slides.py`.

| Dialog | Survey class | State | Patch | What changed | Not done, and why |
|---|---|---|---|---|---|
| S1 Format Cells | b+c | Done | `hst-dlg-sheets-format-cells.patch` | Tabs Số, Căn chỉnh, Phông chữ (with the effects), Viền, Tô màu, Bảo vệ. "Gộp ô" checkbox. "Kế toán" category. Categories in Excel's order. | No "Special" category. |
| S2 Sort | b | Done | `hst-dlg-sheets-sort.patch` | Header option first, one row per level, Add Level and Delete Level. | Not a real grid: Delete removes the last level. No sort by colour (survey: not recommended). |
| S3 AutoFilter / Filter | a | No b/c item | none | | Text belongs to the class-(a) work. |
| S4 Conditional Formatting | b | Done | `hst-dlg-sheets-cond-format.patch` | Seven rule types, each with its own conditions. Manager lists the rule first. | Cell styles instead of direct formats; no Stop If True (survey: 40 h, not recommended). |
| S5 Data Validation | a | No b/c item | none | | Text belongs to the class-(a) work. |
| S6 Insert / Delete Cells | a | No b/c item | none | | Text belongs to the class-(a) work. |
| S7 Page Setup (sheet) | b+c | Partly done | `hst-dlg-sheets-page-setup.patch` | Tabs in Excel's order, opens on Trang. Print Titles fields, applied on OK. | Margins tab and moving scaling need `pageformatpage.ui` (shared page, Writer agent). "Chung" stays first: moving it needs sfx2. Print Titles are text fields without a cell picker. |
| S8 Insert Chart | a | Done (order) | `hst-dlg-sheets-chart.patch` | Chart types in Excel's order. | Wizard kept; Recommended Charts not included (survey: not recommended). |
| S9 Name Manager | b+c | Partly done | `hst-dlg-sheets-name-manager.patch` | Value column. | Comment column needs a model property and a file round trip. |
| S10 Insert Function | a | No b/c item | none | | Text belongs to the class-(a) work. |
| P1 Slide Properties | b | Partly done | `hst-dlg-slides.patch` | "Định dạng nền" tab name. | Hiding paper tray and margins needs `page.cxx` (shared page, Writer agent). |
| P2 Transitions sidebar | a | Done (order) | `hst-dlg-slides.patch` | Effect options, sound, duration. | Ribbon tab is ribbon work. |
| P3 Animation sidebar | a | Done (order) | `hst-dlg-slides.patch` | Direction before start, duration, delay. | Ribbon tab and pane are ribbon work. |
| P4 Slide Show settings | a | Done (order) | `hst-dlg-slides.patch` | Show type and options first, then slides, then displays. | |
