# SPDX-License-Identifier: AGPL-3.0-only
"""Window mode per application (hst-document-window-modes.patch), read from the patch itself.

Every application (HST Writer, Sheets, Slides, Draw, PDF) chooses tabs or separate windows; the HST Office
window always takes the documents opened from it; "Apply to the open windows" splits or merges; crash
recovery restores one window per document for applications set to separate windows.
"""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-document-window-modes.patch")
APPS = ("Writer", "Calc", "Impress", "Draw", "Pdf")
UI_IDS = ("writer", "calc", "impress", "draw", "pdf")
MENUS = ("sw/uiconfig/swriter/menubar/menubar.xml", "sc/uiconfig/scalc/menubar/menubar.xml",
         "sd/uiconfig/simpress/menubar/menubar.xml", "sd/uiconfig/sdraw/menubar/menubar.xml")
TABGROUP = "framework/source/services/documenttabgroup.cxx"


def sections():
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None:
                current.append(line)
    return result


def added(path):
    return "\n".join(line[1:] for line in sections()[path] if line.startswith("+"))


def function(name):
    """Body of a member the patch adds; for a changed member, the patched hunks (added and context lines)."""
    text = "\n".join(line[1:] for line in sections()[TABGROUP] if line[:1] in ("+", " "))
    start = text.find(name)
    return text if start < 0 else text[start:text.find("\n}\n", start)]


class WindowModeOptionsTest(unittest.TestCase):
    def test_series_order(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        # after the patches it builds on (module windows, tab switch, UI mode per tab)
        for earlier in ("hst-module-window-groups.patch", "hst-document-tab-switch-no-flash.patch",
                        "hst-ui-mode-per-tab.patch"):
            self.assertLess(series.index(earlier), series.index("hst-document-window-modes.patch"))

    def test_one_boolean_per_application_defaults_to_tabs(self):
        schema = added("officecfg/registry/schema/org/openoffice/Office/Common.xcs")
        for app in APPS:
            with self.subTest(app=app):
                self.assertRegex(schema, r'<prop oor:name="DocumentTabs%s" oor:type="xs:boolean" '
                                         r'oor:nillable="false">[\s\S]*?<value>true</value>' % app)

    def test_mode_of_each_module_key(self):
        body = function("bool DocumentTabGroup::moduleUsesTabs")
        for key, app in zip(("writer", "calc", "impress", "draw", "pdf"), APPS):
            self.assertIn('if (rKind == u"%s")\n            return officecfg::Office::Common::Misc::'
                          'DocumentTabs%s::get();' % (key, app), body)
        self.assertIn("return true;", body)  # HST Office, Start Center, other modules: tabs

    def test_hst_office_window_takes_every_document(self):
        body = function("bool DocumentTabGroup::takesNewTab")
        self.assertIn("if (rGroup.aKind == OFFICE_KIND)\n        return true;", body)
        self.assertIn("accepts(rGroup, rModule) && !isSeparateWindow(rGroup) && moduleUsesTabs(rModule)", body)

    def test_routing_reuses_windows_only_in_tab_mode(self):
        body = function("DocumentTabGroup::Group& DocumentTabGroup::chooseGroup")
        self.assertIn("if (pContext && takesNewTab(*pContext, rModule))", body)
        self.assertIn("if (!rModule.isEmpty() && moduleUsesTabs(rModule))", body)
        self.assertIn("return newGroup(rModule);", body)

    def test_separate_window_has_no_strip_and_refuses_drops(self):
        self.assertIn("if (rGroup.aMembers.size() == 1 && isSeparateWindow(rGroup))\n        return false;",
                      function("bool DocumentTabGroup::showsTabBar"))
        self.assertIn("if (!takesNewTab(*pGroup, aModule) || groupIsFullScreen(*pGroup))",
                      function("bool DocumentTabGroup::mergeAt"))

    def test_options_changes_are_listened_to(self):
        source = added(TABGROUP)
        for app in APPS:
            self.assertIn('u"DocumentTabs%s"_ustr' % app, source)
        self.assertIn("mxListener->removeListener(pMode.get());", source)
        self.assertIn("DocumentTabGroup::get().windowModeChanged();", source)

    def test_apply_splits_and_merges_after_the_dialog(self):
        source = added(TABGROUP)
        # never while the Options dialog (its Apply button, the restart question) is still up
        self.assertIn("if (Application::IsInModalMode())\n    {\n        m_aApplyWindowModesTimer.Start();", source)
        split = function("void DocumentTabGroup::splitSeparateWindows")
        self.assertIn("detach(xFrame, aTopLeft);", split)
        self.assertIn("pKeep = &pGroup->aMembers.front();", split)  # one tab always stays shown
        merge = function("void DocumentTabGroup::mergeTabWindows")
        # joins the target first, then hides: a parked frame is never reported hidden (XFrameImpl)
        self.assertLess(merge.index("pGroup->aMembers.push_back(rMember);"), merge.index("park(*pMoved);"))
        self.assertNotIn("close", merge.replace("closed", ""))  # documents are never closed
        self.assertIn("rGroup.aKind == OFFICE_KIND", merge)
        self.assertIn('if (rArg.Name == "ApplyToOpenWindows")', source)  # scriptable without the dialog
        header = added("include/framework/documenttabs.hxx")
        self.assertIn("FWK_DLLPUBLIC void applyWindowModes();", header)

    def test_crash_restore_gives_one_window_per_document(self):
        body = function("DocumentTabGroup::restoreGroupFor")
        self.assertIn("pFound = bSeparate ? nullptr : groupById(rWindow.nGroup);", body)

    def test_options_page_rows_and_lock(self):
        ui = added("cui/uiconfig/ui/optgeneralpage.ui")
        for key in UI_IDS:
            with self.subTest(key=key):
                self.assertIn('id="%stabs"' % key, ui)
                self.assertIn('<property name="group">%stabs</property>' % key, ui)
                self.assertIn('id="lock%swindows"' % key, ui)
        self.assertIn('id="applyopenwindows"', ui)
        source = added("cui/source/options/optgdlg.cxx")
        self.assertIn("framework::DocumentTabs::applyWindowModes();", source)
        self.assertIn("rRow.xLock->set_visible(rRow.bReadOnly);", source)

    def test_vietnamese_texts(self):
        po = added("translations/source/vi/cui/messages.po")
        for key in UI_IDS:
            self.assertIn('msgctxt "optgeneralpage|%stabs"\nmsgid "Group files in one window (tabs)"\n'
                          'msgstr "Gom các tệp vào cùng một cửa sổ (dạng thẻ)"' % key, po)
            self.assertIn('msgctxt "optgeneralpage|%swindows"\nmsgid "Each file in its own window"\n'
                          'msgstr "Mỗi tệp một cửa sổ riêng"' % key, po)
        self.assertIn('msgstr "Á_p dụng cho các cửa sổ đang mở"', po)
        ui_po = added("translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po")
        self.assertIn('msgstr "Thẻ hay cửa sổ riêng..."', ui_po)

    def test_view_menu_command_opens_the_page(self):
        for menu in MENUS:
            self.assertIn('<menu:menuitem menu:id=".uno:DocumentWindowMode"/>', added(menu))
        source = added(TABGROUP)
        self.assertIn('rCommand == u".uno:DocumentWindowMode"', source)
        self.assertIn('makePropertyValue(u"OptionsPageID"_ustr', source)
        xcu = os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "FeatureSearch.xcu")
        with open(xcu, encoding="utf-8") as handle:
            keywords = handle.read()
        self.assertRegex(keywords, r"\.uno:DocumentWindowMode</value></prop>\s*<prop oor:name=\"Words\">"
                                   r"<value>[^<]*cửa sổ riêng[^<]*gom thẻ[^<]*tab[^<]*tách cửa sổ")

    def test_user_texts_name_no_foreign_office_suite(self):
        with open(PATCH, encoding="utf-8") as handle:
            text = handle.read()
        for name in ("Microsoft", "Word", "Excel", "PowerPoint"):
            self.assertNotRegex(text, r"\b%s\b" % name)


if __name__ == "__main__":
    unittest.main()
