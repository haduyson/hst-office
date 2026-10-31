# HST Office beta.3 — interaction flows, static audit

Three findings: one branding inconsistency, one quit-cancellation concern, and one incorrect locking-error translation. No GUI execution occurred. Window behavior remains pending the coordinator's run.

Scope: `/home/office/upstream/libreoffice/instdir`, its matching source, HST patches, and the welcome extension. README, backlog, and glossary were read first. Owner decisions supplied with the audit were treated as requirements. Source and installed `welcome_job.py`, `welcome_dialog.py`, and `dialogs.py` are byte-identical. Existing workspace changes were left untouched.

## FLO-01 — Document titles use different application names from the welcome screen

- **Area:** Window titles and application identity.
- **Severity:** Cosmetic.
- **Confidence:** confirmed-static for title inputs/construction; visible-window confirmation pending.
- **Steps:** In vi and en-US, create each of Writer, Sheets, and Slides from Start Center. Inspect its title before editing, after editing, after saving, and after another edit.
- **Expected:** The application suffix agrees with the advertised names: `HST Writer`, `HST Sheets`, `HST Slides`.
- **Actual:** Installed factory UI names remain `Writer`, `Calc`, and `Impress`. Title construction appends product `HST Office` plus that factory name. Thus the source predicts `Không tên 1 — HST Office Writer`, `… — HST Office Calc`, and `… — HST Office Impress`; English uses `Untitled`. The inconsistency concerns the application suffix, not the existing translation “Không tên”.
- **Evidence:** `upstream/libreoffice/framework/source/fwe/helper/titlehelper.cxx:505`, `:539`, `:571`; `upstream/libreoffice/framework/source/services/desktop.cxx:111`; `upstream/libreoffice/officecfg/registry/data/org/openoffice/Setup.xcu:77`, `:165`. XML extraction from installed `calc.xcd`, `writer.xcd`, `impress.xcd`, and `main.xcd` confirms these inputs. Installed `fwk.mo` maps `STR_UNTITLED_DOCUMENT\x04Untitled` to `Không tên`. Welcome labels advertise the three HST names at `extensions/hst-vietnamese-tools/locales/vi.json:141`.
- **Suspected files to fix:** `patches/libreoffice/hst-window-title.patch` / the title helper; possibly the display-name settings owned by `hst-debrand.patch`. Preserve internal module identifiers.
- **Probe confirmation:** `FLO-01`, both locales, all three modules and four title states.

## FLO-02 — Cancel during Quit continues processing other documents

- **Area:** File → Exit / Ctrl+Q with mixed modified tabs. **route: tabs owner** (shared quit path).
- **Severity:** Minor; repeated prompts and closure of other clean documents, with no proven loss of unsaved data.
- **Confidence:** needs-runtime.
- **Steps:** Open modified Writer, Sheets, and Slides documents. Press Ctrl+Q, then Cancel in the first save prompt. Repeat using File → Exit. Compare with Cancel after title-bar X.
- **Expected:** Cancel stops the current quit action and preserves documents that have not yet been processed, consistently with title-bar X.
- **Actual:** Normal Quit calls `Desktop::terminate()`. On a controller's refusal to suspend, the close loop increments its failure count and uses `continue`; it uses `break` only for session shutdown. It therefore proceeds to other documents, which can produce more save prompts or close clean documents. HST's title-bar close handler instead immediately returns on the first refusal.
- **Evidence:** `upstream/libreoffice/sfx2/source/appl/appserv.cxx:457`; `upstream/libreoffice/framework/source/services/desktop.cxx:153`, `:372`, `:1681`; `upstream/libreoffice/framework/source/services/documenttabgroup.cxx:621`. HST wraps termination with `setClosingAll` in `patches/libreoffice/hst-document-tabs.patch:1802`, without changing this continuation rule.
- **Suspected files to fix:** `patches/libreoffice/hst-document-tabs.patch`, particularly its integration with `framework/source/services/desktop.cxx`. Coordinate any change with the tabs owner.
- **Probe confirmation:** `FLO-02`, both locales, first Cancel followed by observation of additional prompts. Subsequent prompts are captured and cancelled; a separate quit action then discards each probe document to test successful exit.

## FLO-03 — A locking error identifies the wrong lock owner in Vietnamese

- **Area:** File-lock error text.
- **Severity:** Minor.
- **Confidence:** confirmed-static.
- **Steps:** Decode installed `uui.mo` with Python `gettext.GNUTranslations`; inspect key `RID_UUI_ERRHDL\x04The file $(ARG1) is currently not locked by yourself.` The corresponding runtime trigger is `InteractiveLockingNotLockedException`, such as an operation requiring a lock that the current user does not hold.
- **Expected:** “Tệp $(ARG1) hiện không được bạn khóa.” The message must say the current user does not own the required lock.
- **Actual:** “Tệp $(ARG1) không bị khóa bởi người khác.” This instead says nobody else has locked the file, obscuring why the operation cannot proceed.
- **Evidence:** Installed `upstream/libreoffice/instdir/program/resource/vi/LC_MESSAGES/uui.mo`, key above; source translation at `upstream/libreoffice/translations/source/vi/uui/messages.po:439`; English definition at `upstream/libreoffice/uui/inc/ids.hrc:157`; exception-to-message mapping at `upstream/libreoffice/uui/source/iahndl.cxx:656`.
- **Suspected file to fix:** `l10n/vi-overrides.jsonl`, followed by the existing translation build process.
- **Probe confirmation:** None. The requested ordinary `.~lock.*#` fixture exercises `Document in Use`, a different message. That fixture must not be cited as confirmation of this specific mistranslation. No remote server or synthetic interaction request is added.

## Runtime handoff

Run as root outside the sandbox, with Xvfb `:94` already running:

```sh
python3 /home/office/tests/output/codex-ux-audit/flows/probe.py
```

The probe (`tests/output/codex-ux-audit/flows/probe.py`) uses only UNO port `22944`, refuses an occupied port, starts one `hst_gui.Office` at a time, and calls `office.stop()` in `finally`. Profiles, fixtures, logs, and screenshots stay under `tests/output/codex-ux-audit/flows/`. It bounds UNO calls, external commands, modal handling, startup, and shutdown. The work budget is 780 seconds plus bounded cleanup; exhausted or failed steps are recorded rather than declared passing.

**Exactly which findings it confirms:** FLO-01 and FLO-02. FLO-03 is supported by catalog evidence only.

Additional requested coverage is exploratory, not additional static findings:

- Both locales: fresh-profile welcome dismissed by Escape, Enter, and its button; checked/unchecked preference and restart of the same profile; initial windows, first-document tips, and their observed order. The probe explicitly restores welcome/tips because the helper normally suppresses them.
- Start Center: keyboard activation of its actual Writer/Sheets/Slides buttons; saved-file recent thumbnails; keyboard opening of a recent entry; return after the last document closes. Focused-button screenshots make navigation auditable.
- Mixed modified documents: actual tab x, Ctrl+W, title-bar X, partial closure then Cancel, successful closure, File → Exit and Ctrl+Q. Save/Don't Save/Cancel mnemonics are exercised. Tab-click geometry comes from accessibility and source layout; unavailable geometry is recorded as a probe failure, never replaced with an unrelated command.
- Slides: F5 from page two starts at page one; Shift+F5 starts at page two; Escape restores the same document tab.
- Errors: nonexistent file, a ZIP-format DOCX with truncated document XML, save into a directory with mode `0555` while Office runs as `hstbuild`, and a valid lock record naming a fictional other user. Every detected dialog is captured before it is answered.

`results.json` contains `{id, step, expected, actual, ok, screenshot}` records. `shots/NN-name.png` and `probe.log` accompany them. `ok: null` means screenshot/text review remains necessary; it is not a pass. Native GTK dialog text may be absent from UNO UI trees, so review screenshots for Vietnamese text, branding, clipping, button mnemonics, and thumbnail appearance. Errors or timeouts may be harness limitations; do not automatically promote them into product defects.

## Verification performed

- Probe parsed and compiled in memory without execution. No X display, socket, `runuser`, `soffice`, or `make` was invoked by this audit.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_welcome.py`: **9 passed**. Existing `ResourceWarning`s at `test_welcome.py:70` concern unclosed `vi.json` and `en.json` handles. These tests cover content, URLs, and locale keys, not GUI dismissal or persisted state.
- Static extraction and hashes (`tests/output/codex-ux-audit/flows/static-evidence.txt`) retain the installed registry and catalog values used above.

Unresolved: coordinator runtime execution and screenshot review, including any tab-owner routing justified by those results.
