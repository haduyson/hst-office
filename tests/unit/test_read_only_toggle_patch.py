# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Read-only mode both ways (hst-read-only-toggle.patch) and the ribbon data behind it.

Offline checks of the patch text and the ribbon data: the edit mode switch reopens the file for writing, the title
mark follows the UI state, the Info page button, the recovery question's default button, the Windows file dialog
texts with their Vietnamese strings, the View tab's Chỉ đọc button in Writer, Sheets and Slides, and the protection tooltips
of Sheets that say they are not the read-only mode. The behaviour itself: CppunitTest_sfx2_hst_autosave."""
import json
import os
import re
import unittest

from _paths import ROOT
from patch_sections import added, after, po_entries, removed

PATCH = "hst-read-only-toggle.patch"
PATCHES = os.path.join(ROOT, "patches", "libreoffice")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class ReadOnlyTogglePatch(unittest.TestCase):
    def test_last_in_series(self):
        names = [n.strip() for n in read("patches", "libreoffice", "series").splitlines()
                 if n.strip() and not n.startswith("#")]
        self.assertIn(PATCH, names)
        self.assertGreater(names.index(PATCH), names.index("hst-user-autosave-test.patch"))

    def test_edit_mode_reopens_for_writing(self):
        code = added(PATCH, "sfx2/source/view/viewfrm.cxx")
        self.assertIn("*oForEdit && !pSh->IsOriginallyReadOnlyMedium()", code)
        self.assertIn("pNewSet->ClearItem( SID_DOC_READONLY );", code)
        self.assertIn("HstAutoSaveState().oOn = xOldObj->HstAutoSaveState().oOn", code)
        # a failed or cancelled switch (the locked-file question) leaves the document read only
        failed = code.index("SID_EDITDOC || rReq.GetSlot() == SID_READONLYDOC ) && *oForEdit )")
        self.assertIn("xOldObj->SetReadOnlyUI( true );", code[failed:failed + 160])

    def test_title_mark_follows_the_ui(self):
        self.assertIn("pMedium->IsReadOnly()", removed(PATCH, "sfx2/source/doc/sfxbasemodel.cxx"))
        self.assertIn("IsReadOnlyUI() || (pMedium && pMedium->HasRestrictedFonts())",
                      added(PATCH, "sfx2/source/doc/sfxbasemodel.cxx"))

    def test_info_page_button(self):
        ui = added(PATCH, "sfx2/uiconfig/ui/hstbackstage.ui")
        self.assertIn('id="inforeadonly"', ui)
        code = added(PATCH, "sfx2/source/backstage/hstbackstagewindow.cxx")
        self.assertIn('CloseAndDispatch(u".uno:EditDoc"_ustr)', code)
        self.assertIn("STR_HST_BS_EDIT_DOCUMENT", code)
        vi = po_entries(added(PATCH, "translations/source/vi/sfx2/messages.po"))
        self.assertEqual(vi["STR_HST_BS_READ_ONLY"][1], "Chuyển sang chỉ đọc")
        self.assertEqual(vi["STR_HST_BS_EDIT_DOCUMENT"][1], "Chỉnh sửa tài liệu")
        self.assertEqual(vi["hstbackstage|inforeadonly"][1], "Chuyển sang chỉ đọc")

    def test_recovery_question_defaults_to_cancel_after_discard(self):
        code = added(PATCH, "svx/source/dialog/docrecovery.cxx")
        self.assertIn("if (m_bBeforeRecovery)", code)
        self.assertIn("set_default_response(RET_CANCEL)", code)

    def test_windows_file_dialog_texts(self):
        code = added(PATCH, "fpicker/source/win32/VistaFilePickerImpl.cxx")
        for call in ("SetTitle", "SetOkButtonLabel", "SetFileNameLabel"):
            self.assertIn("iDialog->" + call, code)
        self.assertEqual(code.count("lcl_hstSetUiLanguageTexts(impl_getBaseDialogInterface()"), 3)
        ids = set(re.findall(r"STR_HST_FILEDLG_\w+", added(PATCH, "include/fpicker/strings.hrc")))
        vi = po_entries(added(PATCH, "translations/source/vi/fpicker/messages.po"))
        self.assertEqual(ids, set(vi))
        self.assertTrue(all(msgstr for _, msgstr in vi.values()))
        self.assertEqual(vi["STR_HST_FILEDLG_SAVE_AS"][1], "Lưu thành")  # glossary: Save As

    def test_view_tab_button(self):
        data = json.loads(read("data", "ribbon", "ribbon-v3.json"))
        for app in data["apps"]:
            view = next(t for t in app["tabs"] if t["id"] == "ViewLabel")
            first = view["groups"][0]["items"][0]
            if app["id"] == "draw":
                self.assertNotEqual(first["k"], "EditDoc")
                continue
            self.assertEqual((first["k"], first["kind"], first.get("new")), ("ReadOnlyDoc", "L", True), app["id"])
        v3 = read("patches", "libreoffice", "hst-ribbon-v3-ui.patch")
        self.assertEqual(v3.count('+                              <object class="GtkToolButton" id="btnViewHstReadOnlyDoc">'), 3)
        self.assertEqual(v3.count('+                                <property name="icon-name">cmd/lc_openreadonly.png</property>'), 3)
        keytips = json.loads(read("data", "ribbon", "keytips-office-parity.json"))
        self.assertEqual(keytips["commands"]["swriter"]["ViewLabel"]["ReadOnlyDoc"], ["F", "Read Mode"])
        tips = json.loads(read("data", "ribbon", "tooltip-descriptions.json"))["descriptions"]
        self.assertTrue(tips[".uno:ReadOnlyDoc"]["vi"].endswith("."))

    def test_view_tab_label_is_read_only(self):
        # lit while the document is read only: .uno:ReadOnlyDoc, named "Read-Only" / "Chỉ đọc" on the ribbon only
        v3 = read("patches", "libreoffice", "hst-ribbon-v3-ui.patch")
        tip = json.loads(read("data", "ribbon", "tooltip-descriptions.json"))["app_titles"]
        for ui, module, app in (("TabbedWriter", "sw", "writer"), ("TabbedCalc", "sc", "calc"),
                                ("TabbedImpress", "sd", "impress")):
            context = ui + "|btnViewHstReadOnlyDoc"
            self.assertIn('<property name="hst-ribbon-label" translatable="yes" context="%s">Read-Only</property>'
                          % context, v3)
            vi = po_entries(added(PATCH, "translations/source/vi/%s/messages.po" % module))
            self.assertEqual(vi[context], ("Read-Only", "Chỉ đọc"))
            self.assertEqual(tip[app][".uno:ReadOnlyDoc"], {"en": "Read-Only", "vi": "Chỉ đọc"})
    def test_sheets_protection_is_not_read_only(self):
        patch = read("patches", "libreoffice", "hst-ribbon-ux-calc.patch")
        for button in ("btnReviewProtect", "btnReviewToolProtectionDocument"):
            vi = re.search(r'msgctxt "TabbedCalc\|%s"\n\+msgid "Lock[^"]+"\n\+msgstr "([^"]+)"' % button, patch)
            self.assertIsNotNone(vi, button)
            self.assertIn("Không phải chế độ chỉ đọc", vi.group(1))


if __name__ == "__main__":
    unittest.main()
