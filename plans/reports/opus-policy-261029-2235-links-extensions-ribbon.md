# opus-policy: links, extensions, HST ribbon (2026-10-29)

Status: DONE_WITH_CONCERNS (see Remaining).

Patches stay in series order; `scripts/apply-patches.sh --check`: 12/12 "already applied". Edited sections were regenerated from the pristine 26.8.1.1 tarball plus the earlier patches and compared with the tree, so each still applies to pristine in order.

## A. No repository URL in the product
- About: "Mã nguồn: https://github.com/..." line removed; now one line "Phần mềm nguồn mở — xem Trợ giúp → Thông tin giấy phép." (`hst-about.patch`). Release Notes button hidden (Credits already).
- `hst-defaults.patch`: SendFeedbackURL, GetInvolvedURL, ReleaseNotesURL, CreditsURL (and ExtensionsURL) now empty. `hst-debrand.patch`: their handlers (appserv.cxx) do nothing on an empty URL (reachable only via the command search).
- MPL s3.2 notice only in the licence documents, Vietnamese + English, e-mail only (lienhe@hasontech.vn): Help > License Information dialog (code prepends it, all UI languages; `licensedialog` is what the menu opens, its "Hiển thị giấy phép" button opens LICENSE.html) and the top of `readlicense_oo/license/license.xml` -> installed `LICENSE.html` / `LICENSE`. Both in `hst-debrand.patch`.
- vi override of the crash-report text had a github issues URL: replaced with the e-mail (`l10n/vi-overrides.jsonl`).
- Extension Manager publisher links to github/libreoffice.org/documentfoundation hosts are dropped (name shown as plain text) - third-party dictionary metadata had 8 github links.
- `tests/runtime/check-no-libreoffice-ui.py`: About text has no URL/github; licence notice present at the top of LICENSE.html/LICENSE and in the dialog source with no URL; "github" (any case) and extension-catalogue references scanned in all `.mo`, `share/registry`, `share/config` (menubar, notebookbar, .ui), the HST extension. Allow-list: `share/extensions/dict-*` (third-party dictionary authors' pages; reason in the script) and the licence documents (not in the scanned roots). 1981 files scanned, 0 hits. `check-defaults.py` also asserts the empty URLs.

## B. Hidden, not retargeted
`scripts/patches/strip-donation.py` extended (COMMANDS = Donation, SendFeedback, GetInvolved; collapses only separators made adjacent by the removal) and `hst-remove-donation.patch` regenerated from pristine: 34 files = all menubars (Start Center, Writer, Calc, Impress, Draw, Math, Base and the others), popup/notebookbar XML, Tabbed notebookbar .ui (full, compact, groupedbar). "What's New" has no menu item (only the About link, hidden). Website stays hasontech.vn. Screenshot 03: Help menu without feedback/get involved; 08: About.

## C. Extensions (`hst-extensions.patch` new, last in series; `hst-start-center-banner.patch`, `hst-defaults.patch`, `hst-debrand.patch`)
- Start Center "Phần mở rộng" opens `.uno:ExtensionManager` (ExtLinkClickHdl removed). Extension Manager: "Get more extensions online" link and Update button hidden; per-extension "Update..." item removed; `ExtensionCmdQueue::checkForUpdates` is a no-op (every online update path ends there); WebsiteLink/ExtensionsURL empty. Dictionary `en` description no longer links the extension library.
- Online catalogue dialog (templates, dictionaries, themes, icons, palettes, gallery): `AdditionsDialogHelper::RunAdditionsDialog` opens nothing; buttons/links hidden (templates action bar, appearance, colour page, linguistic page, edit-modules dialog, gallery sidebar). 3 tips linking to the extension site removed.
- Confirmation before every install from a user file (Add..., double-click `.oxt`, `soffice file.oxt`): `_addExtension` always asks; dialog title "Cài đặt tiện ích mở rộng", owner text (with extension name), buttons "Tiếp tục" / "Hủy" (Cancel is default; non-vi UI uses standard OK/Cancel). Strings: vi overrides of existing msgids `RID_STR_WARNING_INSTALL_EXTENSION`, `RID_STR_ADD_PACKAGES` (new msgids cannot be added with the overrides tool). Verified live: Cancel installs nothing; Continue installs the test .oxt (`work/policy-sample.oxt`). Bundled HST extension unchanged (still "Đi kèm với HST Office").
- Docs: `docs/LICENSE_AUDIT.md` (3.1 source row, 3.2 About/menu rows, extension row now "Đã xử lý"), `docs/BRAND.md` (About rule), `docs/EXTENSION_CONTRACT.md`, README bullet.

## D. HST commands in the ribbon
Native mechanism: `Addons.xcu` `OfficeToolBar` replaced by `OfficeNotebookBar` (items appear in the Tabbed UI "Phần mở rộng" tab; Style Text). No floating "Phần bổ sung" window. Writer: NĐ 30, TCVN3/VNI, Giải pháp HASON TECH; Calc: date, VND, percent, CSV, Giải pháp; Impress: Giải pháp (added so the tab is not empty). HST menu unchanged. Fresh profile, Xvfb :97, user nobody: screenshots 10/11/16-swriter, 13/16-scalc, 14/15/16-simpress. In the non-Tabbed layout there is no HST toolbar any more (menu only).

## E. Build and QA
`build-linux.sh --build` (vi `.mo` deleted first; override rows, registry, extension regenerated; built 4 times, last 5m40), stale package outputs from the opus-ver list deleted, `--package`: 38 .deb in dist/linux.
- check-defaults.py (nobody): all PASS incl. 6 new URL checks. check-office-roundtrip.py: 9/9 PASS. check-no-libreoffice-ui.py: PASS. check-deb-install.sh dist/linux (docker): PASS (incl. no-libreoffice-ui step). ci-quality.sh: 18 commands, 0 failures.
- Screenshots `tests/output/screenshots-policy/` (all viewed): 01 welcome, 02 Start Center, 03 Help menu, 04 Extension Manager (no online link, no Update), 05 Add picker, 06 install confirmation, 07 after cancel / 07-after-continue (installed), 08 About, 09 licence dialog (notice on top), 10-17 Writer/Calc/Impress ribbon. Profile `tests/output/hst-gui-policy/` (LANG vi_VN + private LOCPATH). My soffice killed; none left.

## Remaining / notes
- No window manager on Xvfb, so dialog title bars (the new title) are not visible in screenshots; the title is set in code.
- The online-update "check" in the "extension update required" dialog (after an engine upgrade) is now inert (button does nothing).
- `NOTICE.md` (repo document, not shipped in the product tree) still names the GitHub repository; not changed (repo may move; owner to decide).
- The vi licence dialog still carries the upstream legal text (LibreOffice copyright, mozilla.org and libreoffice.org URLs): kept, legal.
- Bundled dictionary extensions still show their authors' homepages (non-github) as clickable publisher links.
- Existing profiles keep the old floating toolbar only if the user had already placed it; fresh profiles are clean.

Files changed: README.md, docs/BRAND.md, docs/EXTENSION_CONTRACT.md, docs/LICENSE_AUDIT.md, extensions/hst-vietnamese-tools/Addons.xcu, l10n/vi-overrides.jsonl, patches/libreoffice/{series,hst-about,hst-debrand,hst-defaults,hst-remove-donation,hst-start-center-banner}.patch, patches/libreoffice/hst-extensions.patch (new), scripts/patches/strip-donation.py, tests/runtime/{check-defaults,check-no-libreoffice-ui}.py, this report. Upstream tree (via patches): cui about.cxx, tipoftheday.hrc, tipofthedaydlg.cxx, appearance/colorpage/optlingupage/editmodulesdialog .ui, optlingu.cxx; sfx2 appserv.cxx, backingwindow.cxx/.hxx, AdditionsDialogHelper.cxx, templatedlg.cxx; desktop deployment gui (dialog2, extensioncmdqueue, extensionboxwithbuttons, extlistbox); svx sidebargallery.ui; officecfg Common.xcu, ExtensionManager.xcu; readlicense_oo license.xml; dictionaries/en/description.xml; 34 menubar/notebookbar files. Generated: dist/linux/*, tests/output/{screenshots-policy,hst-gui-policy,deb-install}, work/*.
