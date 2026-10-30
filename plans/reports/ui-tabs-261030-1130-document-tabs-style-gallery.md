# Document tabs, style gallery, Vietnamese intro texts, window titles

Date 2026-10-30. Tree: LibreOffice 26.8.1.1 + HST series. Linux GTK3 under Xvfb :97 (no WM).

## A. Document tabs: design decision

**Chosen: option 2, "tab group" of ordinary task frames.** Each document keeps its own frame and
top-level WorkWindow (menubar, Tabbed ribbon, sidebar, status bar, title unchanged). Group members
share position/size/maximized state. Only the active one is mapped; the others are parked
(`Show(false)`), so the taskbar shows one entry. A VCL-painted tab strip sits between the top docking
area and the document. It is placed by `LayoutManager::implts_doLayout` and works for every module
and for the Start Center.

Rejected: option 1, one top-level hosting several frames. Notebookbar and menubar belong to the
SystemWindow, frame activation relies on XTopWindowListener, and sfx2 uses `GetSystemWindow()`
widely, so this would be a deep framework/vcl rewrite with high regression risk on GTK3 and Windows.
Reparenting via `SystemChildWindow`/plugin parent, or sub-frames, have the same problems.

**Kongming advice (summary)**, applied unless noted:
- It confirmed option 2.
- Critical trap: a frame's `IsHidden` follows window visibility (`XFrameImpl::windowHidden`), not the
  Hidden load flag. Without a fix, closing the shown tab with the titlebar X terminates the app, and
  CloseWin turns the tab into the Start Center. Fix: parked frames keep `IsHidden=false`.
- Close a tab with `.uno:CloseWin`, not CloseDoc (CloseDoc would close all views of the document).
- Join before the window is mapped (geometry set while unmapped), with a WindowShow listener as
  fallback.
- Activate the frame explicitly after a switch (no WM means no focus events).
- Suppress showing the neighbour tab while the app terminates; handle autorecovery.
- Use real dispatch commands plus accelerators, not a global key hook.
- Strip in LayoutManager, not an sfx2 child window. Exclusions: sub-frames, Help, headless/LOK,
  non-WorkWindow containers.
- Deviation: kongming suggested an `XTerminateListener` to suppress neighbour showing. In
  `Desktop::terminate` the frames close before `queryTermination`, so instead `setClosingAll()` is
  wrapped around `impl_closeFrames`.
- Deviation: kongming suggested a WorkWindow subclass as the pre-show hook. I used explicit
  `prepareShow()` calls in LoadEnv, `SfxFrame::Appear` and autorecovery, plus the WindowShow
  fallback, which avoids changing how TaskCreator creates windows.

**Behaviour**
- New or opened documents become the active tab.
- Tab strip: title, a dot in the module colour when modified, a close button on each tab, a module
  colour mark, and "+" with a menu: Văn bản / Bảng tính / Trình chiếu / Mở tệp…. Middle-click closes.
- Writer, Calc and Impress tabs can be mixed.
- A tab's close button activates the tab first if it is modified, then dispatches CloseWin, so the
  save query is parented to a visible window.
- Closing the last tab turns it into the Start Center (upstream behaviour). The Start Center closes
  when the first document opens (its frame is reused).
- Option `Office.Common/Misc/DocumentTabs` (default true) in Tools > Options > HST Office > General >
  "Thẻ tài liệu". Turning it off dissolves the group into cascaded windows.
- **Shortcuts:** Ctrl+Alt+. = next tab, Ctrl+Alt+, = previous tab (`.uno:NextDocumentTab` /
  `.uno:PrevDocumentTab`, Global accelerators, rebindable). Other combinations are taken:
  - Ctrl+Tab: Writer table jumps.
  - Ctrl+PgUp/PgDn: Calc sheets.
  - Ctrl+Alt+PgUp/PgDn (with or without Shift): Writer comments, hard-coded in `edtwin.cxx`.
  - Ctrl+F6: vcl.
  - Ctrl+W (CloseWin) and Ctrl+N already behave per tab.

## B. Style gallery

**Cause:** a 65 px scrolled icon view with 36 px rows, so the second row is cut off and a
scrollbar appears. Only Writer's Tabbed `notebookbar.ui` uses this control; Calc and the other
variants don't.

**Fix:**
- Exactly one row of taller previews (100×52; row 58 px plus frame = height-request 60, inside the
  ribbon slot).
- No scrollbar. The view holds one page (as many previews as fit the width), so there is no
  wheel-scroll to a half row.
- Buttons ◂ / ▸ page through the styles; ▾ opens all styles in the Styles deck of the sidebar.
- Minimum width is 2 previews. A 1485 px window shows 2; wider windows show more.

## Other items (from the coordinator)

- **Intro, descriptive and legal texts are Vietnamese in every UI language.** All verified under
  en-US and vi:
  - About description (`aboutdialog.ui`, no longer translatable).
  - "Bản phát hành này do HASON TECH cung cấp." (was "This release was supplied by %OOOVENDOR.").
  - The open-source line and contact block (already Vietnamese).
  - Start Center hint "Chào mừng đến với HST Office! / Thả tài liệu vào đây…".
  - Banner artwork and link (already Vietnamese).
  - License dialog notice: bilingual, Vietnamese first (unchanged).
  - Welcome dialog: done by the backlog agent (commit 66cda5b). I reverted my own edit there.
- **Window titles.** The Start Center and dialogs showed "HST Office 26.8".
  - The app display name is now "HST Office".
  - `%PRODUCTVERSION` in UI texts is now 1.0, e.g. "HST Office 1.0 Document Recovery".
  - The X11/GTK app name (hidden leader windows) drops the engine version from ProductKey.
  - `utl::ConfigManager::getProductVersion()` stays 26.8.1.1 (extensions, help).
  - The installer still writes `ProductKey=HST Office 26.8` in bootstraprc; that is the installer's
    area, so I left it unchanged.
- **Start Center link:** it is now a flat button, not a hyperlink, so there is no underline and the
  dot of "tại" stays visible (zoomed screenshot `30-start-center-link-zoom.png`).
- **Icons:** `scripts/brand/apply-icon-overrides.py` now runs in `build-linux.sh build()`.
  `--check`: 77 targets, 0 upstream left. The installed `res/mainapp_48_8.png` is the HST icon
  (`40-window-icon-mainapp-48.png`).
- Local tree synced with main: reversed the old sysui and vi-descriptions patches and applied the
  new ones plus `hst-copyright.patch`.

## Files and patches

- New: `patches/libreoffice/hst-document-tabs.patch`. Touches framework (new `documenttabgroup.cxx`,
  `documenttabbar.cxx`, headers; `frame`, `desktop`, `autorecovery`, `loadenv`, `layoutmanager`,
  `dispatchprovider`), `include/framework/documenttabs.hxx`, sfx2 `frame.cxx`, cui General page,
  officecfg (`Common.xcs`, `Accelerators.xcu`, `GenericCommands.xcu`) and the vi `.po` files.
- New: `hst-style-gallery.patch` (svx `stylespreview.ui`, `StylesPreviewWindow.*`, vi svx `.po`).
- New: `hst-window-title.patch` (desktop `app.cxx`, `dp_gui_service.cxx`, vcl `X11Helper.cxx`).
- Updated:
  - `hst-about.patch`: Vietnamese description and publisher line.
  - `hst-start-center-banner.patch`: flat link button, Vietnamese hint.
  - `series`: three lines added.
- Vietnamese strings ship as translated entries appended to the vi `.po` in the patches, the same
  precedent as the banner patch. Examples: "Mở trong thẻ mới", "Đóng thẻ", "Thẻ tài liệu",
  "Kiểu dáng trước/tiếp theo", "Tất cả kiểu dáng".
- Tests:
  - New in `tests/runtime/`: `hst_gui.py` (shared GUI helper), `check-document-tabs.py`,
    `check-style-gallery.py`, `check-window-title.py`, `check-vi-intro.py`.
  - `check-no-libreoffice-ui.py`: the notice needle is now found by content; the publisher line now
    comes first.
- `scripts/build-linux.sh` (icon overrides) and `README.md` (one line about tabs).

## Verification (local, final build)

- `check-document-tabs` 16/16 PASS. Screenshots `tests/output/screenshots-tabs/01–07`: Start Center,
  three tabs, switch, save query on the tab, after close, new tab, option off.
- `check-style-gallery` PASS (the analyser fails on the "before" screenshot). See `10-style-gallery-before/after`.
- `check-window-title` 10/10 PASS. `check-vi-intro` 13/13 PASS (screenshots
  `tests/output/screenshots-vi-intro/{en,vi}-0[1-4]`).
- `check-office-roundtrip` 9/9 PASS. `check-no-libreoffice-ui` PASS.
- `check-defaults`: 2 FAIL on `HelpRootURL`. This comes from the other agent's offline-help work in
  progress (`check-defaults.py` and `hst-offline-help.patch` are uncommitted in the working tree, not
  in my build). Not caused by my changes.
- `ci-quality.sh`: 20 commands, 1 failure, `apply-patches --check` on my already-patched tree.
  `hst-packaging-vendor.patch` and `hst-packaging-vi-descriptions.patch` (installer agent) change the
  same packinfo lines, so once the latter is applied the former can't reverse-apply. The full series,
  including my patches, applies cleanly to pristine sources. Needs a fix by the installer agent.
- `build-linux.sh --package`: 38 .deb in `dist/linux`. `tests/runtime/check-deb-install.sh dist/linux`
  (docker ubuntu:24.04): PASS.
- Concern: `dist/linux/hst_office1.0-debian-menus_1.0.0-1_all.deb` dates from 12:32. Since the new
  packaging patches went in, sysui builds `libreoffice26.8-debian-menus_26.8.1-1_all.deb`
  (`workdir/CustomTarget/sysui/deb`), so the HST-named menus deb in `dist/` is a stale copy. That
  is packaging naming in the installer/icon agents' area; please check.

## Limitations

- Shared display: another agent runs soffice on :97 at the same time. The tests scope X queries to
  their own soffice pid and raise their own windows before screenshots. One run of the tabs check
  stopped early once; the rerun passed.
- The tab strip sits below the ribbon, not in the title bar (that would need vcl border-window work).
- One group per process; no tab drag-out or reordering.
- Many tabs shrink to about 72 px; tabs that still don't fit are scrolled out of view, with the active
  tab kept visible. The Window menu lists all of them.
- Full-screen mode hides the strip; switching tabs while full screen is untested.
- Wayland: window position can't be set, so only size and maximized state carry over.
- A modal dialog raised by background code (macros) on a parked document may appear without a
  visible parent.
- The style gallery follows the ribbon width, so narrow windows show 2 previews.

## To verify on Windows/macOS

- Windows (clang-cl): it should compile; the code uses portable vcl/framework APIs and the only
  platform-specific file is `X11Helper.cxx` (unx only).
- Windows behaviour:
  - Hide/show of top-level windows with `SetWindowState` before show: maximized state, no flicker,
    one taskbar button.
  - Focus after a switch.
  - Owned dialogs of parked windows.
  - The style gallery: vcl IconView item sizes, since 60 px must hold a 58 px row.
  - Ctrl+Alt+. / Ctrl+Alt+, with AltGr layouts.
- macOS: same window questions; the menubar is global there.

## Unresolved questions

1. Should closing the window with the title-bar X close only the current tab (as now) or all tabs
   like a browser?
2. Should the installer write `ProductKey` without the engine version (installer agent's area)?
3. Fix for the vendor/vi-descriptions patch overlap (installer agent).

## Integration round (evening 2026-10-30)

Build: main at ffa4f9d, plus the changes below. Includes `hst-offline-help`, `hst-copyright`,
`hst-packaging-macos-dmg`, the update check (c5e03b4, 69c35a2), the backlog work (NĐ 30 wizard,
welcome dialog, tip images, 86 translation fixes) and the icon overrides.
`apply-patches.sh --check`: every patch already applied. The whole series also applies cleanly to
pristine sources.

**Owner decisions implemented**
- **Title-bar X closes all tabs.** Order:
  1. The other tabs first; each modified one is shown, then its save query appears.
  2. The clicked tab last (upstream `.uno:CloseFrame`).
  3. Cancel on any query keeps that tab and the remaining ones.
  - The × on a tab still closes only that tab.
- **18 HST templates ship in the HST extension**, which works the same on every OS with no
  installer change.
  - Location: `template/hst-van-ban|hst-bang-tinh|hst-trinh-chieu`.
  - Group names come from `groupuinames.xml`: "HST — Văn bản hành chính / Bảng tính / Trình chiếu".
  - `Paths.xcu` adds `%origin%/template`.
  - Size: the `.oxt` grows by about 54 KB; about 350 KB more when installed.

**Defects found and fixed**
- A full-screen slide show runs in its own frame, and that frame joined the tab group and parked the
  Impress tab. Presentation and full-screen windows are now excluded.
- UNO exceptions from frames being disposed could escape the tab group's VCL callbacks. All of them
  are now guarded.
- After tab switches, the classic menubar appeared above the Tabbed ribbon. Fixes:
  - a parked tab keeps its menubar attached;
  - the notebookbar applies its menubar mode to the frame it sets up;
  - `SfxNotebookBar::CloseMethod` only restores the menubar of its own window.
  - Result: switching between Writer tabs, opening a new tab, and Writer→Calc→Impress loads show no
    menubar.
  - Residual: a classic menubar can still appear on some Calc/Impress tabs after cross-module
    switches (GTK3 native menubar). Re-hiding it by toggling the menubar worked visually but raised
    crashes to 3 of 10 runs, so it was removed. See the open questions below.

**Upstream GTK3 crash (not caused by tabs)**
- Trigger: under Xvfb, loading a document right after closing a hidden one crashes in
  `GtkSalMenu::CreateMenuBarWidget` / `SwView::IsPasteAllowed`, inside a nested
  `gtk_clipboard_wait_for_targets` loop.
- It also crashes with tabs disabled (2 of 8 runs) and with the final build (1 of 6 runs).
- The tabs test now writes its ODT fixture directly instead of saving a hidden document.

**QA (final build, fresh profiles, Xvfb :97)**

| Check | Result |
|---|---|
| check-defaults | 18/18; F1 and Help → Trợ giúp open `…/hst-vietnamese-tools/help/index.html` (seen through a logging `xdg-open`) |
| check-office-roundtrip | 9/9 |
| check-no-libreoffice-ui | PASS (includes the guide) |
| check-vi-intro | PASS (12 checks); one earlier run, made while packaging ran in parallel, missed the About window |
| check-window-title | 9/9 |
| check-document-tabs | 29/29, run twice |
| check-style-gallery | 4/4 |
| check-template-manager (new) | 7/7 |
| check-update-notify | 11/11 |
| NĐ 30 wizard, welcome dialog, Vietnamese tip-of-the-day image | open; screenshots `tests/output/screenshots-integration/01–03` |
| Translation spot checks (UI labels) | 5/5: Lưu thành…, Giãn cách bộ khung, Cập nhật bảng tổng hợp (checked in `registry_vi.xcd`), Bảng tổng hợp, Chèn trang chiếu |
| `ci-quality.sh` | 24 commands, 0 failures |
| `--package` | 38 .deb; the menus deb is a fresh `hst_office1.0-debian-menus` (stale libreoffice-named outputs removed) |
| `check-deb-install.sh dist/linux` (docker) | PASS |

`check-document-tabs` details:
- Original 16 checks.
- Title-bar X with 2 modified documents: 2 queries; Cancel on the second keeps that tab.
- Mixed Writer/Calc/Impress group: each tab shows its window and ribbon, with distinct ribbon colours.
- Slide show from the Impress tab: Esc returns to the intact group, and no presenter console opens on
  one display.
- Title-bar X with 3 modified documents: 3 queries, all closed.
- Option off.
- Screenshots: `tests/output/screenshots-tabs/01–14`.

**Open questions**
1. Residual classic menubar on some cross-module tab switches under GTK3. This needs a fix in vcl's
   GTK native menubar or sfx2's menubar bookkeeping (`SfxNotebookBar::ShowMenubar` uses
   `SfxViewFrame::Current()`). Please check it on a real desktop and on Windows.
2. The upstream GTK3 clipboard/menubar crash. Worth a check on a real desktop, where a clipboard
   manager answers quickly.
3. The bootstraprc product key question is unchanged (owner).
