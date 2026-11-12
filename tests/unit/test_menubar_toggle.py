# SPDX-License-Identifier: AGPL-3.0-only
"""The classic menu bar toggle (hst-menubar-toggle.patch), read from the patch and the extension.

Owner decisions of 2026-11-13: the menu bar stays hidden under the ribbon by default; "Thanh trình đơn" turns it on
and off from the classic View menu and the "≡" menu, and the feature search (Alt+Q) finds it; while it is shown its
Alt+letter mnemonics and F10 work; the "≡" menu no longer repeats Mới / Gần đây / Đóng nor offers the UI-mode and
toolbar choosers.
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-menubar-toggle.patch")
APPS = ("sw/uiconfig/swriter", "sc/uiconfig/scalc", "sd/uiconfig/simpress")
MENU = "{http://openoffice.org/2001/menu}"


def sections():
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None and not line.startswith("--- "):
                current.append(line)
    return result


def added(path):
    return "\n".join(line[1:] for line in sections()[path] if line.startswith("+"))


def after(path):
    """The hunks of one file as they read after the patch (context and added lines)."""
    return "\n".join(line[1:] for line in sections()[path] if line[:1] in (" ", "+"))


class MenubarTogglePatchTest(unittest.TestCase):
    def test_the_patch_is_in_the_series(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            self.assertIn("hst-menubar-toggle.patch", handle.read().split())

    def test_view_menu_offers_the_toggle_after_the_ui_chooser(self):
        for app in APPS:
            with self.subTest(app=app):
                text = after(app + "/menubar/menubar.xml")
                self.assertIn('<menu:menuitem menu:id=".uno:UIPicker" menu:style="text"/>\n'
                              '      <menu:menuitem menu:id=".uno:Menubar" menu:style="text"/>', text)

    def test_notebookbar_menu_has_the_toggle_and_no_duplicates(self):
        for app in APPS:
            with self.subTest(app=app):
                path = app + "/popupmenu/notebookbar.xml"
                self.assertIn('menu:id=".uno:Menubar"', added(path))
                text = after(path)
                for gone in (".uno:AddDirect", ".uno:RecentFileList", ".uno:CloseDoc", ".uno:UIPicker",
                             ".uno:AvailableToolbars"):
                    self.assertNotIn(f'"{gone}"', text, gone)
                # the hunk starts at the top of the menu: the toggle comes first, then customising and options
                self.assertIn('<menu:menupopup xmlns:menu="http://openoffice.org/2001/menu">\n'
                              '  <menu:menuitem menu:id=".uno:Menubar" menu:style="text"/>\n'
                              '  <menu:menuitem menu:id=".uno:ConfigureDialog"/>\n'
                              '  <menu:menuitem menu:id=".uno:OptionsTreeDialog"/>', text)

    def test_toggle_only_with_a_ribbon(self):
        source = added("sfx2/source/appl/appserv.cxx")
        self.assertIn("if (sfx2::SfxNotebookBar::IsActive())\n                sfx2::SfxNotebookBar::ToggleMenubar();",
                      source)
        self.assertIn("if (!sfx2::SfxNotebookBar::IsActive())", source)
        self.assertIn("rSet.Put(SfxVisibilityItem(nWhich, false));", source)

    def test_shown_menu_bar_keeps_alt_letter_and_f10(self):
        source = added("sfx2/source/notebookbar/HstRibbonKeyTips.cxx")
        self.assertIn("return pMenuBar && pMenuBar->IsDisplayable();", source)
        self.assertRegex(source, r"if \(IsF10\(rCode\)\)\n\s+\{\n\s+if \(bMenubar\)\n\s+return false;\n\s+ShowTabs\(\);")
        self.assertIn("&& !bMenubar ? LetterOf(rCode) : 0;", source)
        self.assertIn("rKey.GetCode() == KEY_F10 || rKey.GetCode() == KEY_MENU", source)


class FeatureSearchFindsTheToggleTest(unittest.TestCase):
    def test_keywords_of_the_toggle(self):
        root = ET.parse(os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "FeatureSearch.xcu")).getroot()
        name = "{http://openoffice.org/2001/registry}name"
        words = {}
        for node in root.iter("node"):
            props = {p.get(name): p.find("value").text for p in node.findall("prop")}
            if "Command" in props:
                words[props["Command"]] = props["Words"]
        self.assertIn("thanh trình đơn", words[".uno:Menubar"])
        self.assertIn("thanh menu", words[".uno:Menubar"])  # the word users still type


if __name__ == "__main__":
    unittest.main()
