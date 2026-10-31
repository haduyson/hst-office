# HST Office display audit — static evidence, 2026-10-31

Four confirmed text defects and two visual risks need runtime review. No GUI was launched, no build was run, and no source files were changed.

**Snapshot:** `/home/office/upstream/libreoffice/instdir`. Its installed `share/extensions/hst-vietnamese-tools/data/release.json:2` says `1.0.0-beta.2`, although the requested target is beta.3. The generated `upstream/libreoffice/include/hst_version.h:4` says `1.0.0`. These findings describe the inspected install; they do not establish that the beta.3 package has the same resources. The pre-existing dirty banner/source edits were left untouched.

Evidence: decoded catalogs, resource matches and SHA-256 hashes (`tests/output/codex-ux-audit/display/static-evidence.json`). Paths below are relative to `/home/office`; `I/` abbreviates `upstream/libreoffice/instdir/` and `E/` abbreviates `extensions/hst-vietnamese-tools/`.

## Findings

### DSP-01 — Licence summary has the wrong copyright line

- **Area:** Help → Licence information, vi and en-US.
- **Steps:** Open Writer; dispatch `.uno:ShowLicense`; read the copyright paragraph.
- **Expected:** `© 2026 HASON TECH · © 2000–2026 The Document Foundation và các tác giả LibreOffice`, without “All rights reserved”.
- **Actual:** English says `Copyright © 2000–2026 LibreOffice contributors. All rights reserved.` Vietnamese says `Bản quyền © 2000–2026 thuộc những người đóng góp cho LibreOffice. Bảo lưu mọi quyền.` Neither contains the owner’s line.
- **Severity / confidence:** minor / confirmed-static.
- **Evidence:** `I/share/config/soffice.cfg/sfx/ui/licensedialog.ui:74`; installed `sfx.mo`, context `licensedialog|label`, decoded with `gettext.GNUTranslations`; matching translation at `upstream/libreoffice/translations/source/vi/sfx2/messages.po:4011`. `upstream/libreoffice/sfx2/source/appl/appserv.cxx:325` appends this label unchanged after the HST notice.
- **Suspected fix:** `patches/libreoffice/hst-copyright.patch` / `hst-debrand.patch`, owning `sfx2/uiconfig/ui/licensedialog.ui`, and the Vietnamese translation/override for that label.

### DSP-02 — Licence summary remains English in an English UI

- **Area:** Licence dialog introductory/legal summary.
- **Steps:** Start with `lang="en_US.UTF-8"`; dispatch `.uno:ShowLicense`.
- **Expected:** The product’s licence-dialog content remains Vietnamese under the owner’s language policy. Original third-party licence documents are outside this finding.
- **Actual:** The HST preamble is bilingual, followed by an English product summary beginning `%PRODUCTNAME is made available subject to the terms…`. Changing the UI language changes the summary’s language.
- **Severity / confidence:** minor / confirmed-static.
- **Evidence:** `I/share/config/soffice.cfg/sfx/ui/licensedialog.ui:68` has `translatable="yes"`; `upstream/libreoffice/sfx2/source/appl/appserv.cxx:317` prepends Vietnamese and English but retains `xLabel->get_label()` at line 325. There are no installed en-US `.mo` files; English uses the `.ui` source text.
- **Suspected fix:** `patches/libreoffice/hst-debrand.patch`, owning the licence-dialog label and its assembly in `sfx2/source/appl/appserv.cxx`.

### DSP-03 — English HTML Options still displays “LibreOffice Basic”

- **Area:** Tools → Options → Load/Save → HTML Compatibility.
- **Steps:** Use en-US; open that Options page; inspect the Basic-export checkbox. The probe opens it with `OptionsPageID=17000`.
- **Expected:** The visible product name is HST Office in either UI language.
- **Actual:** The English checkbox says `LibreOffice Basic`. Vietnamese already translates the same entry to `%PRODUCTNAME _Basic`, so it resolves to HST Office there.
- **Severity / confidence:** cosmetic / confirmed-static.
- **Evidence:** `I/share/config/soffice.cfg/cui/ui/opthtmlpage.ui:629` supplies `LibreOffice _Basic`; line 630 makes the control visible. `upstream/libreoffice/cui/source/options/opthtml.cxx:51` binds the checkbox and line 240 sets its state without replacing its label. Installed `cui.mo` context `opthtmlpage|starbasic` decodes to `%PRODUCTNAME _Basic`.
- **Suspected fix:** `patches/libreoffice/hst-debrand.patch`, owning `cui/uiconfig/ui/opthtmlpage.ui`; retain the existing Vietnamese translation when changing the source key.

### DSP-04 — Extension text colours may lose contrast in dark mode

- **Area:** HST welcome/solutions dialog and NĐ 30 validation text.
- **Steps:** Set Tools → Options → Appearance to Dark. Open HST solutions/welcome; inspect the links and F1 hint. Open NĐ 30 and enter the invalid values from DSP-05.
- **Expected:** These labels remain readable against the actual dark dialog surface.
- **Actual:** Links always use `#0B57D0`, the F1 hint `#5F6368`, and validation errors `#C5221F`, while the dialog background follows the toolkit. There is no dark-mode colour branch for these labels. Rendered contrast is unmeasured.
- **Severity / confidence:** minor / needs-runtime.
- **Evidence:** `E/python/hst_office/welcome_dialog.py:21`, `:99`, `:143`; `E/python/hst_office/wizard_nd30.py:20`, `:71`; `E/python/hst_office/dialogs.py:42`. These four installed Python files were byte-identical to their repository counterparts when checked.
- **Suspected fix:** `E/python/hst_office/welcome_dialog.py` and `wizard_nd30.py`, using theme-aware foreground/background pairs.

### DSP-05 — NĐ 30 validation summary has little room for multiple errors

- **Area:** NĐ 30 wizard, status below the preview.
- **Steps:** Open `org.hst.office.vi:Nd30Wizard`. Enter number `12A`, symbol `ABC /`, and date `31/02/2026`; inspect the entire validation summary, including its last line.
- **Expected:** All three errors are readable without clipping at normal and enlarged DPI.
- **Actual:** The errors are concatenated into one wrapped fixed-text control measuring only **286 × 14 AppFont units**. The installed pure validator produces a 109-character Vietnamese summary and a 95-character English summary for those inputs. The control has neither automatic height growth nor scrolling. Whether the last line is actually clipped needs font/layout measurement.
- **Severity / confidence:** minor / needs-runtime.
- **Evidence:** `E/python/hst_office/wizard_nd30.py:13` defines the 600 × 362 dialog; lines 16–17 produce preview width 286; line 70 allocates the 14-unit status height; line 104 assigns all errors. `E/python/hst_office/nd30.py:78` validates these inputs. The Vietnamese output ends `Ngày: ngày không hợp lệ`.
- **Suspected fix:** `E/python/hst_office/wizard_nd30.py`, status sizing or presentation of multiple errors.

### DSP-06 — Update menu captions ignore the English UI language

- **Area:** HST menu, Help menu and Extension ribbon tab.
- **Steps:** Start en-US; inspect the HST update command, Help’s update command, and the Extension tab.
- **Expected:** Menu and ribbon-command captions follow the OS/UI language, as requested. This finding does not prescribe the update result dialog’s language.
- **Actual:** The en-US values are `Kiểm tra cập nhật…` and `Kiểm tra cập nhật HST Office…`, identical to Vietnamese.
- **Severity / confidence:** minor / confirmed-static.
- **Evidence:** `I/share/extensions/hst-vietnamese-tools/Addons.xcu:93`, `:107`, `:197` explicitly assign those values to `xml:lang="en-US"`. The source `E/Addons.xcu` contains the same assignments.
- **Suspected fix:** `E/Addons.xcu` and its owning label-generation/check logic, if generated.

## Coverage and limits

- Read `README.md`, `docs/BACKLOG.md`, `docs/L10N_GLOSSARY.md`, the complete GUI helper, relevant HST patches, installed registry/UI resources and extension dialogs. Applied the UI/UX review skill’s desktop-relevant layout, contrast and truncation checks.
- Decoded **34 installed Vietnamese `.mo` catalogs** and searched built registry/UI/extension resources for `LibreOffice`, `The Document Foundation`, `libreoffice.org`, `github`, and product-name placeholders. The scan found **zero GitHub matches** in the inspected textual resources and catalog values. Reachability and runtime replacement were checked before promoting branding matches to findings; this is not a claim that every binary error path is clean.
- Compared translations and sizing in **17 Writer/Calc/Impress `notebookbar*.ui` files**. The installed registry selects `notebookbar.ui` for all three. The default tab labels are present and translated. Examples of expansion are Writer `Media Player` → `Trình phát đa phương tiện` (12 → 24 characters) and `Extension` → `Phần mở rộng` (9 → 12, excluding mnemonic markers). Default explicit width requests are 100 for line-style controls and 200 for media controls; ordinary tab labels do not have hard fixed widths. Width requests and string length alone do not prove clipping, so no ribbon-overflow defect is asserted.
- Actual fit, scrolling, glyph clipping, the one-row Writer gallery, icon consistency, Start Center banner, and document-tab contrast require screenshots. `SymbolStyle=auto` and installed light/dark icon packs do not establish the selected runtime theme. The probe records effective settings and device DPI rather than assuming a forced DPI value took effect.
- No runtime screenshots or runtime PASS results were fabricated. Static validation of the probe is recorded in validation.log (`tests/output/codex-ux-audit/display/validation.log`). Unit tests were not run: no product implementation changed, and they cannot establish visual fit.

## Probe handoff

Run outside the sandbox, as root, with Xvfb already on **`:94`** and UNO **22942** unused:

```bash
cd /home/office
python3 tests/output/codex-ux-audit/display/probe.py
```

probe.py (`tests/output/codex-ux-audit/display/probe.py`) writes `results.json`, `probe.log`, fresh profiles under `runs/`, and numbered `shots/*.png`, all below `tests/output/codex-ux-audit/display/`. Its four baseline sessions cover vi/en-US at 1600×1000 and 1366×768. It captures Start Center, Writer, Calc, Impress, every requested dialog, extra HTML/Appearance Options pages, and document tabs. The welcome capture uses `org.hst.office.vi:ShowSolutions`, which opens the same welcome component with Vietnamese content. Print/PDF are cancelled without producing output.

Four further sessions cover dark mode in both languages, Vietnamese at `SAL_FORCEDPI=144`, and English at `SAL_FORCEDPI=192`. Variant sessions repeat the three module windows, Start Center, Appearance, welcome, NĐ 30, update, About, licence and Format Cells. The probe attempts Insert/Extension/Home ribbon captures when the build exposes UITest; unavailable introspection is recorded rather than treated as a product failure.

Modal dispatch runs on daemon threads; X windows are filtered by the helper-owned PID. Keyboard input explicitly focuses that window. Dialogs close with Escape, the welcome close helper, or a dialog-only close request. Each session calls `office.stop()` in `finally`. A real manual update check runs last; a timeout stops that instance before another starts. There is no mock update response or extra listening port. Work stops at 750 seconds with cleanup time reserved; unstarted sessions are recorded as skipped.

If Xvfb cannot change resolution, the probe records the actual framebuffer and the failed requested mode; a smaller application window does **not** count as a real 1366×768 dialog-fit test. Screenshot capture success is distinct from manual visual approval (`actual.visual_review`); `ok=null` means undecided or optional capability unavailable.

**Findings the probe is intended to confirm, exactly:**

| ID | Runtime evidence |
|---|---|
| DSP-01 | `*-licence.png`, optional extracted `label` text, and `DSP-01` result rows. |
| DSP-02 | English and Vietnamese `*-licence.png`, with optional extracted text. |
| DSP-03 | `*-options-html.png` in both languages; optional `starbasic` text. |
| DSP-04 | Dark `*-welcome.png` and `*-nd30-invalid.png`; inspect foreground/background contrast. |
| DSP-05 | `*-nd30-invalid.png` at both baseline sizes and DPI variants; verify all three inputs and the final error line. |
| DSP-06 | English/Vietnamese `*-ribbon-extension.png` when UITest supports the notebookbar; otherwise this item remains statically confirmed but visually unverified. |

## Unresolved questions

1. Is the installed tree intentionally still stamped beta.2, or will the coordinator run against a refreshed beta.3 tree? Compare the saved hashes before attributing results to beta.3.
2. Should the update **result dialog** also remain Vietnamese in en-US? Its source declares that policy, but the supplied exception list does not mention it. The mixed menu captions in DSP-06 are separately governed by the explicit menu-language rule.
