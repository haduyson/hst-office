# Research: slow right-click context menu in LibreOffice on macOS (target 26.8.x)

Researcher subagent, 2026-10-29. Saved verbatim-in-substance by the controller (subagent could not write files). No Mac available: everything below comes from bug reports and source reading — **no measurement of the owner's delay**.

## Bottom line

- No open tdf bug for "context menu slow on macOS" in 25.x/26.x; old macOS reports (tdf#107113, tdf#106962) closed WORKSFORME. 26.8 release notes say nothing about context-menu performance.
- Candidates ranked by evidence:
  1. **Synchronous spell/grammar work on right-click** — `SwView::ExecSpellPopup` ([viewling.cxx](https://github.com/LibreOffice/core/blob/master/sw/source/uibase/uiview/viewling.cxx)): with autospell on and no selection it may run `AutoSpell_` on the whole "WrongDirty" paragraph, then `GetCorrection()`, then `GetGrammarCorrection()` before showing the menu, all on the main thread. [tdf#154279](https://bugs.documentfoundation.org/show_bug.cgi?id=154279) (NEW, all platforms, reproduced Linux/Windows): freeze seconds–minutes when paragraph language has many dictionaries. macOS also ships `MacOSXSpell` calling NSSpellChecker synchronously ([macspellimp.mm](https://github.com/LibreOffice/core/blob/master/lingucomponent/source/spellcheck/macosxspell/macspellimp.mm)) — latency UNVERIFIED.
  2. **Main thread busy with background layout/autospell** — [tdf#120014](https://bugs.documentfoundation.org/show_bug.cgi?id=120014) fixed by [gerrit 175725](https://gerrit.libreoffice.org/c/core/+/175725) (25.2+); [tdf#155266](https://bugs.documentfoundation.org/show_bug.cgi?id=155266)/[tdf#160767](https://bugs.documentfoundation.org/show_bug.cgi?id=160767) fixed in 24.x. Already in 26.8; work becomes interruptible, not faster.
  3. **Cold-start init on first right-click** (NSSpellChecker, thesaurus "Synonyms") — [tdf#107113](https://bugs.documentfoundation.org/show_bug.cgi?id=107113) 2.29 s first vs 0.33 s later; [tdf#105439](https://bugs.documentfoundation.org/show_bug.cgi?id=105439). Old.
  4. **Hypothesis:** 26.8.2+ shows popup via `[NSMenu popUpContextMenu:]` ([gerrit 211382](https://gerrit.libreoffice.org/c/core/+/211382), tdf#150754) → OS adds Services/AutoFill items. Not in 26.8.1. Do **not** backport master-only [211014](https://gerrit.libreoffice.org/c/core/+/211014) (Continuity items).
  5. Accessibility clients / window managers (BetterTouchTool, Moom, VoiceOver…) — dev checklist in [tdf#57071](https://bugs.documentfoundation.org/show_bug.cgi?id=57071) c2 (2012). `AquaSalMenu::ShowNativePopupMenu` toggles a11y popup state ([salmenu.cxx](https://github.com/LibreOffice/core/blob/master/vcl/osx/salmenu.cxx)).
  6. Custom "Font Size" context item creates an info printer — [tdf#146507](https://bugs.documentfoundation.org/show_bug.cgi?id=146507), fixed master only by [gerrit 210516](https://gerrit.libreoffice.org/c/core/+/210516).
- Skia/Metal: unlikely (popup is native NSMenu). 26.8 defaults to raster via [gerrit 208182](https://gerrit.libreoffice.org/c/core/+/208182) (verify in tree).

## Config mitigations (HST defaults)

| Setting | Effect | Side effect | Verdict |
|---|---|---|---|
| `Linguistic/General/IsSpellAuto=false` | skips ExecSpellPopup spell path | no squiggles | A/B proof only; needs owner approval to ship |
| `Common/VCL/ForceSkiaGPU=false`, `SAL_SKIA=raster` | CPU raster | — | already 26.8 default; A/B only |
| Don't ship "Font Size"/extra items in context menu | avoids printer query | none | free |
| No bundled grammar extensions (LanguageTool) | removes GetGrammarCorrection cost | lose feature | free for HST v1 |
| Few dictionaries per language | reduces suggestion cost | — | only if profiling shows |

No config key disables OS-added NSMenu items; code change in `AquaSalMenu::ShowNativePopupMenu` is the only lever.

## Code-level options

- Spell path: our own patch in `ExecSpellPopup` (avoid synchronous full-paragraph `AutoSpell_`, bound suggestion time) if profiling points there.
- 26.8.2 popUpContextMenu: if delay appears only after it, revert that single change.

## Measuring on macOS

1. `sample soffice.bin 5 -file out.txt` / Instruments Time Profiler during the delay — look for ExecSpellPopup, AutoSpell_, NSSpellChecker, GetGrammarCorrection, NSMenu/NSServices, idle tasks. Highest value.
2. Automated: `cliclick rc:x,y` or `CGEventPost`, poll `CGWindowListCopyWindowInfo` for soffice window at popup-menu level (101); avoid AppleScript (uses a11y).
3. Matrix: clean vs user profile; cold vs warm; plain text / misspelt word / selection / other-language paragraph; autospell on/off; `SAL_SKIA=raster`; 26.8.1 vs 26.8.2+; a11y tools quit; right after opening large doc vs after 1 min.
4. `XToolkitExperimental.startRecording` trace events (zone coverage UNVERIFIED).

## Linux parity

Candidate 1 and 6 measurable on Linux (tdf#154279 reproduces on gtk3). Candidates 3–5 and the NSMenu step are macOS-only → a delay absent on Linux is macOS-specific.

## Unresolved questions

1. Owner's macOS version + chip; LibreOffice version (26.8.0/1 or 26.8.2+)?
2. First right-click only or every time? Only on misspelt words / with autospell / in large docs?
3. Accessibility/window-manager/text tools running? Extra dictionaries/grammar extensions installed?
4. Is 208182 in 26.8.1 tree? (check during source unpack)
5. What does `sample` show during the delay?

## Owner answers (2026-10-29 13:42)

- Delay on **every** right-click, in **Writer, Calc and Impress**; Mac = Apple Silicon. Owner will run an HST-provided measurement script on the Mac and send results.
- Consequence: Writer-only `ExecSpellPopup` (candidate 1) and cold-start init (candidate 3) cannot explain it alone. Focus shifts to shared macOS VCL path: native popup (`AquaSalMenu::ShowNativePopupMenu` / NSPopUpButtonCell vs popUpContextMenu), per-item status updates on `PopupMenu::Activate` (e.g. Paste state querying NSPasteboard via system clipboard), accessibility clients. Must be confirmed by `sample` on the owner's Mac.
