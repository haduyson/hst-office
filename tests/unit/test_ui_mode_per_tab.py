# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ui-mode-per-tab.patch: every document tab shows the user interface mode and the toolbars of its own module.

User report 13/11/2026: after "Apply to All" (or trying the modes one by one) the Sheets tab of a window with Writer
and Sheets tabs showed only the menubar: the ribbon was closed, and the toolbars, stored as invisible by an earlier
switch to a ribbon mode, never came back; a Sheets file opened from that window got the same. GUI: tests/runtime/
check-ui-mode-tabs.py (Linux) and check-windows-ui-mode-tabs.py. Offline: the patch hunks per file."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-ui-mode-per-tab.patch"
HXX = "include/sfx2/notebookbar/SfxNotebookBar.hxx"
CXX = "sfx2/source/notebookbar/SfxNotebookBar.cxx"
APPSERV = "sfx2/source/appl/appserv.cxx"
WORKWIN = "sfx2/source/appl/workwin.cxx"
PICKER = "cui/source/dialogs/uipickerdlg.cxx"
LAYOUT = "framework/source/layoutmanager/layoutmanager.cxx"


def changes():
    """{path: (removed lines, added lines)}"""
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").split("\n---\n", 1)[1].splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], ([], []))
        elif current is None or line.startswith(("@@", "--- a/")):
            continue
        elif line.startswith("-"):
            current[0].append(line[1:])
        elif line.startswith("+"):
            current[1].append(line[1:])
    return out


def added(path):
    return "\n".join(changes()[path][1])


class UiModePerTab(unittest.TestCase):
    def test_last_after_the_tab_and_notebookbar_patches(self):
        series = [n for n in (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
                  if not n.startswith("#")]
        self.assertEqual(series.count(PATCH.name), 1)
        for earlier in ("hst-document-tabs.patch", "hst-module-window-groups.patch", "hst-menubar-toggle.patch",
                        "hst-document-tab-switch-no-flash.patch"):
            self.assertGreater(series.index(PATCH.name), series.index(earlier))

    def test_files(self):
        self.assertEqual(set(changes()), {HXX, CXX, APPSERV, WORKWIN, PICKER, LAYOUT})
        self.assertIn("License: modified upstream files keep their license (MPL-2.0).",
                      PATCH.read_text(encoding="utf-8").split("\n---\n")[0])

    def test_mode_of_the_frame_not_of_current(self):
        self.assertIn("static bool IsActiveFor(const css::uno::Reference<css::frame::XFrame>& xFrame,", added(HXX))
        cxx = added(CXX)
        self.assertIn("if (xFrame.is() ? IsActiveFor(xFrame) : IsActive())", cxx)
        self.assertIn("return IsActiveFor(pViewFrm->GetFrame().GetFrameInterface(), bConsiderSingleToolbar);", cxx)
        self.assertIn("IsActiveFor(GetFrameInterface(), true)", added(WORKWIN))
        self.assertIn("sfx2::SfxNotebookBar::IsActive(true)", "\n".join(changes()[WORKWIN][0]))

    def test_menubar_of_the_frames_module(self):
        cxx = added(CXX)
        self.assertIn("SfxNotebookBar::ShowMenubarForModuleOf(xFrame, bHasMenubar);", cxx)
        self.assertIn("SfxNotebookBar::ShowMenubarForModuleOf(xFrame, true);", cxx)
        self.assertIn("void SfxNotebookBar::ShowMenubar(bool bShow) { ShowMenubarForModuleOf({}, bShow); }", cxx)
        # closing a ribbon shows the frame's own menubar too (a parked tab of the module)
        self.assertRegex(cxx, r"ShowMenubarForModuleOf\(xFrame, true\);\s*(//[^\n]*\n\s*)+if \(const Reference<frame::"
                              r"XLayoutManager> xLayoutManager = lcl_getLayoutManager\(xFrame\);[^}]*showElement\(MENUBAR_STR\);")

    def test_toolbars_of_the_mode_come_back_when_a_ribbon_closes(self):
        cxx = added(CXX)
        body = cxx[cxx.index("static void lcl_showModeToolbars"):]
        self.assertLess(body.index("createElement(rToolbar)"), body.index("showElement(rToolbar)"))
        self.assertIn('for (const char* pList : { "Toolbars", "UserToolbars" })', cxx)
        closing = cxx[cxx.index("SfxNotebookBar::ShowMenubarForModuleOf(xFrame, true);"):]
        self.assertRegex(closing[:900], r"if \(xFrame\.is\(\)\)\s*lcl_showModeToolbars\(xFrame\);")
        self.assertNotIn("lcl_firstSetup", cxx)  # no per-frame repair at set-up: it showed toolbars of other modes

    def test_menubar_of_a_loading_frame_changes_nothing(self):
        cxx = added(CXX)
        body = cxx[cxx.index("void SfxNotebookBar::ShowMenubarForModuleOf"):]
        self.assertLess(body.index("try"), body.index("identify( xModuleFrame )"))
        self.assertIn("m_bLock = false;\n        return;", body)

    def test_apply_to_all_stores_the_toolbars_of_the_other_applications(self):
        picker = added(PICKER)
        self.assertIn("void lcl_storeModeToolbars(const OUString& rApp, const OUString& rModuleId, const OUString& rMode)",
                      picker)
        self.assertIn("css::ui::theWindowStateConfiguration::get(xContext)->getByName(rModuleId)", picker)
        self.assertIn('aNew.push_back(comphelper::makePropertyValue(u"Visible"_ustr, bVisible));', picker)
        for app, module in (("Writer", "text.TextDocument"), ("Calc", "sheet.SpreadsheetDocument"),
                            ("Impress", "presentation.PresentationDocument"), ("Draw", "drawing.DrawingDocument")):
            self.assertIn('std::pair{ "%s", "com.sun.star.%s" }' % (app, module), picker)
        self.assertIn("if (sCurrentApp != OUString::createFromAscii(pApp))", picker)

    def test_shown_again_frame_updates_its_object_bars(self):
        workwin = added(WORKWIN)
        self.assertIn("const bool bWasInvisible = !m_pWrkWin->IsVisible_Impl();", workwin)
        self.assertRegex(workwin, r"if \( bWasInvisible \)\s*if \( SfxDispatcher\* pDispatcher = "
                                  r"m_pWrkWin->GetBindings\(\)\.GetDispatcher_Impl\(\) \)\s*pDispatcher->Update_Impl\( true \);")

    def test_visible_is_sent_after_the_toolbars_are_unhidden(self):
        removed, layout = "\n".join(changes()[LAYOUT][0]), added(LAYOUT)
        self.assertIn("implts_notifyListeners( frame::LayoutManagerEvents::VISIBLE, a );", removed)
        self.assertIn("    if ( !bSetVisible )", layout)  # INVISIBLE (unchanged line) still goes out first
        self.assertIn("    if ( bSetVisible )\n        implts_notifyListeners( frame::LayoutManagerEvents::VISIBLE, a );", layout)

    def test_same_mode_again_applies(self):
        removed = "\n".join(changes()[APPSERV][0])
        self.assertIn("aCurrentMode == aNewName", removed)
        self.assertNotIn("aCurrentMode == aNewName", added(APPSERV))


if __name__ == "__main__":
    unittest.main()
