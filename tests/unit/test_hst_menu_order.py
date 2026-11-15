# SPDX-License-Identifier: AGPL-3.0-only
"""The HST menu always ends with "Giải pháp HASON TECH" and "Kiểm tra cập nhật".

LibreOffice's configmgr orders set nodes by name length, then by name
(m1 … m9, m10 …), not by their order in Addons.xcu. New menu items must
therefore be numbered so these two entries stay last.
"""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ADDONS = Path(__file__).resolve().parents[2] / "extensions/hst-vietnamese-tools/Addons.xcu"
NAME = "{http://openoffice.org/2001/registry}name"


def menu_urls():
    root = ET.parse(ADDONS).getroot()
    top = next(n for n in root.iter("node") if n.get(NAME) == "org.hst.office.vi")
    submenu = next(n for n in top if n.get(NAME) == "Submenu")
    # Same ordering as configmgr's LengthContentsCompare.
    items = sorted(submenu, key=lambda n: (len(n.get(NAME)), n.get(NAME)))
    urls = []
    for item in items:
        url = next((p for p in item if p.get(NAME) == "URL"), None)
        urls.append(url.find("value").text if url is not None else None)
    return urls


def all_urls():
    """The URL of every item of the HST menu and its submenus."""
    root = ET.parse(ADDONS).getroot()
    top = next(n for n in root.iter("node") if n.get(NAME) == "org.hst.office.vi")
    return [next((p.find("value").text for p in n.findall("prop") if p.get(NAME) == "URL"), None)
            for n in top.iter("node") if n is not top and n.get(NAME) != "Submenu"]


class HstMenuOrder(unittest.TestCase):
    def test_solutions_and_update_are_last(self):
        self.assertEqual(menu_urls()[-2:], ["org.hst.office.vi:ShowSolutions", "org.hst.office.update:Check"])

    def test_feature_search_comes_right_before_them(self):
        self.assertEqual(menu_urls()[-3], ".uno:CommandPopup")

    def test_macro_vba_comes_before_feature_search(self):
        self.assertEqual(menu_urls()[-4], "org.hst.office.vi:EditVba")

    def test_duplex_and_default_apps_come_before_macro_vba(self):
        self.assertEqual(menu_urls()[-6:-4], ["org.hst.office.vi:ToggleDuplex", "org.hst.office.vi:DefaultApps"])

    def test_file_order_is_the_shown_order(self):
        # Addons.xcu lists the items as the menu shows them, so the source does not mislead (Ngôn ngữ giao diện
        # once sat after m15 in the file but was shown eighth)
        root = ET.parse(ADDONS).getroot()
        top = next(n for n in root.iter("node") if n.get(NAME) == "org.hst.office.vi")
        for submenu in (n for n in top.iter("node") if n.get(NAME) == "Submenu"):
            names = [n.get(NAME) for n in submenu.findall("node")]
            self.assertEqual(names, sorted(names, key=lambda n: (len(n), n)))

    def test_no_command_is_listed_twice(self):
        urls = [u for u in all_urls() if u]
        self.assertEqual(sorted({u for u in urls if urls.count(u) > 1}), [])


if __name__ == "__main__":
    unittest.main()
