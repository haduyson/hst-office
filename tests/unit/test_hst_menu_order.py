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


class HstMenuOrder(unittest.TestCase):
    def test_solutions_and_update_are_last(self):
        self.assertEqual(menu_urls()[-2:], ["org.hst.office.vi:ShowSolutions", "org.hst.office.update:Check"])


if __name__ == "__main__":
    unittest.main()
