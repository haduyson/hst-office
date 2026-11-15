# SPDX-License-Identifier: AGPL-3.0-only
"""Quick access toolbar of hst-ribbon-adaptive-qat.patch: defaults, the ▾ menu, add/remove from the ribbon, per-app
storage apart from the placement, overflow inside the tab row, and the row below the ribbon."""
import os
import re
import unittest

from _paths import ROOT

from patch_sections import added, po_entries, sections

PATCH = "hst-ribbon-adaptive-qat.patch"
APPS = {"sw/uiconfig/swriter": ".uno:OpenFromWriter", "sc/uiconfig/scalc": ".uno:OpenFromCalc",
        "sd/uiconfig/simpress": ".uno:Open", "sd/uiconfig/sdraw": ".uno:Open"}


MOCKUP_PATCH = "hst-ribbon-mockup-compact.patch"


def toolbar(module, patch=MOCKUP_PATCH):
    """[(command, visible)] of a module's notebookbarshortcuts.xml after the patch."""
    lines = [line[1:] for line in sections(patch)[f"{module}/toolbar/notebookbarshortcuts.xml"]
             if line[:1] in (" ", "+")]
    return [(m.group(1), m.group(2) is None) for m in
            re.finditer(r'xlink:href="([^"]+)"( toolbar:visible="false")?', "\n".join(lines))]


class Defaults(unittest.TestCase):
    def test_six_buttons_of_the_mockup_in_its_order(self):
        # New, Open ▾, Save ▾, Undo ▾, Redo ▾, Print (owner decision D3); KeyTips 1-6 follow this order
        for module, open_command in APPS.items():
            items = toolbar(module)
            self.assertEqual([c for c, shown in items if shown],
                             [".uno:AddDirect", open_command, ".uno:Save", ".uno:Undo", ".uno:Redo", ".uno:Print"],
                             module)
            hidden = {c for c, shown in items if not shown}
            for command in (".uno:PrintPreview", ".uno:SendMail"):
                self.assertIn(command, hidden, module)
        self.assertIn(".uno:Presentation", {c for c, shown in toolbar("sd/uiconfig/simpress") if not shown})

    def test_earlier_default_was_save_undo_redo(self):
        # the patch the mockup default replaces; a profile customised since keeps its own toolbar
        for module in APPS:
            self.assertEqual([c for c, shown in toolbar(module, PATCH) if shown],
                             [".uno:Save", ".uno:Undo", ".uno:Redo"], module)

    def test_checklist_matches_the_defaults(self):
        qat = added(PATCH, "sfx2/source/notebookbar/HstQuickAccess.cxx")
        for command in (".uno:AddDirect", ".uno:OpenFromWriter", ".uno:OpenFromCalc", ".uno:Save", ".uno:Print",
                        ".uno:PrintPreview", ".uno:SendMail", ".uno:Undo", ".uno:Redo"):
            self.assertIn(f'u"{command}"_ustr', qat)

    def test_mockup_patch_follows_the_qat_patch(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            series = handle.read().split()
        self.assertLess(series.index(PATCH), series.index(MOCKUP_PATCH))


class Behaviour(unittest.TestCase):
    def test_menu_offers_checklist_customize_and_placement(self):
        qat = added(PATCH, "sfx2/source/notebookbar/HstQuickAccess.cxx")
        self.assertIn("SetMenuType(ToolBoxMenuType::Customize | ToolBoxMenuType::ClippedItems)", qat)
        self.assertIn("SfxResId(STR_HST_QAT_CUSTOMIZE)", qat)
        self.assertIn("SfxResId(m_bBelow ? STR_HST_QAT_ABOVE : STR_HST_QAT_BELOW)", qat)
        self.assertIn('makePropertyValue(u"ResourceURL"_ustr, QAT_URL)', qat)

    def test_ribbon_right_click_adds_and_qat_right_click_removes(self):
        tabs = added(PATCH, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("pCommand->GetCommand() == CommandEventId::ContextMenu", tabs)
        qat = added(PATCH, "sfx2/source/notebookbar/HstQuickAccess.cxx")
        self.assertIn("SfxResId(bInQat ? STR_HST_QAT_REMOVE : STR_HST_QAT_ADD)", qat)
        drop = added(PATCH, "vcl/source/control/HstRibbonDrop.cxx")
        self.assertIn("m_xTabs->PreNotify(rNEvt)", drop)  # also in the compact ribbon's popup

    def test_list_saved_per_app_apart_from_placement(self):
        store = added(PATCH, "sfx2/source/notebookbar/HstQuickAccessStore.cxx")
        self.assertIn("->getUIConfigurationManager(aModule)", store)
        self.assertIn("XUIConfigurationPersistence>(xConfig, uno::UNO_QUERY_THROW)->store();", store)
        self.assertIn('compact::SetAppListed(u"QatBelowApps"_ustr, rApp, bBelow);', store)
        self.assertNotIn("officecfg::", store)
        schema = added(PATCH, "officecfg/registry/schema/org/openoffice/Office/HSTRibbon.xcs")
        self.assertIn('<prop oor:name="QatBelowApps" oor:type="oor:string-list" oor:nillable="false">', schema)

    def test_overflow_never_moves_the_tabs(self):
        tabctrl = added(PATCH, "vcl/source/control/tabctrl.cxx")
        self.assertIn("const tools::Long nRoom = nMaxWidth - nTabs - nSearch - 4;", tabctrl)
        self.assertIn("nH = nHeight - nTabBottom - TAB_OFFSET*2 - ImplHstPageBottomReserve();", tabctrl)

    def test_strings_are_vietnamese(self):
        entries = po_entries(added(PATCH, "translations/source/vi/sfx2/messages.po"))
        self.assertEqual(entries["STR_HST_QAT_ADD"][1], "Thêm vào thanh truy cập nhanh")
        self.assertEqual(entries["STR_HST_QAT_REMOVE"][1], "Xóa khỏi thanh truy cập nhanh")
        self.assertEqual(entries["STR_HST_QAT_CUSTOMIZE"][1], "Tùy chỉnh…")
        self.assertEqual(entries["STR_HST_QAT_BELOW"][1], "Hiện bên dưới ribbon")
        self.assertEqual(entries["STR_HST_QAT_ABOVE"][1], "Hiện bên trên ribbon")

    def test_new_sources_are_built(self):
        sfx = added(PATCH, "sfx2/Library_sfx.mk")
        self.assertIn("sfx2/source/notebookbar/HstQuickAccess \\", sfx)
        self.assertIn("sfx2/source/notebookbar/HstQuickAccessStore \\", sfx)


class ListenerThread(unittest.TestCase):
    def test_ui_configuration_listener_holds_the_solar_mutex(self):
        # a UNO client changing the toolbar from its own thread must not lay out the tab row unlocked
        code = added("hst-ribbon-shortcuts-listener-solarmutex.patch", "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("SolarMutexGuard aGuard;", code)
        self.assertIn("if (!m_pParent || m_pParent->isDisposed())", code)


if __name__ == "__main__":
    unittest.main()
