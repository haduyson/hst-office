# SPDX-License-Identifier: AGPL-3.0-only
"""hst-module-window-groups.patch: HST Writer/Sheets/Slides/PDF windows of their own, tab detach.

Source-level checks of the patch (the behaviour is checked under Xvfb by tests/runtime/check-module-windows.py):
the routing reads the Referer that DispatchWatcher sets on every command line/IPC request, the tab commands act on
the window of their frame, the new texts are Vietnamese, and the patch is the last one of the series."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-module-window-groups.patch"
FILES = {
    "desktop/source/app/app.cxx", "framework/inc/documenttabgroup.hxx", "framework/inc/helper/titlebarupdate.hxx",
    "framework/inc/strings.hrc", "framework/inc/uielement/documenttabbar.hxx",
    "framework/source/dispatch/dispatchprovider.cxx", "framework/source/helper/titlebarupdate.cxx",
    "framework/source/loadenv/loadenv.cxx", "framework/source/services/documenttabgroup.cxx",
    "framework/source/uielement/documenttabbar.cxx", "include/framework/documenttabs.hxx",
    "officecfg/registry/data/org/openoffice/Office/UI/GenericCommands.xcu",
    "translations/source/vi/framework/messages.po",
    "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po",
    "vcl/inc/osx/salframe.h", "vcl/inc/salframe.hxx", "vcl/osx/salframe.cxx", "vcl/source/window/syswin.cxx",
}


def added():
    """file -> added lines of the patch"""
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], [])
        elif current is not None and line.startswith("+"):
            current.append(line[1:])
    return out


def text(path):
    return "\n".join(added()[path])


class ModuleWindowGroups(unittest.TestCase):
    def test_last_in_the_series(self):
        series = [n for n in (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
                  if not n.startswith("#")]
        self.assertEqual(series.count(PATCH.name), 1)
        self.assertEqual(series[-1], PATCH.name)

    def test_touches_the_planned_files_only(self):
        self.assertEqual(set(added()), FILES)
        header = PATCH.read_text(encoding="utf-8").split("\n---\n", 1)[0]
        self.assertIn("License: modified upstream files keep their license (MPL-2.0).", header)

    def test_external_origin_is_the_dispatch_watcher_referer(self):
        loadenv = text("framework/source/loadenv/loadenv.cxx")
        self.assertIn('== "private:OpenEvent"', loadenv)
        self.assertIn("PROP_REFERRER", loadenv)
        # both show paths of LoadEnv route through the origin helper
        self.assertEqual(loadenv.count("lcl_prepareDocumentTab(xTargetFrame")
                         + loadenv.count("lcl_prepareDocumentTab(m_xTargetFrame"), 2)
        self.assertIn('aOrigin.aModule = u"pdf"_ustr', loadenv)

    def test_routing_rules(self):
        group = text("framework/source/services/documenttabgroup.cxx")
        choose = group[group.index("DocumentTabGroup::chooseGroup"):group.index("void DocumentTabGroup::setKind")]
        # Start Center -> HST Office window; external -> new window; first window -> HST Office; else context
        order = [choose.index(s) for s in ("rModule == START_MODULE", "if (bExternal)", "m_aGroups.empty()",
                                           "contextGroup()", "accepts(*pContext, rModule)")]
        self.assertEqual(order, sorted(order))
        accepts = group[group.index("bool DocumentTabGroup::accepts"):]
        self.assertIn("rGroup.aKind == OFFICE_KIND", accepts[:400])

    def test_commands_act_on_the_window_of_their_frame(self):
        self.assertIn("DocumentTabGroup::createCommandDispatch(xFrame)",
                      text("framework/source/dispatch/dispatchprovider.cxx"))
        group = text("framework/source/services/documenttabgroup.cxx")
        self.assertIn('rCommand == u".uno:DetachDocumentTab"', group)
        self.assertIn("activateRelative(\n                xFrame,", group)

    def test_detach_keeps_the_kind_and_never_maximizes(self):
        group = text("framework/source/services/documenttabgroup.cxx")
        detach = group[group.index("void DocumentTabGroup::detach"):group.index("void DocumentTabGroup::moveTab")]
        self.assertIn("newGroup(pSource->aKind)", detach)
        self.assertIn("vcl::WindowState::Normal", group)
        self.assertIn("Platform::Wayland", group)
        self.assertIn("canDetach", detach)

    def test_office_window_taskbar_identity(self):
        update = text("framework/source/helper/titlebarupdate.cxx")
        self.assertIn("isOfficeWindow(xFrame)", update)
        self.assertIn('sDesktopName = "Startcenter"', update)

    def test_hst_office_launcher_shows_its_own_window(self):
        app = text("desktop/source/app/app.cxx")
        self.assertIn("framework::DocumentTabs::showOfficeWindow()", app)
        self.assertIn("#include <framework/documenttabs.hxx>", app)

    def test_vietnamese_texts(self):
        self.assertIn('msgstr "Tách ra cửa sổ mới"', text("translations/source/vi/framework/messages.po"))
        self.assertIn("STR_DOCTAB_DETACH", text("framework/inc/strings.hrc"))
        self.assertIn(".uno:DetachDocumentTab", text("officecfg/registry/data/org/openoffice/Office/UI/GenericCommands.xcu"))
        ui = text("translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po")
        self.assertIn('msgstr "Tách thẻ tài liệu ra cửa sổ mới"', ui)
        # cfgex reads the first contiguous GenericCommands run only: the entry follows PrevDocumentTab
        patch = PATCH.read_text(encoding="utf-8")
        self.assertTrue(re.search(r'\n msgstr "Thẻ tài liệu trước"\n \n\+#\. hstMW', patch))

    def test_no_foreign_product_names(self):
        for path, lines in added().items():
            for line in lines:
                self.assertIsNone(re.search(r"Microsoft|\bWord\b|Excel|PowerPoint", line), (path, line))

    def test_macos_native_tabs_stay_within_a_group(self):
        mac = text("vcl/osx/salframe.cxx")
        self.assertIn("pOther->mnTabGroupId != mnTabGroupId", mac)
        self.assertIn("SetTabGroupId", text("vcl/inc/salframe.hxx"))


if __name__ == "__main__":
    unittest.main()
