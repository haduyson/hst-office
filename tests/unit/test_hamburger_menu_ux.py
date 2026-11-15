# SPDX-License-Identifier: AGPL-3.0-only
"""The ribbon's ≡ menu (hst-hamburger-menu-ux.patch): feature search first in every app, Draw complete."""
import re
import unittest

from patch_sections import added, sections

PATCH = "hst-hamburger-menu-ux.patch"
APPS = ("sw/uiconfig/swriter", "sc/uiconfig/scalc", "sd/uiconfig/simpress", "sd/uiconfig/sdraw")
SEARCH = '<menu:menuitem menu:id=".uno:CommandPopup" menu:label="Tìm tính năng"/>'


def path(app):
    return app + "/popupmenu/notebookbar.xml"


class HamburgerMenu(unittest.TestCase):
    def test_every_app_starts_with_the_feature_search(self):
        for app in APPS:
            with self.subTest(app=app):
                lines = [line for line in sections(PATCH)[path(app)] if line[:1] in (" ", "+")]
                body = [line[1:].strip() for line in lines]
                start = body.index('<menu:menupopup xmlns:menu="http://openoffice.org/2001/menu">')
                self.assertEqual(body[start + 1], SEARCH)
                self.assertEqual(body[start + 2], "<menu:menuseparator/>")
                self.assertEqual(body[start + 3], '<menu:menuitem menu:id=".uno:Menubar" menu:style="text"/>')

    def test_draw_gets_report_and_update_after_help(self):
        lines = [line[1:].strip() for line in sections(PATCH)[path("sd/uiconfig/sdraw")] if line[:1] in (" ", "+")]
        ids = [m.group(1) for m in (re.search(r'menu:id="([^"]+)"', line) for line in lines) if m]
        self.assertEqual(ids, [".uno:CommandPopup", ".uno:Menubar", ".uno:ConfigureDialog", ".uno:OptionsTreeDialog",
                               ".uno:HelpIndex", "org.hst.office.vi:ReportError", "org.hst.office.update:Check",
                               ".uno:About"])
        text = added(PATCH, path("sd/uiconfig/sdraw"))
        self.assertIn('menu:label="Báo lỗi cho HASON TECH"', text)
        self.assertIn('menu:label="Kiểm tra cập nhật HST Office"', text)

    def test_other_apps_only_gain_the_search(self):
        for app in APPS[:3]:
            with self.subTest(app=app):
                self.assertEqual(added(PATCH, path(app)), "  " + SEARCH + "\n  <menu:menuseparator/>")


if __name__ == "__main__":
    unittest.main()
