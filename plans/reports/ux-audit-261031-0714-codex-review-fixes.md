# HST Office v1.0.0-beta.3: UX audit (Codex review) and fixes

Date: 2026-10-31. Build: LibreOffice 26.8.1.1 + HST series, Linux GTK3, Xvfb :94 (own display, no window manager).

## Process

- Codex CLI (gpt-6-astra, xhigh) ran in 2 rounds, using `codex exec -s workspace-write`. Round 1 covered 4 areas in parallel: shortcuts, display, features and flows. Round 2 was a visual review of the runtime evidence.
- Codex's sandbox cannot reach X, sockets or `runuser`, so its round 1 was static. It also wrote probe scripts, which I ran outside the sandbox.
  - The probes proved too brittle on this shared, loaded host: 20 s connect timeouts, and other agents relinking `libmergedlo.so` mid-run.
  - Instead, I collected runtime evidence with a simple harness on a hard-linked instdir snapshot (`tests/output/codex-ux-audit/instdir-snap`). That gave 76 screenshots plus window geometry, in vi, en, dark-requested and DPI 144.
  - Codex then reviewed every screenshot.
- I reproduced each finding before fixing it.
- Codex reports:
  - `plans/reports/codex-ux-audit-261031-{shortcuts,display,features,flows}-static.md` (static);
  - `plans/reports/codex-ux-audit-261031-runtime-review.md` (visual review and re-assessment).
- Evidence is under `tests/output/codex-ux-audit/evidence/` and `tests/output/shortcuts/`.
- No blocker was found.

## Findings

| ID | Area | Severity | Status | Commit |
|---|---|---|---|---|
| DSP-01 | Licence dialog showed "Copyright © 2000–2026 LibreOffice contributors. All rights reserved." (vi: "Bảo lưu mọi quyền"), not the owner's copyright line | major (owner rule) | fixed: fixed Vietnamese summary with "© 2026 HASON TECH · © 2000–2026 The Document Foundation và các tác giả LibreOffice"; the upstream URL and "All rights reserved" are removed (`hst-ux-fixes.patch`, sfx2 `appserv.cxx`) | b9848cd |
| DSP-02 | Licence summary was English in the en UI (legal text must be Vietnamese) | minor | fixed (same change) | b9848cd |
| DSP-03 | Options → HTML Compatibility read "LibreOffice Basic" in en | cosmetic | fixed: `%PRODUCTNAME _Basic` (`opthtmlpage.ui`) | b9848cd |
| FEA-02 | en Extension Manager install confirmation lacked the HST third-party/responsibility notice | minor | fixed: English version of the notice for non-vi UIs (`dp_gui_dialog2.cxx`); default Cancel kept | b9848cd |
| NEW-01 | NĐ 30 wizard was 1350×815 px, taller than a 1366×768 screen, so "Chèn văn bản" was off-screen on common laptops | major | fixed: compacted to 600×300 AppFont (675 px measured, `fix-nd30-compact.png`) | 70ba5a6 |
| DSP-05 | NĐ 30 validation status had room for one line only | minor | fixed: status 24 units (two lines). Messages no longer repeat the field name ("Số: số: …" → "Số: chỉ gồm chữ số") | 70ba5a6 |
| FEA-01 / DSP-06 | Update menu items (HST menu, Help menu, ribbon) were Vietnamese in the en UI | minor | fixed: "Check for Updates…" / "Check for HST Office Updates…" in `Addons.xcu`. The update result dialogs stay Vietnamese by design (docs/UPDATE_CHECK.md) | 70ba5a6 |
| FEA-03 | Malformed CSV error showed Python's English parser text ("row 2: unexpected end of data") | minor | fixed: localized "(lỗi gần hàng N, thường do dấu ngoặc kép chưa đóng)" | 70ba5a6 |
| FEA-04 | Undo entries "Insert ND30 document", "Import CSV" and "Convert … to Unicode" were English in the vi UI | cosmetic | fixed: localized undo titles (`locales/*.json` `undo`) | 70ba5a6 |
| KEY-03 | Offline guide shortcut page omitted the document-tab keys | minor | fixed: Ctrl+Alt+. / Ctrl+Alt+, and Ctrl+W added to `help/phim-tat.html` | 70ba5a6 |
| FLO-03 | vi lock error said "không bị khóa bởi người khác" (inverted meaning) | minor | fixed: "Tệp $(ARG1) hiện không do bạn khóa." (`l10n/vi-overrides.jsonl`) | 7fc902d |
| RV-01 | PDF export option "Xuất placeholder (R)" was untranslated | minor | fixed: "Xuất bộ giữ chỗ (_R)" plus tooltip (glossary "Bộ giữ chỗ") | 7fc902d |
| FEA-05 | Installed updater was stamped 1.0.0-beta.2 | major (build state) | fixed by rebuilding the extension package; source `data/hst/release.json` was already beta.3. No code change | — |
| KEY-T | Shortcut table: Ctrl+A/B/I/U/Z/Y/X/V/S/F/H/Shift+S/O/P, F7, F12, F1, Ctrl+N, Ctrl+Alt+,/., Ctrl+W, Calc Ctrl+B/Z/1, Impress F5/Esc, Ctrl+Q | — | verified OK: new `tests/runtime/check-shortcuts.py` 55/55 (vi full, en subset) | b39fd87 |
| KEY-01 | Duplicate ribbon-tab mnemonics in vi (T: Tập tin/Trang đầu; C: Chèn/Tham chiếu/Công cụ; X: Xem lại/Xem) | minor | deferred: Alt+letter does not switch notebookbar tabs at all under GTK3 here (`fix-ribbon-alt-*.png`), so there is no observable effect; translations left unchanged | — |
| KEY-02 | Duplicate mnemonics in the classic vi menus (C: Chỉnh sửa/Công cụ; File: Mở/Mẫu) | minor | deferred: the classic menu bar is hidden in the default Tabbed UI; needs a coordinated glossary pass | — |
| RV-02 | Template Manager shows "Japanese normal" instead of the existing vi name | cosmetic | deferred: upstream case-sensitive name lookup (`sfx2/source/doc/doctempl.cxx`) | — |
| RV-03 | en Impress sidebar: the Slide → Format box is blank (vi shows "Màn hình 16:9") | minor | deferred: root cause not found (svx `papersizelistbox` / sd `SlideBackground`) | — |
| DSP-04 | Extension dialog colours in dark mode | minor | not verifiable: the dark appearance is not applied under GTK3/Xvfb; check on a real dark desktop | — |
| NEW-02 | Options dialog is 1104×822 px at 1600×1000 | — | not a defect: upstream caps the dialog at 80 % of the screen height (Codex checked `treeopt.cxx`) | — |
| FLO-01 | Window titles read "… — HST Office Writer/Calc/Impress", while the welcome dialog and README say HST Writer/Sheets/Slides | cosmetic | question for owner (current titles are asserted by `check-window-title.py`) | — |

The extension install confirmation, the undo titles and the PDF translation were not captured on screen: the extension flow needs a file chooser, and the other two were checked in the installed files and `.mo` catalog.

### For the banner/tabs owners (not fixed here)

- **Tabs, minor.** The Start Center tab is labelled "Start Center" in English in the vi UI (`vi-tabs.png`, `vi-w-close-query.png`).
- **Tabs, minor (FLO-02).** File → Exit / Ctrl+Q with 3 modified tabs: Cancel on the first save prompt does not stop the quit. All 3 prompts appear, and nothing is closed or lost.
  - This is upstream `Desktop::impl_closeFrames` behaviour (`continue` after a refused suspend). It is inconsistent with the title-bar X, which stops at the first Cancel.
  - Evidence: `quit-cancel-prompt0..2.png`.
- **Banner:** no findings.

## Files

- New patch `patches/libreoffice/hst-ux-fixes.patch`, appended to the series before `hst-digital-signature.patch`:
  - `sfx2/source/appl/appserv.cxx` (on top of hst-about/hst-debrand);
  - `cui/uiconfig/ui/opthtmlpage.ui`;
  - `desktop/source/deployment/gui/dp_gui_dialog2.cxx` (on top of hst-extensions).
- Extension, `extensions/hst-vietnamese-tools/`:
  - `Addons.xcu`;
  - `locales/{vi,en}.json`;
  - `help/phim-tat.html`;
  - `python/hst_office/` `actions.py`, `nd30_writer.py`, `csv_calc.py`, `encoding_writer.py`, `wizard_csv.py`, `wizard_nd30.py`.
- `l10n/vi-overrides.jsonl`: 3 rows.
- Tests:
  - new `tests/runtime/check-shortcuts.py`;
  - `check-vi-intro.py`: asserts the licence copyright line;
  - `check-update-notify.py`: the policy phase now honours `--display`, where before it was hard-wired to :97.

## Verification

- **Builds** (as hstbuild, incremental): sfx2, `Library_merged`, `UIConfig_cui`, `Library_deploymentgui`, the uui/flt `.mo` files and the extension package. Each upstream edit was compiled before moving on.
- **`apply-patches.sh --check`:** every patch applied. The committed series plus the new patch applies to pristine 26.8.1.1 files from the release tarballs: 22/22.
- **Runtime checks on the snapshot, :94:**

| Check | Result |
|---|---|
| check-shortcuts | 55/55 |
| check-defaults | 18/18 |
| check-office-roundtrip | 9/9 |
| check-no-libreoffice-ui | PASS |
| check-vi-intro | 13/13 static + GUI |
| check-window-title | 9/9 |
| check-style-gallery | 4/4 |
| check-template-manager | 7/7 |
| check-update-notify | 11/11 |

  - window-title, style-gallery, template-manager and update-notify each failed once in the first pass. The cause was startup timing, or my own parallel runs on the same display. They passed on a clean rerun.
- **Unit tests:** `python3 -m unittest discover -s tests/unit`: 117 OK.
- **`scripts/ci-quality.sh`:** 25 commands, 0 failures.
- **Xvfb :94** was stopped at the end.

## Unresolved questions

1. FLO-01: should window titles use HST Writer / HST Sheets / HST Slides instead of "HST Office Writer/Calc/Impress"? This is an owner decision; the tests assert the current form.
2. KEY-01/KEY-02: should a native reviewer reassign the Vietnamese mnemonics as a glossary pass?
3. FLO-02: should Cancel during Quit stop the whole quit, like the title-bar X? This is for the tabs owner.

Status: DONE_WITH_CONCERNS
Summary: Codex audited the 4 areas, then visually reviewed 76 runtime screenshots. 13 confirmed defects are fixed: 2 major (the licence "All rights reserved" line and the NĐ 30 wizard not fitting 1366×768) plus minor/cosmetic localisation and branding issues. A new check-shortcuts runtime test passes 55/55, all listed regression checks pass, and ci-quality has 0 failures.
Concerns/Blockers: 2 tabs items are routed (English "Start Center" tab label in vi; Cancel during Quit continues). Dark mode and real 1366×768 / HiDPI behaviour remain unverified under Xvfb. KEY-01/02, RV-02 and RV-03 are deferred.
