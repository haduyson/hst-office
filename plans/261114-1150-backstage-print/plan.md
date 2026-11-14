# Backstage Print page (1.0.2)

Status: implemented on `feat/backstage-print`; verification is in progress (see the report).
Branch base: `feat/ribbon-adaptive` (a513bc57), on top of `rc/1.0.2-batch5`. Patch: `hst-backstage-print.patch`, which comes after `hst-ribbon-adaptive-backstage.patch` in the series.

## Outcome
File ("Tệp tin") ▸ In, Ctrl+P, and every Print command with a dialog (ribbon, menu) open a Print page inside the File panel. As in the reference suite (`plans/reports/backstage-print-shots/reference/`):
- **Settings on the left:** a big "In" button with the copies, the printer and its properties, the range/pages, the application's options (Sheets "Thu phóng", print area; Slides slides/handouts/notes), sides, collate, orientation, paper size and pages per sheet.
- **Links:** "Thiết lập trang" and "Thêm tùy chọn" (the classic dialog for the same job).
- **Preview on the right:** a live preview with page navigation and zoom.
- **Window frame:** the banner and the document tab strip stay visible. The panel's placement is `GetPlacement` from the ribbon work.

## Constraints
- Reuse the print engine and dialog code. Do not write a new printing path.
- The printout must equal the dialog's for the same options.
- The classic dialog must stay reachable.
- Own only the Print page and its wiring. The backstage frame belongs to `feat/ribbon-adaptive`.

## Non-goals
- macOS native print dialog (unchanged).
- Mail merge printing (keeps the classic dialog).
- Margin presets on the page itself. Margins are document page style, not a print setting; "Thiết lập trang" opens the page style dialog.

## Design
1. **vcl `PrintDialog` panel form.** The same class gets a second form, loaded from `vcl/ui/hstprintpanel.ui`. That file is generated from `printdialog.ui` and keeps the same ids, plus the zoom controls and the two links.
2. **`vcl::PrintJobPanel` hand-over.**
   - `Printer::PreparePrintJob` offers each interactive job to a host at the point where it would run the dialog.
   - `ResumePrintJob` is the dialog-OK path. `CancelPrintJob` is the Cancel path.
3. **sfx2 `BackstagePrintPage`.** The File panel is the host.
   - Showing the page runs `.uno:Print`, so the job comes back through the hand-over.
   - Leaving the page or closing the panel cancels the job.

## Acceptance
- Ctrl+P shows the page, and the preview renders in Writer, Sheets, Slides and Draw.
- "In" to a PDF/file printer gives the same output as the classic dialog with the same options.
- The classic dialog is reachable, and its Cancel returns to the page.
- `CppunitTest_vcl_hst_print_panel` passes, and so does `tests/unit/test_backstage_print.py`.
- gla11y is clean, and the series applies fresh.
- Linux and Windows screenshots are captured.

## Files
- **vcl:**
  - `vcl/source/window/printdlg.cxx`
  - `vcl/inc/printdlg.hxx`
  - `vcl/source/gdi/print3.cxx`
  - `include/vcl/print.hxx`
  - new: `include/vcl/hstprintjobpanel.hxx`, `vcl/source/window/hstprintjobpanel.cxx`, `vcl/uiconfig/ui/hstprintpanel.ui`
  - makefiles
  - `vcl.suppr`
  - test: `vcl/qa/cppunit/hstprintjobpanel.cxx`
- **sfx2:**
  - new: `hstbackstageprint.{hxx,cxx}`
  - hooks in `hstbackstagewindow.{hxx,cxx}` and `hstbackstage.{hxx,cxx}`
  - `hstbackstage.ui`
- **Vietnamese strings:** in the vcl and sfx2 `messages.po`.

## Risk / rollback
The hand-over is a single call in `PreparePrintJob`. Removing the `SetHost` call in `InstallFileTabHandler` brings back the classic dialog everywhere. Dropping the patch from the series reverts the whole change.
