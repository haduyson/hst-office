# Phase 04 — Right-click delay investigation, fix and measurement

**Status:** pending; macOS reproduction/fix acceptance BLOCKED on a Mac. **Depends on:** 01 for baseline; final comparison includes 02/03/05. **Parallelizable:** research/harness authoring; GUI measurements and upstream patches run serially.

## Context and evidence

Owner reports LibreOffice macOS right-click delay. No affected version, Mac or reproduction is available here. Linux GTK measurements establish parity/regression behavior only.

| Lead | Verified evidence | What remains unknown |
|---|---|---|
| [tdf#146507](https://bugs.documentfoundation.org/show_bug.cgi?id=146507) | Context-menu lag involving Font Size; [TDF September QA report](https://qa.blog.documentfoundation.org/2026/10/06/qa-dev-report-september-2026/) lists a fix | Exact commit, candidate inclusion, macOS relevance |
| [tdf#173112](https://bugs.documentfoundation.org/show_bug.cgi?id=173112) | macOS scrollbar-drag hang; [upstream notification](https://mid.mail-archive.com/libreoffice-bugs%40lists.freedesktop.org/msg1170184.html) identifies `47b1d3136187d5370fbc3549cd837e23ef937c8d` for 26.8.1; [maintainer](https://www.mail-archive.com/libreoffice-bugs%40lists.freedesktop.org/msg1171361.html) confirms 26.2.6.3 | Different interaction; [later report](https://go.mail-archive.com/libreoffice-bugs%40lists.freedesktop.org/msg1177173.html) says hangs recur; no right-click fix conclusion |
| [tdf#150651](https://bugs.documentfoundation.org/show_bug.cgi?id=150651) | [Original report](https://www.mail-archive.com/libreoffice-bugs%40lists.freedesktop.org/msg886799.html): M1/Monterey, document switching through Dock right-click menu | Dock menu differs from document menu; fix/version unverified |

Direct Bugzilla access was denied during planning; archived messages above are original bugzilla-daemon reports. Recheck current status, fix commits and ancestry at execution; a listed bug is a hypothesis lead, not the owner's diagnosis.

## Exact files

- Create `scripts/perf/context-menu-matrix.json`, `scripts/perf/run-context-menu.py`, `scripts/perf/macos-context-menu.swift`, `scripts/perf/analyze-context-menu.py`, `tests/perf/test_context_menu_metrics.py`, `tests/fixtures/perf/manifest.json`.
- Create `docs/CONTEXT_MENU_PERFORMANCE.md` with raw-evidence links; outputs under `tests/output/perf/`. Conditional fix: `patches/libreoffice/context-menu-latency.patch` and a regression test in the actual affected upstream module; no empty placeholder patch.
- Inspect `vcl/osx/salmenu.cxx`, `vcl/osx/salframeview.mm`, `vcl/unx/gtk3/`, `framework/source/uielement/`, `svx/source/`, `sw/source/uibase/`, `sc/source/ui/`, `sd/source/ui/` at the pin. Locate `AquaSalMenu::ShowNativePopupMenu`, Font Size controller and language/clipboard calls; resolve exact edit files from traces.

## Steps and measurement contract

1. Obtain OS/architecture/LO version, document type, mouse/trackpad gesture, fonts, extensions, accessibility consumers and fresh/existing profile reproduction. Preserve original profiles/documents; test copies. Include Writer text/selection/misspelling/table/link/image, Sheets cell/range/row and Slides text/shape/thumbnail, small/large files and after one hour of representative use.
2. Measure **input event → first displayed frame containing the expected menu**. Separately record handler entry, menu construction, native popup dispatch and accessibility menu-open. AX/AT-SPI events alone do not prove pixels displayed. Linux uses GTK3, AT-SPI and Xvfb framebuffer capture; macOS uses passive CGEvent timing, native AX notifications and ScreenCaptureKit display capture including separate popup windows. Calibrate monotonic clock domains and frame uncertainty. Sources: [CGEventTimestamp](https://developer.apple.com/documentation/coregraphics/cgeventtimestamp), [ScreenCaptureKit displayTime](https://developer.apple.com/documentation/screencapturekit/scstreamframeinfo/displaytime).
3. Per context and configuration run 30 cold trials (fresh process, first menu; separately label new/existing profile) and 100 warm trials. This is not an OS-cache-cold claim. Save raw timestamps, environment/hash, screenshots/video snippets, p50/p95/p99/max and timeout counts; label cold p99 weak with 30 observations. Match upstream/HST source, compiler, backend, fonts, fixture, locale, display scale and hardware. Record physical right-click, Control-click, trackpad and synthetic events separately.
4. Profile slow samples with Linux `perf`/process tracing when permitted; on Mac use Instruments Time Profiler and `sample`. Instrument native/menu-construction spans if necessary. Profiling overhead runs separately from acceptance timing. Toggle font enumeration, dictionaries/spellcheck, clipboard, extensions, accessibility consumers and graphics mode one at a time as diagnostic controls.
5. Prefer a verified upstream fix/backport, then a proven safe configuration default, otherwise a minimal source patch. Check fix ancestry in both candidate tags. In addition to upstream/HST controls, measure matched HST-before/HST-after with only the proposed fix changed to attribute improvement. Never disable spellcheck, Font Size, clipboard or accessibility globally just to pass a timing test; preserve menu commands and correct enabled state. If no Linux issue reproduces, ship no speculative fix and keep the Mac requirement open.
6. Proposed project targets: warm p95 ≤150 ms, cold p95 ≤400 ms, no 5-second timeouts/hangs/missing menus; fail a baseline regression exceeding **both 10% and 20 ms**. These are provisional product targets, not measured facts. A slow affected-Mac baseline must show improvement meeting the agreed target plus functional checks before marking FIXED; document any owner-approved revised target.

## Validation commands

On this Linux VPS, after harness implementation and display `:99` ownership check:

```bash
python3 -m unittest discover -s tests/perf -p 'test_context_menu_metrics.py'
xvfb-run --server-num=99 --server-args='-screen 0 1920x1080x24 -nolisten tcp' dbus-run-session -- env SAL_USE_VCLPLUGIN=gtk3 python3 scripts/perf/run-context-menu.py --app upstream/libreoffice/instdir/program/soffice --matrix scripts/perf/context-menu-matrix.json --cold 30 --warm 100 --timeout-ms 5000 --output tests/output/perf/linux-hst
python3 scripts/perf/analyze-context-menu.py --baseline tests/output/perf/linux-upstream --candidate tests/output/perf/linux-hst --warm-p95-ms 150 --cold-p95-ms 400 --regression-percent 10 --regression-floor-ms 20
```

Capture `linux-upstream` first with the same runner and unpatched reference build from 01. Missing baseline must fail. Harness preflights the display; never use auto-increment ports to hide a conflict. On Mac only, after a native build and interactive-session permissions:

```bash
mkdir -p build/tools
swiftc scripts/perf/macos-context-menu.swift -framework AppKit -framework ApplicationServices -framework ScreenCaptureKit -o build/tools/macos-context-menu
build/tools/macos-context-menu --app '/Applications/HST Office.app' --matrix scripts/perf/context-menu-matrix.json --cold 30 --warm 100 --timeout-ms 5000 --output tests/output/perf/macos-hst
```

The harness creates output directories and tracks/cleans only owned application/capture processes. Mac needs supported Xcode/macOS, Accessibility/Input Monitoring/Screen Recording permissions as applicable, and native upstream/HST comparators. Compiling or validating Swift on Linux is not a Mac pass.

## Risks and rollback

Input simulation bypasses gesture recognition; Xvfb bypasses physical display/compositor behavior. State these limitations in results. Revert only the fix/default and rerun matched tests if menu functionality or timing regresses. Release Linux with the explicit unresolved Mac blocker if Linux gates pass; never close the owner's macOS defect from Linux evidence.
