**HST Office v1.0.0-beta.3 — keyboard audit, 2026-10-31**

Static analysis only. Soffice, X, sockets, and make were not run. Existing workspace changes were left untouched. Evidence comes from the built registry, installed Vietnamese catalogs/UI, HST patches, extension/help files, and the matching engine source.

**KEY-01 — Colliding Vietnamese ribbon mnemonics**

- **Area:** Writer, Calc, Impress; default Tabbed UI.
- **Reproduce:** Use Vietnamese UI, open an ordinary document, and inspect/use Alt+T, Alt+C, and Alt+X on the ribbon tab bar.
- **Expected:** Simultaneously visible tabs have distinct mnemonic letters.
- **Actual:** Writer assigns T to `~Tập tin` and `~Trang đầu`, C to `~Chèn`, `Tham ~chiếu`, and `~Công cụ`, and X to `~Xem lại` and `~Xem`. Calc repeats T, C, and X similarly. Impress additionally assigns T to `~Thiết kế` and `~Trình chiếu`. These examples exclude mutually exclusive contextual tabs. A single advertised chord cannot uniquely identify the intended tab; the resulting cycling/focus behavior awaits runtime evidence.
- **Severity:** minor.
- **Evidence:** Installed `share/config/soffice.cfg/modules/swriter/ui/notebookbar.ui:3059`, `:4043`, `:6828`, `:7546`, `:8385`, `:15545`; `scalc/ui/notebookbar.ui:2869`, `:4078`, `:8101`, `:8772`; `simpress/ui/notebookbar.ui:2967`, `:3976`, `:5829`, `:6340`. Paths are under `upstream/libreoffice/instdir/`. `gettext.GNUTranslations(.../program/resource/vi/LC_MESSAGES/sw.mo).pgettext("TabbedWriter|FileTabLabel", "~File")` returns `~Tập tin`; `HomeTabLabel/~Home` returns `~Trang đầu`. Extracted catalog output: static-evidence.json (`tests/output/codex-ux-audit/shortcuts/static-evidence.json:4890`), Calc at line 8456, Impress at line 11661.
- **Suspected files to fix:** `l10n/vi-overrides.jsonl`, with coordinated overrides for the `TabbedWriter`, `TabbedCalc`, and `TabbedImpress` label contexts. Rebuild the affected `.mo` catalogs; preserve wording and assign distinct letters across visible tabs.
- **Confidence:** confirmed-static for duplicate labels; runtime navigation impact remains unverified.

**KEY-02 — Colliding Vietnamese classic-menu mnemonics**

- **Area:** Writer, Calc, Impress menu bars and popups; Start Center File popup.
- **Reproduce:** Display the classic menu bar in Vietnamese. Try Alt+C in Writer/Calc/Impress, Alt+T in Calc/Impress, or open File and inspect the M-labelled entries. Inspect the Edit popup's Find and Find-and-replace entries.
- **Expected:** Sibling menu choices have distinct mnemonic letters.
- **Actual:** `~Chỉnh sửa` and `~Công cụ` share C in all three document apps. Writer's `Định ~dạng` and `Kiểu ~dáng` share D; Calc adds `~Dữ liệu` to D and assigns T to both `~Tập tin` and `~Trang tính`. Impress assigns T to File, `~Trang chiếu`, and `~Trình chiếu`. Within File, `~Mở...` and `~Mẫu` share M, including in Start Center; the document apps also have `Thiết lập ~máy in...`. Edit repeats T for `~Tìm...` and `~Tìm và thay thế...`. Automatic generation preserves explicit mnemonic markers, so it does not repair these collisions.
- **Severity:** minor.
- **Evidence:** `upstream/libreoffice/instdir/share/registry/res/registry_vi.xcd:2`, `GenericCommands/UserInterface/Popups` nodes `.uno:EditMenu`, `.uno:ToolsMenu`, `.uno:FormatMenu`, `.uno:FormatStylesMenu`, and the Calc/DrawImpress popup overrides. Installed menu membership: `share/config/soffice.cfg/modules/swriter/menubar/menubar.xml:97`, `:375`, `:590`, `:751`; `scalc/menubar/menubar.xml:504`; `simpress/menubar/menubar.xml:517`, `:586`; `StartModule/menubar/menubar.xml:28`. These paths are under `upstream/libreoffice/instdir/`. The extracted `mnemonics` groups in static-evidence.json (`tests/output/codex-ux-audit/shortcuts/static-evidence.json`) list exact sibling labels. `upstream/libreoffice/vcl/source/window/menu.cxx:218` invokes mnemonic generation; `vcl/source/window/mnemonic.cxx:126` returns already-marked strings unchanged.
- **Suspected files to fix:** `l10n/vi-overrides.jsonl`, targeting the relevant `officecfg/registry/data/org/openoffice/Office/UI.po` contexts as a coordinated menu group. `l10n/vi-overrides.jsonl:590` currently sets Slide Show to `~Trình chiếu`.
- **Confidence:** confirmed-static for duplicate labels and preservation by the generator; GTK menu activation/cycling awaits runtime.

**Artifacts and validation**

- probe.py (`tests/output/codex-ux-audit/shortcuts/probe.py`) is the coordinator-run probe. table.json (`tests/output/codex-ux-audit/shortcuts/table.json`) contains 1,056 effective entries across Writer, Calc, Impress, Start Center, and both `vi`/`en-US`. Each row includes the module/global candidates, winning command, registry layer/source, observed effect, and `ok`. Runtime fields are currently `not run`/`null`.
- Resolution follows module before global and primary before secondary, with exact UI locale then en-US fallback; empty localized commands are ignored. Both accelerator components in `main.xcd:9261` and `:9675` are merged, followed by locale resources. Fresh probe documents contain no document-specific shortcuts. F1 is explicitly represented as VCL handling, rather than inferred missing from the registry. Source: `framework/source/accelerators/acceleratorconfiguration.cxx:500`, `:955`; `svtools/source/misc/acceleratorexecute.cxx:285`; `vcl/source/window/winproc.cxx:1295`, all under `upstream/libreoffice/`.
- help-validation.json (`tests/output/codex-ux-audit/shortcuts/help-validation.json`): all 177 Linux static command-resolution checks pass, covering every documented chord in its applicable module and both languages; all 18 installed help HTML files match source. Escape during slideshow is checked against `sd/source/ui/slideshow/slideshowimpl.cxx:2042`. This establishes bindings, not successful execution.
- Menu accelerators use the same module/global configuration (`framework/source/uielement/menubarmanager.cxx:1208`); F1 has an explicit menu exception at line 1231. Tooltip shortcuts follow document/module/global precedence (`vcl/source/helper/commandinfoprovider.cxx:298`). The probe captures live menu key events for comparison with `table.json`.
- `python3 -B tests/output/codex-ux-audit/shortcuts/probe.py --static-only` completed. Syntax compilation, row uniqueness, the 28 tracked standard/tab keys in each module/language, UNO key constant mappings, HST tab-binding precedence, help mappings, and unexecuted runtime fields passed local validation. See static-validation.json (`tests/output/codex-ux-audit/shortcuts/static-validation.json`). No product unit tests were needed for these read-only findings.

**Coordinator runtime**

Run as root outside the sandbox, with Xvfb already serving `:94` and port `22941` free:

```bash
cd /home/office
python3 -B tests/output/codex-ux-audit/shortcuts/probe.py
```

The probe imports the existing `hst_gui.py`, creates one Office at a time, and calls `office.stop()` in `finally`. It never starts X or substitutes another UNO port. Profiles, ODF fixtures, `results.json`, updated `table.json`, live menu JSON, `shots/`, and `probe.log` stay under the shortcuts output directory. It suppresses the welcome/tip/update prompts and Impress's new-document template chooser to isolate shortcuts. The runtime budget is approximately 15 minutes; timeouts/errors and remaining untested rows are recorded without a false pass. An unresponsive session is retired before the next Office starts.

Vietnamese document sessions press every requested standard key, both document-tab keys, and the extra documented formatting/paste/table/page-break/slideshow shortcuts. English repeats the common standard operations, dialogs, tab switching, and closing. Start Center runs in both languages, including Open, New, Help, and Quit. Closing shortcuts are exercised on disposable tabs; Alt+F4 uses a dirty fixture and cancels any save prompt.

The probe is meant to confirm **exactly these reported findings**:

1. **KEY-01:** `vi-{Writer,Calc,Impress}-Alt+{T,C,X}` records ribbon state/hierarchy and screenshots for the conflicting tab mnemonics.
2. **KEY-02:** `*-MENUS`, `vi-*-MENU_C_MOD2`, and Start Center's File-menu capture record actual menu labels, accelerators, and mnemonic activation. These need screenshot/hierarchy review; static duplicate labels are not converted into an invented runtime failure.

All other probe steps are shortcut regression checks, not additional defect claims.

**Unresolved validation**

Actual key execution awaits the coordinator. F1 records the expanded installed help URL and windows appearing after the real keypress, but leaves browser navigation unverified until the screenshot/URL is inspected. Alt+F4 remains unverified without a window manager; no title-bar close request is substituted. Real Unikey/ibus-bamboo input and macOS shortcuts require their native environments. The inherited Ctrl+Alt+C/E and Ctrl+Alt+Shift+V/G/K/P bindings are enumerated in `static-evidence.json`; their existence alone does not establish an IME conflict.
