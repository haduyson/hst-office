# opus-04: macOS right-click latency, source analysis + measurement kit

Status: DONE_WITH_CONCERNS. No Mac available: every macOS cause below is a **hypothesis** from source reading; the Swift tool was **never compiled** (no swiftc on Linux). Tree: /home/office/upstream/libreoffice (26.8.1.1).

## A. Source analysis (26.8.1.1, read-only)

### Tree checks
- gerrit 211382 (`popUpContextMenu`): **absent**. `grep popUpContextMenu vcl/osx` = none; salmenu.cxx:301-345 still uses `NSPopUpButtonCell` + `performClickWithFrame:inView:` (salmenu.cxx:330-337). Owner on 26.8.2+ would run a different path; ask the owner's exact version.
- gerrit 208182 (Skia GPU opt-in): **present in effect**. `ForceSkiaGPU` default `false` (officecfg/.../Common.xcs:276-282); `SkiaHelper.cxx:245-273` returns `RenderRaster` unless `SAL_SKIA=metal` or ForceSkiaGPU. Native popup is never painted by Skia, so Metal/raster is unlikely to matter (keep as A/B cell).

### Trace right-click -> menu pixels (same for Writer/Calc/Impress unless noted)
1. `-[SalFrameView rightMouseDown:]` vcl/osx/salframeview.mm:1428 -> `sendMouseEventToFrame` :1240 (cheap; may call `getMouseContainerFrame` only if pointer outside frame).
2. VCL `ImplHandleMouse` vcl/source/window/winproc.cxx:804-826: ContextMenu command is fired on MOUSEBUTTONDOWN (`ImplCallCommand(CommandEventId::ContextMenu)`), nested inside the NSEvent handler.
3. Per-app handler, all converge on `SfxDispatcher::ExecutePopup`:
   - Writer `SwEditWin::Command` sw/source/uibase/docvw/edtwin.cxx:5809 -> **first** `SwView::ExecSpellPopup` :5878 (viewling.cxx:586; AutoSpell_ :621, GetCorrection :633, GetGrammarCorrection :641) else `ExecutePopup`.
   - Calc `ScGridWindow::Command` sc/source/ui/view/gridwin.cxx:3294/3408 -> :3634.
   - Impress `sd::DrawViewShell::Command` sd/source/ui/view/drviews4.cxx:562 -> :812/:841.
4. `SfxDispatcher::ExecutePopup(name,...)` sfx2/source/control/dispatch.cxx:1873-1941: creates a **new** `ResourceMenuController` + `VCLXPopupMenu` every time (:1876-1887), `TryContextMenuInterception` (:1931; viewsh.cxx:3901 builds an UNO ActionTriggerContainer of all items via `CreateActionTriggerContainerFromMenu` even with zero interceptors), then `xPopupMenu->execute` (:1936) -> `PopupMenu::Execute`.
5. `ResourceMenuController::updatePopupMenu` framework/source/uielement/resourcemenucontroller.cxx:131-228: module/config manager lookups, `MenuBarManager::FillMenu` (menubarmanager.cxx:1309) builds every item (Writer text.xml 66 ids, Calc cell.xml ~40, Impress draw.xml ~32 items + submenus).
6. `PopupMenu::ImplExecute` vcl/source/window/menu.cxx:2839: `Activate()` :2884 (fires `MenuActivate` -> `ResourceMenuController::itemActivated` resourcemenucontroller.cxx:276 creates a fresh `MenuBarManager`, then `MenuBarManager::Activate`), then **always** `VclPtrInstance<MenuFloatingWindow>(WB_SYSTEMWINDOW)` :2922 (a real `AquaSalFrame`: NSWindow+NSView, salframe.cxx:168 `initWindowAndView`) and `ImplCalcSize(*pWin)` :2938 (text measurement of every item), `SetOutputSizePixel`, then `Run` :3004 -> `AquaSalMenu::ShowNativePopupMenu`. On the native path the floating window is only used for geometry (salmenu.cxx:312-326); it is never shown.
7. `MenuBarManager::Activate` menubarmanager.cxx:553-740 (synchronous, main thread, SolarMutex): per item `queryDispatch` :649, `addStatusListener` :693 (triggers `GetState` of the slot), then immediately `removeStatusListener` for context menus (:696-698); recurses into every popup-menu-controller submenu (`pThisPopup->Activate()/Deactivate()` :667-672, :705-710 -> Language, Paste Special, Styles, etc. controllers). Images: `FillMenuImages` :591 runs only if `m_bRetrieveImages || showImages changed || icon theme changed`; for a freshly constructed manager those flags are equal (ctor :95-100, :948), so **static reading says per-item NSImage creation may not occur for context menus** - sample must confirm (see H5).
8. `AquaSalMenu::ShowNativePopupMenu` salmenu.cxx:301-345: `[NSPopUpButtonCell performClickWithFrame:inView:]` runs a nested AppKit tracking loop; `[AquaA11yWrapper setPopupMenuOpen: YES/NO]` :334-337. The `SalNSMenu` delegate (`setDelegate` salmenu.cxx:239) fires `menuNeedsUpdate:` (salnsmenu.mm:92-166): for popups this does a second `Activate()/Deactivate()` (:148-150) and a hide-disabled loop; `setAutoenablesItems:YES` (salmenu.cxx:246) makes AppKit call `validateMenuItem:` (salnsmenu.mm:315) per item (takes SolarMutex).

### Status queries that can be slow / macOS-specific
- Clipboard (Paste, Paste Special, Paste Unformatted; every module): Writer `SwView::IsPasteAllowed` sw/source/uibase/uiview/view.cxx:1949 recomputes `CreateFromSystemClipboard` whenever the paste *destination* changes (cached otherwise, with a clipboard listener); Calc `ScCellShell::GetClipState` sc/source/ui/view/cellsh.cxx:615 queries once then caches via listener. macOS path: `AquaClipboard::getContents` vcl/osx/clipboard.cxx:139 -> `applicationDidBecomeActive` :230 (`[pasteboard changeCount]`) -> `new OSXTransferable` (OSXTransferable.cxx:88) -> `initClipboardItemList` :162 (`[mPasteboard types]`, synchronous IPC to pboard; may block with Universal Clipboard/Continuity items or clipboard managers). Real but cached after first query: more likely a first-menu / after-copy cost than every-click.
- Font Size (tdf#146507): `FontSizeMenuController::fillPopupMenu` creates an info `Printer` (fontsizemenucontroller.cxx:146), but `.uno:FontHeight` appears **only in `formrichtext.xml`** popups (grep of sw/sc/sd popupmenu dirs) -> **not** in normal text/cell/shape menus. Excluded as main cause.
- Writer-only: `ExecSpellPopup` (autospell on), Language submenus (`langselectionmenucontroller.cxx:130-`), `.uno:ThesaurusFromContext` (Controller.xcu:190). Owner sees the delay in Calc/Impress too -> cannot be the sole cause.
- Accessibility: popup flag in step 8; a11y listeners run on every `Menu::Insert*`/window creation (`ImplCallEventListeners`) if an AX client is attached.

### Ranked hypotheses (all UNVERIFIED on macOS; Linux data bounds the cross-platform part)
Linux calibration (run C below): the shared dispatch/Activate/FillMenu path costs median 14-19 ms, p95 33-37 ms warm on x86 (`gen` VCL plugin, 24.2). A multi-hundred-ms every-click delay therefore needs a mac-specific cost.

| # | Hypothesis | Why it fits "every click, all 3 modules" | Evidence | `sample`/Instruments symbols to look for |
|---|---|---|---|---|
| H1 | Native-popup machinery per click: `MenuFloatingWindow` NSWindow creation + `ImplCalcSize` + building ~40-70 `NSMenuItem`s + `NSPopUpButtonCell` tracking setup (+ `validateMenuItem:` per item under SolarMutex) | Shared VCL path, absent on Linux (no SalMenu popup) | menu.cxx:2922-2938, 3004; salmenu.cxx:330-337; salnsmenu.mm:92,315 | `PopupMenu::ImplExecute`, `MenuFloatingWindow::MenuFloatingWindow`, `AquaSalFrame::initWindowAndView`, `-[NSWindow initWithContentRect:...]`, `Menu::ImplCalcSize`, `OutputDevice::GetTextWidth`/CoreText, `AquaSalMenu::InsertItem`, `-[NSPopUpButtonCell performClickWithFrame:inView:]`, `-[NSMenu _popUpContextMenu...]`/`-[NSMenuTrackingSession ...]`, `-[SalNSMenuItem validateMenuItem:]` |
| H2 | Synchronous status storm in `MenuBarManager::Activate` (queryDispatch+addStatusListener per item and per submenu controller) with a slow item (clipboard, printer, dictionary) | Same code on all modules; slow only if some `GetState` is slow on mac | menubarmanager.cxx:553-740 | `framework::MenuBarManager::Activate`, `SfxOfficeDispatch::addStatusListener`, `SfxDispatcher::...GetState`/`SfxBindings::...`, `TransferableDataHelper::CreateFromSystemClipboard`, `AquaClipboard::getContents`, `-[NSPasteboard types]`, `-[NSPasteboard changeCount]` |
| H3 | Accessibility / window-manager / clipboard-manager client attached (VoiceOver, BetterTouchTool, Moom, Rectangle, Raycast, Maccy...) | Cost scales with window/menu creation, every click | salmenu.cxx:334-337; tdf#57071 c2 | `AquaA11yWrapper`, `a11y`, `NSAccessibility*`, `_AXUIElement...`, `CGSEventTap...` in main thread, `mach_msg` waits in `-[NSEvent ...]`; compare run with these quit |
| H4 | Per-item `NSImage` creation via `lockFocusFlipped:` if icons are set (conditions in menubarmanager.cxx:584-592 or ActionTrigger path) | Shared, mac-only (`CreateNSImage` only used by native menus) | salmenu.cxx:682-690; salinst.cxx:1050-1074 | `CreateNSImage`, `-[NSImage lockFocusFlipped:]`, `SkiaHelper::createCGImage`, `AquaSalMenu::SetItemImage`, `vcl::CommandInfoProvider::GetImageForCommand` |
| H5 | `TryContextMenuInterception` UNO container + `ResourceMenuController` rebuild per click | Shared; also on Linux (so bounded ~tens of ms) | dispatch.cxx:1873-1941; viewsh.cxx:3901 | `CreateActionTriggerContainerFromMenu`, `ResourceMenuController::updatePopupMenu`, `MenuBarManager::FillMenu` |
| H6 | Writer-only: `ExecSpellPopup` / language submenus / NSSpellChecker | Not all modules | viewling.cxx:586-641 | `SwView::ExecSpellPopup`, `SwTextFrame::AutoSpell_`, `MacOSXSpell`, `-[NSSpellChecker ...]` |
| H7 | Skia Metal init / GPU | Unlikely: raster default, popup not Skia-painted | SkiaHelper.cxx:245-273 | `skwindow::...MetalWindowContext`, `MTLCreateSystemDefaultDevice` (only if owner enabled GPU) |
| -- | `popUpContextMenu` change | Not in tree (26.8.2+ only) | no match in vcl/osx | n/a here; owner version question |

Reading the owner's `sample`: find the main thread ("DispatchQueue_1: com.apple.main-thread"), the call chain under `-[SalFrameView rightMouseDown:]` -> `ImplCallCommand` -> `SfxDispatcher::ExecutePopup`. If the large share sits under `PopupMenu::Execute` -> `Activate`/`MenuBarManager::Activate` => H2; under `ImplExecute` before `ShowNativePopupMenu` outside Activate (window/size/items) => H1/H4; under `-[NSCell performClickWithFrame:inView:]` but in AppKit frames only => H1/H3 (AppKit menu setup, a11y/event taps); in `mach_msg`/`__psynch` waits => IPC/lock (pasteboard, a11y, SolarMutex). Mostly-idle main thread with high latency => an external agent (event tap, compositor).

### Fix candidates (diff sketches; do NOT apply before `sample` data; no patches/ files created)
1. **Diagnostic first (recommended)**: stage timings with `os_signpost` (Instruments "Points of Interest") or `SAL_INFO`/`tools::Time` in `PopupMenu::ImplExecute` (menu.cxx:2884 after `Activate()`, :2922 after `MenuFloatingWindow`, :2938 after `ImplCalcSize`, before/after :3004) and `SfxDispatcher::ExecutePopup` (dispatch.cxx:1873 start, :1931 interception, :1936 execute). Splits H1/H2/H5 in one owner run.
2. If `lockFocusFlipped` dominates (H4), `vcl/osx/salinst.cxx:1050-1074`:
   ```
   -    NSImage* pImage = [[NSImage alloc] initWithSize: NSMakeSize(w, h)];
   -    [pImage lockFocusFlipped:YES]; ... CGContextDrawImage(...); [pImage unlockFocus];
   +    NSImage* pImage = [[NSImage alloc] initWithCGImage: xImage size: NSMakeSize(w, h)];
   ```
   (lockFocus is deprecated since macOS 14; verify orientation/Retina visually.)
3. If pasteboard IPC dominates (H2): cache the flavor list per `changeCount` in `AquaClipboard::getContents` (vcl/osx/clipboard.cxx:139-158):
   ```
   +    if (mxCachedTransferable.is() && mnCachedChangeCount == [mPasteboard changeCount]) return mxCachedTransferable;
        return new OSXTransferable(...);   // store result + changeCount
   ```
   Must keep ownership semantics (`mXClipboardContent` shortcut) and invalidate in `applicationDidBecomeActive`/`setContents`.
4. If window creation + sizing dominates (H1): avoid building the unused `MenuFloatingWindow` text layout on native path, e.g. in `PopupMenu::ImplExecute` skip `ImplCalcSize(*pWin)` (menu.cxx:2938) when `ImplGetSalMenu()` can show natively and size is only needed for `ImplCalcPos` (needs a cheap estimate or lazy size); risky for geometry - only with data.
5. If a11y/event-tap clients dominate (H3): no code fix; document in HST release notes; test `AquaA11yWrapper setPopupMenuOpen` impact by A/B with those apps quit.
6. Do not backport 211014; revert-only option for 211382 if the owner's slow build is >= 26.8.2.

## B. macOS kit (owner runs; UNVERIFIED on Mac)
Files: `scripts/perf/macos-context-menu.swift` (199 lines), `run-context-menu.py` (+ `context_menu_drivers.py`, `context_menu_env.py`, `context_menu_fixtures.py`), `context-menu-matrix.json`, `analyze-context-menu.py` (+ `context_menu_metrics.py`), docs/CONTEXT_MENU_PERFORMANCE.md (Vietnamese owner guide).
- Swift: finds soffice main window via `CGWindowListCopyWindowInfo` (owner pid, layer 0), posts mouseMoved + rightMouseDown (`CGEvent.post` .cghidEventTap), polls for a new window of that pid with layer >= 101 (`kCGPopUpMenuWindowLevel`), t0 = mach clock before posting, Esc to close, waits for window gone, rightMouseUp. `--manual`: listen-only `CGEvent.tapCreate` for right/ctrl-left mouse down, t0 = callback receipt. JSON per trial: ms/timeout/layer/bounds. No AX API.
- Permissions (stated truthfully): synthetic mode needs **Accessibility** for Terminal (CGEvent posting to the HID tap; documented behavior of comparable tools, not verified here; tool checks `AXIsProcessTrusted` and exits 3 with instructions); `--manual` needs **Input Monitoring**; **Screen Recording not needed** (only owner/layer/bounds read). Unverified assumptions: layer 101 for NSPopUpButtonCell menu windows; window-list visibility != pixels drawn; `NSRunningApplication.activate` behavior on newest macOS.
- Runner: `--platform macos --app <.app> --preset owner-quick --sample --output ...`; clean profile per launch (+ `IsSpellAuto` toggle, FirstRun/TipOfTheDay off), `profile=user` = copy only, `SAL_SKIA=raster` cells, cold = fresh process per trial, warm = one warm-up + N; `sample PID 5 1 -file` runs with 3 extra trials (separate from timing); env.json: sw_vers, hw.model, uname -m, LO version (Info.plist), watched a11y/window-manager/clipboard apps from `ps`.
- Analyzer: median/p90/p95/max/timeouts per cell, baseline-vs-candidate (fail on missing baseline/cell, target breach, regression only if both > percent and > floor), `sample` top frames (self-time section, call-graph fallback) + suspect-symbol flagging (symbols in `SUSPECT_SYMBOLS`). The `sample` parser was tested only on a hand-written snippet in the documented layout, not real `sample` output.

## C. Linux parity harness: validated
- `run-context-menu.py --platform linux`: Xvfb (`--start-xvfb`, refuses an existing display, no auto-increment) + ctypes libX11/XTest (`context_menu_x11.py`): XTest right-click, poll root children for a new viewable window, Escape to dismiss. xdotool/xwininfo not needed (ctypes is precise in-process; installed but unused).
- System LibreOffice 24.2 is Writer-only (no calc/impress/gtk3 plugin). To validate all three modules **without touching the system**, I downloaded (apt-get download) calc/impress/draw + uiconfig debs, extracted and overlaid a copy at `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/o4/lo-full` (registry symlink replaced, `fundamentalrc` BRAND_BASE_DIR=${ORIGIN}/..). Reusable by others; delete when done.
- Command: `python3 scripts/perf/run-context-menu.py --platform linux --app <scratchpad>/o4/lo-full/program/soffice --preset linux-parity --start-xvfb --display :98 --output tests/output/perf/linux-system-24.2` (default 20 warm, 5 cold). Raw: `tests/output/perf/linux-system-24.2/*.json`, `summary.txt`, `env.json`. Xvfb :98 and all soffice processes stopped after.

| cell (ms) | n | median | p90 | p95 | max |
|---|---|---|---|---|---|
| writer warm | 20 | 15.9 | 35.5 | 37.2 | 40.0 |
| calc warm | 20 | 13.8 | 30.9 | 34.8 | 45.6 |
| impress warm | 20 | 19.4 | 30.5 | 32.7 | 52.7 |
| writer cold | 5 | 37.9 | 75.4 | 75.4 | 75.4 |
| calc cold | 5 | 41.0 | 56.4 | 56.4 | 56.4 |
| impress cold | 5 | 335.8 | 402.4 | 402.4 | 402.4 |

0 timeouts. Interpretation: warm shared path is cheap on Linux; first right-click in Impress is ~300+ ms even on Linux (init cost: first-use cost in the sd module), which would trip the provisional cold p95 400 ms gate (402.4 on n=5). Limits: gen plugin (not gtk3), Xvfb without compositor, 24.2 not 26.8, n=5 cold, popup window appearance != painted pixels. `analyze --baseline X --candidate X` exercised: reported the cold-impress target breach; missing baseline exits 2.

## D. Tests / fixtures
- `tests/perf/test_context_menu_metrics.py`: 14 tests (percentile/median/summary, regression both-thresholds rule, missing baseline/cell, targets, timeouts, load_runs, `sample` parsing both paths, preset expansion counts, fixtures == manifest, profile autospell). `python3 -m unittest discover -s tests/perf -p 'test_context_menu_metrics.py'` -> OK (14).
- `tests/fixtures/perf/{context-menu-writer.fodt,calc.fods,impress.fodp,manifest.json}`: generated by `scripts/perf/context_menu_fixtures.py` (flat ODF, synthetic text incl. deliberate misspellings, sha256 manifest, no private data). All three loaded by LO 24.2 headless (pdf export OK).

## Files created (all within ownership)
scripts/perf/{macos-context-menu.swift, run-context-menu.py, analyze-context-menu.py, context-menu-matrix.json, context_menu_{drivers,env,fixtures,metrics,x11}.py}; tests/perf/test_context_menu_metrics.py; tests/fixtures/perf/*; tests/output/perf/linux-system-24.2/*; docs/CONTEXT_MENU_PERFORMANCE.md (Vietnamese; owner guide + limits + Linux results). No patches/ files. Per-file <=199 lines. SPDX AGPL-3.0-only headers.

## Unresolved questions / concerns
1. Swift tool uncompiled/untested; first owner run may need fixes (send compiler output). Layer-101 assumption and Accessibility requirement unverified.
2. Owner's exact macOS, LO version (26.8.1 vs 26.8.2+ affects popUpContextMenu), input device, running a11y/WM/clipboard tools.
3. H4 static reading: with a fresh MenuBarManager `FillMenuImages` seems not to run, so context-menu icons come from elsewhere or are absent; `sample` frames `CreateNSImage` decide.
4. Phase file targets use xvfb display :99 and `--app upstream/.../instdir` (not yet built); the runner supports it (`--display :99 --vcl gtk3`, needs a gtk3 build) but baseline `linux-upstream` vs `linux-hst` comparisons await the coordinator's build.
5. `analyze` cold-p95 gate is sensitive to small n (5); phase asks for 30 cold / 100 warm (`--cold 30 --warm 100`).
6. Impress cold ~336 ms on Linux: worth profiling on the 26.8 build (separate from the macOS issue).

Status: DONE_WITH_CONCERNS
Summary: Source trace and ranked hypotheses delivered, owner kit (Swift, runner, analyzer, matrix, Vietnamese guide) and tests written, Linux harness validated on 24.2 for all three modules; macOS tool untested (no Mac/swiftc).
