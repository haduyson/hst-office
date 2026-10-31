# beta.3: residual classic menubar and GTK3 menubar/clipboard crash

Date 2026-10-31. Tree: LibreOffice 26.8.1.1 + HST series, GTK3 under Xvfb :96 (own display, stopped at the end).
Patch: `patches/libreoffice/hst-gtk-menubar-fix.patch` (new, last in `series`; vcl only).
`hst-document-tabs.patch` is unchanged.

## 1. Residual classic menubar

### Root cause (proven)
`MenuBarWindow::SetMenu()` (vcl/source/window/menubarwindow.cxx:194) called
`SalMenu::ShowMenuBar(true)` unconditionally. On GTK3 that creates the GtkMenuBar widget.
`MenuBar::SetDisplayable(false)` (what the Tabbed ribbon uses to hide the menubar) removes the widget
only when the flag changes (`menu.cxx:2463`). So whenever a menubar with `mbDisplayable == false` is
attached to a window again, a widget is created that nothing removes: the flag says hidden, the
widget is shown. The later `SetDisplayable(false)` from `LayoutManager` is a no-op.

Deterministic repro, no tabs, no timing (`tests/output/menubar/det.py`): tabs OFF, Writer with ribbon,
`getContainerWindow().setVisible(false)` then `setVisible(true)` -> classic menubar above the ribbon.
bpftrace (uprobes, low overhead) on the baseline:

```
LM_hide  -> SetDisplayable(0) -> GTK_ShowMenuBar(vis=0)      hidden at load
SetMenuBar(win, nil)          -> GTK_ShowMenuBar(vis=0)      window hidden (detach)
SetMenuBar(win, bar) -> MenuBarWindow_SetMenu_ENTER -> GTK_ShowMenuBar(vis=1) -> LEAVE
SetDisplayable(val=0)  (no state change, no GTK_ShowMenuBar)  -> menubar stays visible
```

Tab flow: the same attach happens when a window is shown after a non-park hide, and (race) when the
hide arrives while `SetMenu()` is still inside its nested main loop (it lasts seconds under Xvfb:
3 to 6.6 s per menubar measured), so the outer unconditional show wins. Reproduced with short gaps
between loads/switches (0.3 s): Impress/Calc menubar visible from the first load and persistent.

### Fix
`ShowMenuBar(m_pMenu->IsDisplayable())`. One line plus comment. The widget now follows the flag by
construction; the previous toggling attempts (which raised the crash rate) are not needed. The earlier
framework/sfx2 changes of the tab patch stay (parked tab keeps its menubar, `SetDisplayable(m_bMenuVisible)`).

### Windows / macOS / Qt reasoning (not run)
- Windows (VCL win backend): `WinSalMenu::VisibleMenuBar()` returns false (vcl/win/window/salmenu.cxx:118):
  the menubar is a VCL-drawn `MenuBarWindow`, never a native bar. `WinSalMenu` does not override
  `ShowMenuBar` (base `SalMenu::ShowMenuBar` is empty). Hidden = `mbDisplayable` only
  (`MenuBar::ImplCreate` sets height 0 if `!IsDisplayable()`, `SetDisplayable` calls `LayoutChanged`),
  so flag and widget cannot diverge. The changed line is a call to an empty virtual: no behaviour
  change. The GTK-only files are not compiled on Windows. The framework/sfx2 parts use only portable APIs.
- macOS: `AquaSalMenu` does not override `ShowMenuBar` either: no change.
- Qt: `QtMenu::ShowMenuBar(bVisible)` calls `setVisible`, so it now also honours the flag.
- Real desktop (GTK3 with window manager): not available here. The deterministic path does not depend on
  Xvfb (hide/show of a window); the WM only maps/unmaps the same GtkWindow.

### Before / after
| Test | Before | After |
|---|---|---|
| hide + show window, tabs off (det.py, screenshot) | menubar shown | hidden |
| new check "window hidden and shown again keeps the menubar hidden" in check-document-tabs | FAIL | PASS |
| module-switch repro (`fast.py`: Writer, Calc, Impress, 3x NextDocumentTab, gap 0.3 s, screenshots, topmost window) | 1 of 6 sessions persistent (Impress); earlier unfiltered runs 3 of 7 | 0 of 12 persistent; 1 transient at n=0 (right after the load, before the async hide) |
| same with 2 s gaps | 0 of 5 | not repeated |

The race needs fast loads; at 2 s gaps the baseline did not show it, so the stochastic number is the weaker
evidence and the deterministic repro the stronger one. Screenshots: `tests/output/menubar/{det,fast-*}`.

## 2. Rare GTK3 crash

### Backtraces (gdb attach, reproduced 3 of 3 on baseline)
Harness (`tests/output/menubar/crash.py`, MODE=store): from the UNO API (Python client thread):
load Hidden Writer, `storeToURL`, `close(true)`, then load the stored file; tabs OFF.
Main thread, baseline:

```
GtkSalData::Yield -> Scheduler -> SfxBindings::NextJob -> SfxDispatcher::SetMenu_Impl
 -> LayoutManager::createElement(menubar) -> SystemWindow::SetMenuBar -> MenuBarWindow::SetMenu
 -> GtkSalMenu::SetFrame -> ActivateAllSubmenus -> MenuBarManager::Activate -> QueryState(.uno:Paste)
 -> SwView::IsPasteAllowed -> gtk_clipboard_wait_for_targets -> g_main_loop_run   (nested loop)
   -> Scheduler idle -> GtkSalMenu::SetFrame (MenuBarHierarchyChangeHandler) -> CreateMenuBarWidget -> SIGSEGV
```
Order from a gdb trace of `~GtkSalFrame` / `GtkSalMenu::SetFrame`: `~GtkSalMenu` of the hidden
document's submenus, `~GtkSalFrame(frame F)`, then `SetFrame(menu M, F)` with M the document's
menubar GtkSalMenu, which was not destroyed. Gtk assertions before the crash
(`gtk_widget_get_window`, `gtk_grid_attach: GTK_IS_GRID`) confirm a dead frame.

Cause chain:
1. The hidden document's menubar is built on the main thread (NextJob timer): hundreds of status queries,
   including a synchronous GTK clipboard round trip in a nested main loop. The nested loop lets the
   GDK lock (= SolarMutex) go, so the UNO client thread runs.
2. That thread closes the document: the frame and its `GtkSalFrame` are destroyed while the menubar object
   still lives (held by the layout manager / UNO references).
3. `GtkSalMenu` keeps a raw `mpFrame`; its HIGHEST-priority update idle (`maUpdateMenuBarIdle`) later
   calls `SetFrame(mpFrame)` on the destroyed frame.
With a settle time of 8 s before `store`/`close` (menubar creation finished) 0 of 4 sessions crashed
(and 0 of 13 without store), so the trigger is "document closed while its own menubar is being built".

### Fix (vcl GTK3, small and safe)
`~GtkSalFrame` calls the new `GtkSalMenu::DetachFromFrame()` (stop the update idle, destroy the widget, clear
`mpFrame`); `CreateMenuBarWidget` returns without a frame. It removes the dangling-frame use proven above.

### Result and what remains
Baseline: 3 of 3 sessions crash, all in `CreateMenuBarWidget` (this backtrace).
After the fix: 4 of 4 sessions still crash in this harness, now at the next victim of the same race:
`SwFEShell::GetObjCntTypeOfSelection` <- `SwTransferable::IsPaste` <- `SwView::IsPasteAllowed`, back in the
same status query: when the nested loop returns, the Writer shell of the closed document is gone. That is
sw/sfx lifetime against a thread that closes a document mid-query: no small safe fix (not vcl, not HST code).
So the fix removes one proven use-after-free but does not make this harness pass; no increase of the crash rate.

### Upstream-only? Xvfb-only? (decision)
- Not HST code. Not caused by the tabs (reproduced with tabs OFF).
- Not Xvfb-only: the mechanism (nested loop in `gtk_clipboard_wait_for_*` releases the GDK/Solar lock while a menubar is
  built, plus a second thread that closes the document) exists on any GTK3 desktop. In interactive use
  all VCL work is on the main thread, so nobody can close the document inside the nested loop: not reachable
  from GUI actions alone. It is reachable when a UNO client or extension thread opens/closes documents (python-uno
  scripts, automation, the tests here). Xvfb widens the window (menubar creation took seconds here; on a desktop a
  clipboard owner answers in ms), which is why it shows up 2 of 8 in tests and is rare for users.
- Real desktop: not run here; no desktop with a clipboard manager was available.
- Mitigation for tests: do not close/open documents from the client while a new window is still being built
  (the tabs test writes its fixture directly and waits). Optional follow-up for upstream: do not call the
  synchronous clipboard check from menubar activation; use the cached Paste state.

## Verification (final build)
- `check-document-tabs`: 33/33, exit 0 in 4 runs (3 plus 1 after restoring from the baseline experiment).
  New: per mixed tab "no classic menubar above the ribbon" (3 checks) and "window hidden and shown again keeps the
  menubar hidden" (screenshot `15-window-reshown.png`). Baseline: the last one FAILs.
- `check-defaults` 0 failures; `check-window-title` exit 0; `check-template-manager` exit 0;
  `check-no-libreoffice-ui` exit 0.
- `check-style-gallery`: first run failed "several style previews shown" (gallery not yet populated, a timing flake under
  load; screenshot shows an empty gallery); rerun 4/4 PASS. Unrelated to the menubar.
- `scripts/ci-quality.sh`: 25 commands, 0 failures. `scripts/apply-patches.sh --check`: all patches applied.
- Series on pristine sources: applied the full series in order to the pristine files from the cached tarball:
  all code hunks apply (framework, sfx2, vcl files identical to the tree). Hunks for `translations/` and
  `dictionaries/` cannot be checked (not in the code tarball), as in the earlier verification.
- Build: incremental `make Library_merged Library_vclplug_gtk3` as hstbuild only. Two extra rebuilds for the
  baseline experiment (sources reverted then restored byte for byte, compared with `cmp`).

## Files
- New `patches/libreoffice/hst-gtk-menubar-fix.patch` (menubarwindow.cxx, gtksalmenu.hxx/.cxx, gtkframe.cxx), added to `series`.
- `tests/runtime/check-document-tabs.py` (menubar checks), `tests/runtime/hst_gui.py` (`classic_menubar_visible`).
- Repro and trace tools (not committed, `tests/output/menubar/`): `det.py`, `fast.py`, `crash.py`, `m*.bt`, `*.gdb`.
- `docs/BACKLOG.md` beta.3 items 2 and 3 can be updated by the owner of that file; not touched.

## Coordinator follow-ups (same round)

1. Start Center tab label in vi: the source string is already translated ("Trang bắt đầu", `STR_DOCTAB_START` in
   `hst-document-tabs.patch`; the same term the glossary notes and the project use for the Start Center). The UI showed
   English because `instdir/.../fwk.mo` was stale (built 10-29; the gbuild MO target has no dependency on the `.po`).
   Rebuilt `fwk`, `cui`, `svx` vi `.mo` (cui/svx were stale too; vcl and basctl `.mo` are also older than their `.po`,
   not rebuilt: not mine). No source change; a clean build is not affected. Unrelated to the term question: sfx2 calls it
   "Trung tâm khởi động" only for the quickstarter menu entry.
2. FLO-02 (Quit continues after Cancel): `framework/source/services/desktop.cxx`, `Desktop::impl_closeFrames`
   (line ~1682): on `suspend(true)` returning false it does `if (m_bSession) break; else continue;`. That is upstream
   behaviour (every document is asked). Fix if the owner agrees: replace by `break;` (stop at the first Cancel, like the
   title-bar X). Risk low: terminate is vetoed anyway (`bFramesClosed` false), frames already closed stay closed as
   today, only the later prompts disappear; applies to every caller of `terminate()` (Ctrl+Q, File > Exit, update restart).
   Not applied. Edit goes into `hst-document-tabs.patch` (desktop.cxx section already exists), no rebuild beyond framework.

## Unresolved questions
1. A real desktop (with WM and clipboard manager) and Windows were not available; the Windows argument is code reading.
2. Should upstream-style crash B (sw/sfx lifetime) be filed or worked around by deferring the clipboard check in
   menubar activation? Needs a product decision; left alone.
3. During this work another agent relinked `libmergedlo.so` twice and one test run hit the missing library; rerun fixed it.
   The `:95` Xvfb I started for parallel crash runs exited by itself (server reset after its last client); `:96` was stopped at the end.

Status: DONE_WITH_CONCERNS
Summary: Residual menubar root cause proven (MenuBarWindow::SetMenu shows the GTK menubar regardless of mbDisplayable) and fixed in vcl; crash backtraced to a dangling GtkSalFrame pointer in GtkSalMenu (fixed, small) followed by a cross-thread document close race inside the GTK clipboard nested loop (not fixable safely; upstream/UNO-thread only, not reachable from pure GUI use).
Concerns/Blockers: crash harness still crashes after the fix at the next victim (Writer shell); no real desktop or Windows run; statistical menubar numbers are small, the deterministic repro and new test carry the proof.
